# Chạy M0/M1 trên Windows PowerShell

Mở terminal tại root repo, dùng Python 3.11+. Nếu dùng venv, thay python bằng
.\.venv\Scripts\python.exe. Cài môi trường theo README nếu chưa có dependency.

Các lệnh sau không gọi mạng:

```powershell
python -m medical_data_crawler.multisource_cli sources
python -m medical_data_crawler.multisource_cli pmc capabilities
python -m medical_data_crawler.multisource_cli pmc --help
python -m medical_data_crawler.multisource_cli pmc demo --output data/pmc-m1-demo
python -m medical_data_crawler.multisource_cli pmc demo --output data/pmc-m1-demo
python -m medical_data_crawler.multisource_cli pmc verify --output data/pmc-m1-demo
python -m medical_data_crawler.multisource_cli report --output data/pmc-m1-demo
Get-ChildItem data/pmc-m1-demo/runs -Recurse
```

Demo là một bài TỔNG HỢP. Hai lần chạy tạo hai report/event, một original, một
document/rendition; lượt hai báo duplicates=1. Đếm report là lượt xử lý, không phải
số tài liệu duy nhất. Mở PMCID.txt/PMCID.json trong thư mục runs để xem văn bản/
Structured Raw. Original là file mang tên SHA-256, chứa XML; đọc bằng VS Code
hoặc Get-Content. Không đổi nội dung hoặc ghi đè original.

Chuẩn bị approval cho PMCID thật do operator chọn sau khi review liên quan tổn thương
da (thay PMC123 bằng PMCID đã review):

```powershell
New-Item -ItemType Directory -Force data/pmc-approvals
python -m medical_data_crawler.multisource_cli pmc prepare --pmcid PMC123 | Set-Content -Encoding utf8 data/pmc-approvals/pilot.json
```

Reader chấp nhận UTF-8 có hoặc không BOM từ PowerShell. Không sửa template thành
approved nếu chưa có quyết định operator.

Hồ sơ gồm approved, source_terms_reviewed, skin_scope_reviewed,
exclusive_provider_ip, pmcids, operations, valid_from/valid_until ISO-8601 có múi giờ,
output và rights. Chỉ cấp hạn ngắn; output đề nghị data/pmc-live.
Mỗi rights.PMCID cần license_uri chính xác, retain_original=true,
third_party_reviewed=true, evidence là căn cứ đã review; extract_text=true khi đã
duyệt trích xuất. Bỏ extract_content khỏi operations nếu chỉ lưu original.
Không cấp AI/phân phối trong phiên này.

Trước pilot thật cần trình operator: endpoint PMC OAI, GetRecord/retain/store/extract,
PMCID cụ thể (1–3), output, căn cứ quyền từng bài, 1 request/giây, tối đa một request
mỗi PMCID, 30 giây và 4 MiB/request. Chỉ sau phê duyệt tường minh mới chạy:

```powershell
python -m medical_data_crawler.multisource_cli pmc validate --approval data/pmc-approvals/pilot.json
python -m medical_data_crawler.multisource_cli pmc pilot --approval data/pmc-approvals/pilot.json --enable-live
python -m medical_data_crawler.multisource_cli pmc verify --output data/pmc-live
```

Validate chỉ kiểm tra cấu hình/grant còn hạn, không xác nhận căn cứ pháp lý. Lệnh
pilot thiếu --enable-live bị chặn. Sau lỗi, giữ report/marker, chẩn đoán và xin duyệt
lại trước lần thử mới. Không scraping thay thế. Mọi output/approval ở data/ đã ignore.
Trong phiên triển khai này chưa có phê duyệt nên không chạy lệnh pilot.

Kiểm thử offline:

```powershell
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

Nếu temp Windows lỗi ACL, dùng thư mục CHƯA TỒN TẠI dưới data:
python -m pytest -q --basetemp=data/pytest-m1-local.
Pytest có thể xóa basetemp cũ; không trỏ vào corpus hay thư mục dữ liệu cần giữ.
