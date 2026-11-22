# Medical Data Crawler

Dự án thu thập kiến thức về tổn thương da thuộc K01–K08 cho Medical RAG. Đầu ra mục tiêu là Structured Raw truy được về tài liệu gốc. Session 01 cung cấp nền tảng Python, kiểm tra bản ghi v0.1 và hàm băm byte. Session 02 bổ sung ArtifactStore và ProvenanceStore, exact deduplication và stable document ID. Session 03 tiếp nhận file HTML/PDF cục bộ, trích xuất content blocks và điều phối offline; có thể dựng record v0.1 trong bộ nhớ khi caller cung cấp thông tin quyền truy cập. Chưa có HTTP crawling production, nguồn thực tế được duyệt, scheduler, batch exporter hoặc manifest. Chunking, embeddings, truy xuất RAG, chẩn đoán và xử lý ảnh nằm ngoài phạm vi.

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

## Cấu trúc

| Đường dẫn | Nội dung |
| --- | --- |
| `src/medical_data_crawler/` | Nền tảng, storage/provenance, acquisition, HTML/PDF extraction và offline pipeline |
| `tests/unit/`, `tests/contract/`, `tests/integration/`, `tests/fixtures/` | Unit/contract/integration tests và mẫu tổng hợp tự tạo; chặn network trong tests |
| `docs/` | [Kiến trúc](docs/ARCHITECTURE.md), [hợp đồng dữ liệu](docs/DATA_CONTRACT.md), [hướng dẫn phát triển](docs/DEVELOPMENT.md) |
| `.github/workflows/quality.yml` | CI kiểm tra package, lint, format và tests |

Xem [cách chạy fixture offline](docs/DEVELOPMENT.md#chạy-fixture-session-03-offline).
HTML được đọc theo DOM, bảng ở dạng text có cảnh báo khi mất cấu trúc. PDF chỉ hỗ
trợ text layer, báo từng trang lỗi/rỗng và giới hạn reading order; không có OCR.
Thông tin trang nằm trong extraction nội bộ vì schema v0.1 chưa biểu diễn được.
Chưa kiểm chứng fidelity trên bộ tài liệu production. Chi tiết trong
[kiến trúc](docs/ARCHITECTURE.md).

Đọc toàn bộ `DEFINE_PROBLEM_v1.0.md` tại root hoặc `docs/` trước khi thay đổi dự án;
giữ nguyên nội dung đặc tả đã khóa.
