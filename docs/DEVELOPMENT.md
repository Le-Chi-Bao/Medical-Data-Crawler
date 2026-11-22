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
$testBase = Join-Path (Get-Location) ('data/pytest-' + [guid]::NewGuid())
python -m pytest -q --basetemp $testBase
```

Kiểm tra thay đổi hợp đồng bằng cả fixture hợp lệ và ca bị từ chối. Dùng `git diff --cached` để rà phạm vi commit. GitHub Actions cài package từ checkout trên Python 3.11 và 3.12, sau đó chạy cùng các kiểm tra. Thay đổi ý nghĩa dữ liệu hoặc mở rộng scope cần review theo Problem Definition.

## Chạy fixture Session 03 offline

Sau khi cài dependency, pipeline không cần Internet. Chạy đoạn Python sau tại root
(trong PowerShell có thể lưu thành script cục bộ hoặc dùng here-string đưa vào Python):

```python
from pathlib import Path

from medical_data_crawler.acquisition import DocumentRequest, LocalDocumentAdapter
from medical_data_crawler.pipeline import OfflinePipeline, RecordRights
from medical_data_crawler.provenance import ProvenanceStore
from medical_data_crawler.storage import ArtifactStore

artifacts = ArtifactStore(Path("data/offline-demo/originals"))
events = ProvenanceStore(Path("data/offline-demo/events"), artifacts)
pipeline = OfflinePipeline(artifacts, LocalDocumentAdapter(artifacts, events))
request = DocumentRequest(
    Path("tests/fixtures/synthetic.html"),
    source_id="synthetic-fixtures",
    logical_key="session03-html",
    locator="repository-fixture:synthetic.html",
)
result = pipeline.process(
    request, rights=RecordRights("Self-authored synthetic repository fixture")
)
print(result.extraction.status, len(result.extraction.blocks))
print(result.warnings, result.errors)
assert result.record is not None
```

File HTML do phiên này tự tạo, không phải nguồn y khoa production. Chạy lại tái sử
dụng original nhưng ghi event mới. `data/` đã được ignore; không stage originals hay
event sinh ra. Bỏ đối số `rights` để chỉ nhận extraction nội bộ khi chưa có access
basis. Không tự áp dụng access basis của fixture cho nguồn thực tế.

Chạy nhóm kiểm thử offline (dùng basetemp mới trên Windows như hướng dẫn phía trên):

```powershell
$testBase = Join-Path $env:TEMP ('mdc-session03-' + [guid]::NewGuid())
python -m pytest -q tests/unit/test_acquisition.py tests/unit/test_html_extraction.py tests/unit/test_pdf_extraction.py tests/integration --basetemp $testBase
```

`tests/conftest.py` chặn kết nối socket và DNS trong tests. PDF được tạo trong bộ nhớ
bằng pypdf với text tổng hợp/font Helvetica, trang rỗng, stream hỏng hoặc mật khẩu
fixture; không cần download hay reportlab. Test fault injection bổ sung lỗi backend
và page boundaries. Các test không thay thế đánh giá fidelity trên tài liệu thực,
font Unicode PDF hay layout nhiều cột đại diện. Giới hạn và cấu hình cố định của
extractor nằm trong [ADR 05](ARCHITECTURE.md#adr-05--acquisition-và-extraction-offline-trong-session-03).

## Chạy export batch offline

Chạy từ root sau khi cài package.

```powershell
python scripts/demo_offline_export.py
```

Demo dùng HTML tổng hợp có sẵn và tạo thêm HTML có media, PDF trang trắng cùng
một yêu cầu file bị thiếu. Một yêu cầu riêng bỏ qua quyền truy cập để minh họa
`skipped`. Kết quả dự kiến là 5 đầu vào, 3 record xuất thành công, 1 mục
`failed`, 1 mục `skipped`. Ba record xuất ra lần lượt có trạng thái extraction
`success`, `partial`, `failed`. Demo in `Verification PASS` sau khi đọc lại batch.

```text
data/offline-export-demo/
  originals/<sha256>
  events/<event_id>.json
  exports/<batch_id>/manifest.json
  exports/<batch_id>/records/<input_index>.json
```

Trong ứng dụng, gọi `export_batch(pipeline.process_many(requests, rights=rights),
output_root, provenance)` để lấy đường dẫn manifest. Đối với quyền khác nhau
theo tài liệu, gọi `pipeline.process(request, rights=rights_for_request)` cho
từng yêu cầu rồi chuyển iterable kết quả vào `export_batch`.
`verify_batch(manifest_path, provenance)` trả `VerificationResult` với
`valid`, `error_code` và `input_index` (nếu lỗi gắn với một mục). Lỗi toàn batch
khi export được báo qua `ExportError`. Mã lỗi trong manifest và kết quả xác minh
dùng giá trị cố định để tránh tiết lộ chi tiết đầu vào. Scope của demo là dữ liệu
tổng hợp. Dùng căn cứ truy cập được xác minh cho từng tài liệu khi chuyển sang pilot.

Chạy riêng nhóm kiểm thử exporter và hai schema.

```powershell
$testBase = Join-Path (Get-Location) ('data/pytest-export-' + [guid]::NewGuid())
python -m pytest -q tests/contract tests/integration/test_export.py tests/unit/test_export_publication.py --basetemp $testBase
```
