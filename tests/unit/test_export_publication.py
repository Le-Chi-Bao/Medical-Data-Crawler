import pytest

from medical_data_crawler.export import _publish


def test_atomic_publisher_refuses_existing_file_and_cleans_temporary_file(tmp_path):
    target = tmp_path / "published.json"
    _publish(target, b'{"version": 1}')
    mtime = target.stat().st_mtime_ns
    with pytest.raises(FileExistsError):
        _publish(target, b'{"version": 2}')
    assert target.read_bytes() == b'{"version": 1}'
    assert target.stat().st_mtime_ns == mtime
    assert list(tmp_path.iterdir()) == [target]
