# Medical Data Crawler

Dự án thu thập kiến thức về tổn thương da thuộc K01–K08 cho Medical RAG. Đầu ra mục tiêu là Structured Raw truy được về tài liệu gốc. Session 01 cung cấp nền tảng Python, kiểm tra bản ghi v0.1 và hàm băm byte. Crawler, extraction engine và export pipeline thuộc các phiên sau. Chunking, embeddings, truy xuất RAG, chẩn đoán và xử lý ảnh nằm ngoài phạm vi.

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
| `src/medical_data_crawler/` | Cấu hình, logging, exceptions, SHA-256, validator và schema |
| `tests/unit/`, `tests/contract/`, `tests/fixtures/` | Unit tests, contract tests và mẫu tự tạo |
| `docs/` | [Kiến trúc](docs/ARCHITECTURE.md), [hợp đồng dữ liệu](docs/DATA_CONTRACT.md), [hướng dẫn phát triển](docs/DEVELOPMENT.md) |
| `.github/workflows/quality.yml` | CI kiểm tra package, lint, format và tests |

Đọc `DEFINE_PROBLEM_v1.0.md` trước khi thay đổi dự án. File được track tại root trong baseline hiện tại. Nếu working tree đã di chuyển tài liệu vào `docs/`, đọc bản tại đó.
