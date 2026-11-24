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

## Kiểm tra registry nguồn offline

```powershell
python -m pytest -q tests/unit/test_source_policy.py
```

Nhóm test kiểm tra schema đóng gói, registry tại `config/source_candidates.v0.1.json`
và các đường cấp quyền bằng fixture tổng hợp. Khi review một thay đổi registry, giải mã
hai snapshot JSON và gọi `validate_registry_update(previous, proposed, at=...)` với
thời điểm quyết định có múi giờ. Xem [chính sách nguồn](SOURCE_POLICY.md) trước khi dùng
gate trong luồng tiếp nhận. Đánh giá corpus dùng [phiếu baseline](PILOT_EVALUATION.md).

## Chạy HTML preflight offline

Sau khi cài package vào virtual environment theo README, chạy từ root với fixture tổng hợp.

```powershell
python -B scripts/inspect_html_preflight.py tests/fixtures/synthetic.html
```

Script in JSON gồm metadata và số đếm để hỗ trợ reviewer điền hồ sơ. Gọi
`inspect_html()` từ `medical_data_crawler.html_preflight` khi cần dùng kết quả
trong mã Python. Test dùng fixture tổng hợp và chặn socket/DNS theo cấu hình chung.
Xem cách đặt giới hạn byte, cung cấp tên trường chứng cứ HTTP và đọc kết quả. [HTML preflight](HTML_PREFLIGHT.md)

## Kiểm tra HTTP acquisition ngoại tuyến

Chạy tại root sau khi cài package.

```powershell
python scripts/demo_http_acquisition.py
python -m pytest -q tests/unit/test_http_acquisition.py tests/unit/test_https_transport.py tests/integration/test_http_pipeline.py
```

Demo in `Verification PASS` và manifest của hai bản ghi đã trích xuất thành công.
Mỗi lần chạy cấp event và batch ID mới. ArtifactStore dùng lại original nếu byte
trùng. Output dưới `data/http-acquisition-demo/` đã được Git ignore.

Test adapter dùng phản hồi HTTP tổng hợp qua `http.client.HTTPResponse`. Test transport
dùng socket giả để kiểm tra IP đích, hostname TLS, trust store, header request và
deadline. DNS và kết nối thật bị chặn bởi fixture chung. Dùng thư mục pytest tạm
riêng theo hướng dẫn phía trên nếu Windows từ chối quyền truy cập. Xem API cấu hình,
quyền và hành vi khi tải lỗi. [HTTP acquisition](HTTP_ACQUISITION.md)

## Kiểm tra tiếp nhận nội bộ ngoại tuyến

Chạy bằng Python trong virtual environment tại root repo.

```powershell
python scripts/demo_internal_import.py
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

Demo cấp phê duyệt cho HTML và PDF tổng hợp, dùng thêm một bản HTML trùng byte,
một PDF hỏng và một đầu vào thiếu phê duyệt. Báo cáo dự kiến có tổng 5 mục, 3
bản ghi xuất và 2 lỗi. Hai original ứng với ba sự kiện được chấp nhận. Demo xác
minh manifest và in `Verification PASS`. Dữ liệu sinh ra nằm trong `data/`.

Dùng fixture tổng hợp cho test cấp quyền và lỗi file, kể cả test đường dẫn đặc
thù Windows. Các test offline được bảo vệ bởi fixture chặn socket và DNS. Sau
khi cài package, chạy `python -m medical_data_crawler.internal_import_cli --help`
để xem tham số. [Định dạng đặc tả và cách chạy batch](INTERNAL_IMPORT.md)

## Chạy Catalog SQLite ngoại tuyến

```powershell
python scripts/demo_catalog.py
python -m pytest -q tests/unit/test_catalog_model.py tests/contract/test_catalog_schema.py tests/integration/test_catalog_workflow.py tests/integration/test_catalog_legacy_link.py
```

Demo xác minh 13 document tổng hợp ở 2 miền và replay cùng metadata trên
`data/catalog-demo/catalog.sqlite3`. Giá trị `integrity` là `pass` khi các kiểm
tra SQLite hoàn tất. Mở API catalog dưới thư mục trạng thái do người vận hành
kiểm soát. Database demo nằm trong `data/`, đã được Git ignore.
[Cách dùng API và các mã lỗi](CATALOG_IMPLEMENTATION.md)
