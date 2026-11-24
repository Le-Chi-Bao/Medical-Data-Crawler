import hashlib
import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .errors import FoundationError
from .storage import ArtifactStore, StorageError


class ProvenanceError(FoundationError):
    """Sự kiện tiếp nhận không hợp lệ hoặc không ghi được."""


@dataclass(frozen=True)
class HTTPAttempt:
    """One exchange with a policy-checked locator and a fixed outcome code."""

    source_id: str
    locator: str
    attempted_at: str
    status: int | None
    outcome: str


@dataclass(frozen=True)
class HTTPTrace:
    user_agent: str
    outcome: str
    attempts: tuple[HTTPAttempt, ...]


def _validate_text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ProvenanceError("Trường văn bản phải là chuỗi khác rỗng")
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise ProvenanceError("Trường văn bản không mã hóa được UTF-8") from None


def document_id(source_id: str, logical_key: str) -> str:
    """Caller cung cấp khóa logic bền vững theo chính sách nguồn đã duyệt."""
    _validate_text(source_id)
    _validate_text(logical_key)
    identity = json.dumps([source_id, logical_key], ensure_ascii=False).encode("utf-8")
    return "doc:" + hashlib.sha256(identity).hexdigest()


class ProvenanceStore:
    def __init__(self, root: Path, artifacts: ArtifactStore):
        self.root = root
        self.artifacts = artifacts
        root.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        *,
        source_id: str,
        logical_key: str,
        locator: str,
        acquired_at: datetime,
        checksum: str | None,
        error_code: str | None = None,
        http: HTTPTrace | None = None,
    ) -> str:
        """Chỉ nhận locator đã loại secrets/PHI và mã lỗi từ danh sách an toàn."""
        identity = document_id(source_id, logical_key)
        _validate_text(locator)
        try:
            if not isinstance(acquired_at, datetime) or acquired_at.utcoffset() is None:
                raise ProvenanceError("Thời điểm tiếp nhận cần datetime có múi giờ")
            timestamp = acquired_at.isoformat()
        except (ValueError, TypeError, OverflowError):
            raise ProvenanceError("Thời điểm tiếp nhận không hợp lệ") from None
        if (
            (checksum is not None and not isinstance(checksum, str))
            or (checksum is None) == (error_code is None)
            or (
                error_code is not None
                and (
                    not isinstance(error_code, str)
                    or error_code not in {"read_error", "invalid_input"}
                )
            )
        ):
            raise ProvenanceError("Thông tin sự kiện không hợp lệ")
        artifact = None
        if checksum is not None:
            try:
                artifact = self.artifacts.verify(checksum)
            except StorageError:
                raise ProvenanceError("Tham chiếu artifact không hợp lệ") from None
        event_id = uuid4().hex
        event = {
            "event_version": "0.1",
            "event_id": event_id,
            "document_id": identity,
            "source_id": source_id,
            "locator": locator,
            "acquired_at": timestamp,
            "artifact_reference": artifact.reference if artifact else None,
            "sha256": artifact.sha256 if artifact else None,
            "byte_size": artifact.byte_size if artifact else None,
            "status": "accepted" if artifact else "failed",
            "error_code": error_code,
        }
        if http is not None:
            event["http"] = asdict(http)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.root, prefix=".pending-", delete=False
            ) as out:
                temporary = Path(out.name)
                json.dump(event, out, ensure_ascii=False)
                out.flush()
                os.fsync(out.fileno())
            os.link(temporary, self.root / (event_id + ".json"))
        except OSError:
            raise ProvenanceError("Không công bố được sự kiện") from None
        finally:
            if temporary is not None:
                active_error = sys.exception()
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    if active_error is None:
                        raise ProvenanceError("Sự kiện đã công bố nhưng cleanup thất bại") from None
                    active_error.add_note("Không dọn được temporary file của sự kiện")
        return event_id
