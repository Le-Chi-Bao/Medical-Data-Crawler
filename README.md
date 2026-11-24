# Medical Data Crawler

Dự án thu thập kiến thức về tổn thương da thuộc K01–K08 cho Medical RAG. Pipeline tiếp nhận HTML/PDF cục bộ hoặc tải từng tài liệu từ URL HTTPS đã duyệt khi caller bật HTTP. Cả hai luồng lưu byte gốc theo SHA-256, ghi provenance, trích xuất nội dung và xuất Structured Raw v0.1 khi có căn cứ truy cập. Manifest v0.1 cho phép đối chiếu checksum, nguồn gốc và trạng thái từng mục. Chunking, embeddings, truy xuất RAG, chẩn đoán và xử lý ảnh nằm ngoài phạm vi.

## Cài đặt và kiểm tra

Dùng Python 3.11 trở lên. Chạy tại root bằng PowerShell.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m ruff format --check .
```

Trên Linux/macOS dùng `.venv/bin/python` thay cho đường dẫn Windows. Việc cài dependency có thể cần mạng. Tests chỉ dùng dữ liệu cục bộ.

## Demo export offline

```powershell
.\.venv\Scripts\python scripts/demo_offline_export.py
```

Demo dùng fixture tổng hợp HTML/PDF và in đường dẫn manifest, thống kê cùng kết quả xác minh. Batch nằm tại `data/offline-export-demo/exports/<batch_id>/`. Originals và sự kiện nằm trong `originals/` và `events/` cùng cấp với `exports/`. Toàn bộ `data/` đã được Git ignore. Xem [cách tích hợp và kiểm tra](docs/DEVELOPMENT.md#chạy-export-batch-offline) và [kết quả nghiệm thu MVP](docs/MVP_VERIFICATION.md).

## Demo HTTP bằng fixture offline

```powershell
.\.venv\Scripts\python scripts/demo_http_acquisition.py
```

Demo dùng registry tổng hợp trong bộ nhớ, resolver và transport giả lập. Demo tải hai fixture HTML/PDF vào ArtifactStore, trích xuất, xuất batch và xác minh manifest dưới `data/http-acquisition-demo/`. HTTP mặc định tắt. Xem cấu hình cho URL đã duyệt và quy trình tiếp nhận tài liệu nội bộ. [HTTP acquisition](docs/HTTP_ACQUISITION.md)

## Cấu trúc

| Đường dẫn | Nội dung |
| --- | --- |
| `src/medical_data_crawler/` | Storage, provenance, acquisition, trích xuất HTML/PDF, export và xác minh batch |
| `tests/unit/`, `tests/contract/`, `tests/integration/`, `tests/fixtures/` | Unit/contract/integration tests và mẫu tổng hợp tự tạo; chặn network trong tests |
| `docs/` | [Kiến trúc](docs/ARCHITECTURE.md), [hợp đồng dữ liệu](docs/DATA_CONTRACT.md), [hướng dẫn phát triển](docs/DEVELOPMENT.md) |
| `.github/workflows/quality.yml` | CI kiểm tra package, lint, format và tests |

HTML được đọc theo DOM, bảng ở dạng text có cảnh báo khi mất cấu trúc. PDF chỉ hỗ
trợ text layer, báo từng trang lỗi/rỗng và giới hạn reading order; không có OCR.
Thông tin trang nằm trong extraction nội bộ vì schema v0.1 chưa biểu diễn được.
Chưa kiểm chứng fidelity trên bộ tài liệu production. Chi tiết trong
[kiến trúc](docs/ARCHITECTURE.md).

Đọc toàn bộ `DEFINE_PROBLEM_v1.0.md` tại root hoặc `docs/` trước khi thay đổi dự án;
giữ nguyên nội dung đặc tả đã khóa.

## Chuẩn bị corpus pilot

[Registry v0.1](config/source_candidates.v0.1.json) có 16 ứng viên đang chờ review.
Xem [chính sách nguồn](docs/SOURCE_POLICY.md), [kế hoạch tuyển mẫu](docs/PILOT_PLAN.md),
[phiếu đánh giá offline](docs/PILOT_EVALUATION.md) và [trạng thái pilot](docs/PILOT_READINESS.md).
