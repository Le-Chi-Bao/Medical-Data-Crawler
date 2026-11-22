import hashlib
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

from .errors import FoundationError
from .integrity import sha256_stream


class StorageError(FoundationError):
    """Artifact thiếu, bị hỏng hoặc không thể lưu an toàn."""


@dataclass(frozen=True)
class Artifact:
    reference: str
    sha256: str
    byte_size: int


class ArtifactStore:
    """Lưu byte trên filesystem có hỗ trợ hard link atomic, không thay thế file."""

    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def _path(self, checksum: str) -> Path:
        if not isinstance(checksum, str) or re.fullmatch(r"[0-9a-f]{64}", checksum) is None:
            raise StorageError("Checksum không hợp lệ")
        return self.root / checksum

    def verify(self, checksum: str) -> Artifact:
        path = self._path(checksum)
        try:
            if path.is_symlink() or not path.is_file():
                raise StorageError("Artifact thiếu hoặc không phải file thường")
            with path.open("rb") as stream:
                actual = sha256_stream(stream)
                size = stream.tell()
            if actual != checksum or size == 0:
                raise StorageError("Artifact không toàn vẹn")
            return Artifact(checksum, checksum, size)
        except OSError:
            raise StorageError("Không đọc được artifact") from None

    def copy_to(self, checksum: str, destination: BinaryIO) -> Artifact:
        """Xác minh trước khi đọc và kiểm tra lại chính stream đang sao chép."""
        artifact = self.verify(checksum)
        digest = hashlib.sha256()
        size = 0
        try:
            with self._path(checksum).open("rb") as source:
                while chunk := source.read(65536):
                    digest.update(chunk)
                    size += len(chunk)
                    if destination.write(chunk) != len(chunk):
                        raise StorageError("Đích ghi không đủ byte")
        except (OSError, ValueError, TypeError, AttributeError):
            raise StorageError("Không sao chép được artifact") from None
        if digest.hexdigest() != checksum or size != artifact.byte_size:
            raise StorageError("Artifact thay đổi trong khi đọc")
        return artifact

    def put(self, source: bytes | BinaryIO) -> Artifact:
        stream = BytesIO(source) if isinstance(source, bytes) else source
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=self.root, prefix=".pending-", delete=False
            ) as out:
                temporary = Path(out.name)
                digest = hashlib.sha256()
                size = 0
                while True:
                    chunk = stream.read(65536)
                    if not isinstance(chunk, bytes):
                        raise StorageError("Input stream phải trả về bytes")
                    if not chunk:
                        break
                    digest.update(chunk)
                    if out.write(chunk) != len(chunk):
                        raise StorageError("Temporary file ghi không đủ byte")
                    size += len(chunk)
                out.flush()
                os.fsync(out.fileno())
            if size == 0:
                raise StorageError("Từ chối artifact rỗng")
            checksum = digest.hexdigest()
            target = self._path(checksum)
            try:
                os.link(temporary, target)
            except FileExistsError:
                self.verify(checksum)
                with temporary.open("rb") as incoming, target.open("rb") as existing:
                    while chunk := incoming.read(65536):
                        if existing.read(len(chunk)) != chunk:
                            raise StorageError("Xung đột nội dung tại đường dẫn hash") from None
                    if existing.read(1):
                        raise StorageError("Xung đột kích thước artifact") from None
            return self.verify(checksum)
        except (OSError, ValueError, TypeError, AttributeError):
            raise StorageError("Không lưu được artifact") from None
        finally:
            if temporary is not None:
                active_error = sys.exception()
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    if active_error is None:
                        raise StorageError("Artifact đã công bố nhưng cleanup thất bại") from None
                    active_error.add_note("Không dọn được temporary file của artifact")
