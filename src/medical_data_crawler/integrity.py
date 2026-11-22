import hashlib
from typing import BinaryIO


def sha256_stream(stream: BinaryIO) -> str:
    """Băm các byte từ vị trí hiện tại đến EOF. Caller quản lý vòng đời stream."""
    digest = hashlib.sha256()
    while chunk := stream.read(65536):
        digest.update(chunk)
    return digest.hexdigest()
