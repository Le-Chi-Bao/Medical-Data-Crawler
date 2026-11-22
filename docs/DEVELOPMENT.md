# Phát triển và kiểm tra

Cài môi trường theo [README](../README.md). Các lệnh dưới đây dùng Python trong virtual environment đã kích hoạt.

## Cấu hình

Gọi `load_settings()` để lấy mặc định hoặc truyền `Path` tới file TOML. Ví dụ:

```toml
data_dir = "data"
log_level = "INFO"
```

Biến `MDC_DATA_DIR` và `MDC_LOG_LEVEL` ưu tiên hơn TOML. Đường dẫn tương đối tính từ thư mục đang chạy. Đọc cấu hình không tạo thư mục. Các mức hỗ trợ gồm DEBUG, INFO, WARNING, ERROR và CRITICAL.

## Thử validator

```python
import json
from pathlib import Path

from medical_data_crawler.contract import validate_record

record = json.loads(Path("tests/fixtures/record.json").read_text(encoding="utf-8"))
validate_record(record)
```

Khi thêm producer, gọi `configure_logging(settings)` từ entry point, dùng logger dưới `medical_data_crawler` và chỉ ghi thông tin vận hành cần thiết.

## Kiểm tra trước commit

Chạy `python -m pytest -q`, `python -m ruff check .` và `python -m ruff format --check .`. Khi Windows từ chối truy cập thư mục tạm dùng chung của pytest, dùng thư mục mới riêng cho lần chạy:

```powershell
$testBase = Join-Path $env:TEMP ('mdc-' + [guid]::NewGuid())
python -m pytest -q --basetemp $testBase
```

Kiểm tra thay đổi hợp đồng bằng cả fixture hợp lệ và ca bị từ chối. Dùng `git diff --cached` để rà phạm vi commit. GitHub Actions cài package từ checkout trên Python 3.11 và 3.12, sau đó chạy cùng các kiểm tra. Thay đổi ý nghĩa dữ liệu hoặc mở rộng scope cần review theo Problem Definition.
