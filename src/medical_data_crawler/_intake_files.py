"""Bounded file snapshots for the offline internal intake gateway."""

import codecs
import logging
import os
import re
import stat
import sys
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from functools import cache
from html.parser import HTMLParser
from pathlib import Path
from tempfile import SpooledTemporaryFile
from threading import Lock
from typing import BinaryIO

from pypdf import PdfReader

from .integrity import sha256_stream
from .pipeline import detect_media_type

INTAKE_MEDIA_TYPES = {"html": "text/html", "htm": "text/html", "pdf": "application/pdf"}
MAX_INPUT_BYTES = 32 * 1024 * 1024
_CHUNK_SIZE = 64 * 1024
_SPOOL_IN_MEMORY = 1024 * 1024
_WINDOWS_RESERVED = re.compile(r"CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³]|CONIN\$|CONOUT\$")
_HTML_ELEMENTS = frozenset(
    (
        "html head body title meta main article section header footer nav div p h1 h2 h3 h4 h5 h6 "
        "table thead tbody tr td th span ul ol dl li dt dd pre blockquote figure strong em a img "
        "hr br b i form script style template"
    ).split()
)
_HTML_BOMS = (
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
)


class IntakeFileError(Exception):
    """A controlled code without user-supplied path or parser details."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


_private_parser = ContextVar("private_intake_parser", default=False)
_diagnostic_lock = Lock()
_diagnostic_users = 0
_prior_factory = None


def _private_record(name, level, fn, lno, msg, args, exc_info, func=None, sinfo=None, **kwargs):
    if _private_parser.get() and name.split(".", 1)[0] in {"pypdf", "bs4"}:
        msg, args, exc_info, sinfo = "internal_intake_parser_diagnostic", (), None, None
    return _prior_factory(name, level, fn, lno, msg, args, exc_info, func, sinfo, **kwargs)


@contextmanager
def private_pdf_diagnostics() -> Iterator[None]:
    """Redact diagnostics only in the current intake context, including concurrent calls."""
    global _diagnostic_users, _prior_factory
    with _diagnostic_lock:
        if not _diagnostic_users:
            _prior_factory = logging.getLogRecordFactory()
            logging.setLogRecordFactory(_private_record)
        _diagnostic_users += 1
    token = _private_parser.set(True)
    try:
        yield
    finally:
        _private_parser.reset(token)
        with _diagnostic_lock:
            _diagnostic_users -= 1
            if not _diagnostic_users and logging.getLogRecordFactory() is _private_record:
                logging.setLogRecordFactory(_prior_factory)


@cache
def _windows_api():
    import ctypes
    from ctypes import wintypes

    class AttributeTagInfo(ctypes.Structure):
        _fields_ = [("attributes", wintypes.DWORD), ("tag", wintypes.DWORD)]

    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
    api.GetDriveTypeW.restype = wintypes.UINT
    api.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    api.CreateFileW.restype = wintypes.HANDLE
    api.GetFileInformationByHandleEx.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    api.GetFileInformationByHandleEx.restype = wintypes.BOOL
    api.GetFileType.argtypes = [wintypes.HANDLE]
    api.GetFileType.restype = wintypes.DWORD
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.CloseHandle.restype = wintypes.BOOL
    return api, AttributeTagInfo


def _local_path(value: str | Path) -> Path:
    try:
        raw = os.fspath(value)
    except TypeError:
        raise IntakeFileError("invalid_path") from None
    if not isinstance(raw, str) or not raw or any(ord(char) < 32 for char in raw):
        raise IntakeFileError("invalid_path")
    if raw.replace("\\", "/").startswith("//") or "://" in raw or raw.lower().startswith("file:"):
        raise IntakeFileError("network_path_disallowed")
    path = Path(raw)
    if not path.is_absolute():
        raise IntakeFileError("invalid_path")
    if ".." in path.parts:
        raise IntakeFileError("path_outside_root")
    if os.name == "nt":
        if not re.fullmatch(r"[A-Za-z]:", path.drive) or any(
            re.search(r'[:<>"|?*]', part)
            or part.endswith((".", " "))
            or _WINDOWS_RESERVED.fullmatch(part.split(".", 1)[0].rstrip().upper())
            for part in path.parts[1:]
        ):
            raise IntakeFileError("invalid_path")
        api, _ = _windows_api()
        drive_type = api.GetDriveTypeW(path.anchor)
        if drive_type == 4:  # DRIVE_REMOTE
            raise IntakeFileError("network_path_disallowed")
        if drive_type not in {2, 3, 5, 6}:  # Removable, fixed, optical and RAM disk
            raise IntakeFileError("invalid_path")
    return path


def _reject_link(info: os.stat_result) -> None:
    if stat.S_ISLNK(info.st_mode) or (
        getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    ):
        raise IntakeFileError("path_link_disallowed")


def check_local_path(value: str | Path) -> Path:
    """Check the path and its existing ancestors without requiring the tail to exist."""
    path = _local_path(value)
    try:
        for component in (*reversed(path.parents), path):
            info = component.lstat()
            _reject_link(info)
            if component != path and not stat.S_ISDIR(info.st_mode):
                raise IntakeFileError("invalid_path")
    except FileNotFoundError:
        pass
    except (OSError, UnicodeError, ValueError):
        raise IntakeFileError("invalid_path") from None
    return path


@contextmanager
def _windows_handle(path: Path, *, directory: bool) -> Iterator[int]:
    import ctypes

    api, attribute_info = _windows_api()
    # OPEN_REPARSE_POINT examines the final component itself. BACKUP_SEMANTICS
    # permits directory handles. Holding read-sharing handles prevents concurrent
    # write/delete handles from changing ancestors before children are opened.
    open_reparse_point, backup_semantics = 0x00200000, 0x02000000
    read_attributes, generic_read = 0x80, 0x80000000
    share_read, open_existing = 1, 3
    handle = api.CreateFileW(
        str(path),
        read_attributes if directory else generic_read,
        share_read,
        None,
        open_existing,
        open_reparse_point | backup_semantics,
        None,
    )
    if handle is None or handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        info = attribute_info()
        if not api.GetFileInformationByHandleEx(
            handle,
            9,
            ctypes.byref(info),
            ctypes.sizeof(info),  # FileAttributeTagInfo
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        if info.attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise IntakeFileError("path_link_disallowed")
        if bool(info.attributes & stat.FILE_ATTRIBUTE_DIRECTORY) != directory:
            raise IntakeFileError("invalid_path" if directory else "not_regular_file")
        if api.GetFileType(handle) != 1:  # FILE_TYPE_DISK
            raise IntakeFileError("not_regular_file")
        yield handle
    finally:
        api.CloseHandle(handle)


@contextmanager
def _open_windows(path: Path) -> Iterator[BinaryIO]:
    import _winapi
    import msvcrt

    with ExitStack() as handles:
        for parent in reversed(path.parents):
            handles.enter_context(_windows_handle(parent, directory=True))
        handle = handles.enter_context(_windows_handle(path, directory=False))
        # The CRT stream owns its duplicate. The checked handle retains the
        # no-write/no-delete sharing policy for the whole read.
        process = _winapi.GetCurrentProcess()
        duplicate = _winapi.DuplicateHandle(
            process, handle, process, 0, False, _winapi.DUPLICATE_SAME_ACCESS
        )
        try:
            descriptor = msvcrt.open_osfhandle(duplicate, os.O_RDONLY | os.O_BINARY)
        except OSError:
            _winapi.CloseHandle(duplicate)
            raise
        with os.fdopen(descriptor, "rb") as stream:
            yield stream


@contextmanager
def _open_posix(path: Path) -> Iterator[BinaryIO]:
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    with ExitStack() as handles:
        parent = os.open(path.anchor, directory_flags)
        handles.callback(os.close, parent)
        edges = []
        for index, part in enumerate(path.parts[1:], start=1):
            initial = os.stat(part, dir_fd=parent, follow_symlinks=False)
            _reject_link(initial)
            is_file = index == len(path.parts) - 1
            if is_file and not stat.S_ISREG(initial.st_mode):
                raise IntakeFileError("not_regular_file")
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK if is_file else directory_flags
            descriptor = os.open(part, flags, dir_fd=parent)
            handles.callback(os.close, descriptor)
            opened = os.fstat(descriptor)
            if not os.path.samestat(initial, opened):
                raise IntakeFileError("file_changed")
            edges.append((parent, part, opened))
            parent = descriptor
        with os.fdopen(parent, "rb", closefd=False) as stream:
            yield stream
        for parent, part, opened in edges:
            try:
                current = os.stat(part, dir_fd=parent, follow_symlinks=False)
            except OSError:
                raise IntakeFileError("file_changed") from None
            if not os.path.samestat(opened, current):
                raise IntakeFileError("file_changed")


@contextmanager
def open_local_binary(value: str | Path) -> Iterator[BinaryIO]:
    """Open an explicit absolute local file with link-safe ancestor traversal."""
    path = _local_path(value)
    if path == Path(path.anchor):
        raise IntakeFileError("not_regular_file")
    opener = _open_windows if os.name == "nt" else _open_posix
    try:
        with opener(path) as stream:
            yield stream
    except FileNotFoundError:
        raise IntakeFileError("file_not_found") from None
    except NotADirectoryError:
        raise IntakeFileError("invalid_path") from None
    except (OSError, UnicodeError, ValueError):
        raise IntakeFileError("read_error") from None


def _copy_bounded(source: BinaryIO, destination: BinaryIO, before: os.stat_result) -> None:
    size = 0
    while chunk := source.read(min(_CHUNK_SIZE, before.st_size - size + 1)):
        size += len(chunk)
        if size > before.st_size:
            raise IntakeFileError("file_changed")
        if destination.write(chunk) != len(chunk):
            raise IntakeFileError("partial_read")
    after = os.fstat(source.fileno())
    if (after.st_size, after.st_mtime_ns, after.st_ctime_ns) != (
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    ) or not os.path.samestat(before, after):
        raise IntakeFileError("file_changed")
    if size != before.st_size:
        raise IntakeFileError("partial_read")


class _HTMLStructure(HTMLParser):
    has_html_markup = False

    def handle_decl(self, decl: str) -> None:
        self.has_html_markup |= decl.lower().split()[:2] == ["doctype", "html"]

    def handle_starttag(self, tag: str, attrs) -> None:
        self.has_html_markup |= tag in _HTML_ELEMENTS


def _validate_html(snapshot: BinaryIO) -> None:
    if detect_media_type(snapshot, "text/html") != "text/html":
        raise IntakeFileError("format_mismatch")
    prefix = snapshot.read(4)
    bom, encoding = next(
        ((bom, encoding) for bom, encoding in _HTML_BOMS if prefix.startswith(bom)),
        (b"", "latin1"),
    )
    snapshot.seek(len(bom))
    decoder = codecs.getincrementaldecoder(encoding)()
    parser = _HTMLStructure(convert_charrefs=False)
    try:
        while chunk := snapshot.read(_CHUNK_SIZE):
            parser.feed(decoder.decode(chunk))
            if len(parser.rawdata) > _CHUNK_SIZE:
                raise IntakeFileError("invalid_document")
        parser.feed(decoder.decode(b"", final=True))
        if parser.rawdata.startswith("<") or parser.cdata_elem:
            raise IntakeFileError("invalid_document")
        parser.close()
    except (ValueError, AssertionError, RecursionError):
        raise IntakeFileError("invalid_document") from None
    if not parser.has_html_markup:
        raise IntakeFileError("format_mismatch")


def _validate_content(snapshot: BinaryIO, media_type: str) -> None:
    if media_type == "application/pdf":
        if snapshot.read(5) != b"%PDF-":
            raise IntakeFileError("format_mismatch")
        snapshot.seek(0)
        try:
            with private_pdf_diagnostics():
                reader = PdfReader(snapshot, strict=True)
                if not reader.is_encrypted:
                    # Walk the page tree only. Text parsing remains permission-gated.
                    len(reader.pages)
        except Exception:
            raise IntakeFileError("invalid_document") from None
        return

    _validate_html(snapshot)


def _local_temp_directory() -> Path:
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            raise IntakeFileError("snapshot_error")
        path = Path(local_app_data) / "Temp"
    else:
        path = Path("/private/tmp" if sys.platform == "darwin" else "/tmp")
    path = check_local_path(path)
    if not path.is_dir():
        raise IntakeFileError("snapshot_error")
    return path


def _inside_root(path: Path, root: Path) -> bool:
    # Windows can enable case-sensitive directories, so compare component names
    # exactly. Drive letters can safely use either case.
    return (
        len(path.parts) > len(root.parts)
        and path.anchor.lower() == root.anchor.lower()
        and path.parts[1 : len(root.parts)] == root.parts[1:]
    )


@contextmanager
def snapshot_document(
    local_path: str,
    approved_roots: tuple[Path, ...],
    declared_format: str,
    max_bytes: int,
    expected_sha256: str | None,
    *,
    dry_run: bool = False,
) -> Iterator[tuple[BinaryIO, str]]:
    """Validate a bounded, private snapshot and yield its verified bytes and digest."""
    if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_INPUT_BYTES:
        raise IntakeFileError("invalid_size_limit")
    path = _local_path(local_path)
    if not any(_inside_root(path, root) for root in approved_roots):
        raise IntakeFileError("path_outside_root")
    declared = INTAKE_MEDIA_TYPES.get(declared_format)
    suffix = INTAKE_MEDIA_TYPES.get(path.suffix.removeprefix(".").lower())
    if declared is None or suffix is None:
        raise IntakeFileError("unsupported_format")
    if declared != suffix:
        raise IntakeFileError("format_mismatch")
    with ExitStack() as snapshots:
        with open_local_binary(path) as original:
            before = os.fstat(original.fileno())
            if before.st_size == 0:
                raise IntakeFileError("empty_file")
            if before.st_size > max_bytes:
                raise IntakeFileError("file_too_large")
            spool_limit = max_bytes if dry_run else _SPOOL_IN_MEMORY
            temp_directory = _local_temp_directory() if before.st_size > spool_limit else None
            snapshot = snapshots.enter_context(
                SpooledTemporaryFile(max_size=spool_limit, mode="w+b", dir=temp_directory)
            )
            _copy_bounded(original, snapshot, before)
        snapshot.seek(0)
        digest = sha256_stream(snapshot)
        if expected_sha256 is not None and digest != expected_sha256:
            raise IntakeFileError("checksum_mismatch")
        snapshot.seek(0)
        _validate_content(snapshot, declared)
        snapshot.seek(0)
        yield snapshot, digest
