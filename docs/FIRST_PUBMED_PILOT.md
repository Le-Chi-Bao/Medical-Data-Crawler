# Lần thử PubMed đầu tiên — Session 06D.1P

**READY FOR OPERATOR REVIEW. Chưa lấy dữ liệu PubMed thật.**
Ngày kiểm tra: 25/11/2026. File local ban đầu không tồn tại tại
`data/operator/pubmed-approval.json`; vì vậy reader trả `invalid_operator_approval`.
Không có file của lần chạy trước để xác định nó từng sai trường nào.
Phiên này đã tạo mẫu local, giữ cả ba cờ xác nhận ở `false`.

### Cập nhật Stage A ngày 26/11/2026

Đã nhận xác nhận riêng của operator cho điều khoản metadata, đúng một pilot
tối đa 20 bản ghi và IP egress không có client NCBI khác. Cửa sổ local được
chuẩn bị theo đồng hồ hệ thống: 00:43:43–01:43:43 UTC+07 cùng ngày.
Chỉ sau xác nhận mới bật ba cờ; validator trả `ready`.

Đã chạy đúng một lần:

```powershell
python -m medical_data_crawler.pubmed_cli pilot --approval data/operator/pubmed-approval.json --enable-network --limit 20
```

Lệnh thoát với exit code 2 và `redirect_denied` trong exchange ESearch đầu tiên.
Có truy cập mạng thật nhưng transport từ chối HTTP 3xx trước khi đọc metadata;
không đi theo redirect, không retry lỗi terminal này. Không tạo run ID, snapshot,
report của pilot hay catalog live. Kết quả phiên này: **0 bản ghi PubMed thật,
0 tài liệu toàn văn, 0 bản trích xuất từ tài liệu thật**.

CLI chỉ lưu mã lỗi cố định; không có status 3xx cụ thể hoặc `Location` để xác
định đích chuyển hướng. Chưa đủ bằng chứng kết luận lỗi tương thích provider.
Không tự đổi endpoint, bật redirect hoặc tắt TLS. Giữ bằng chứng chẩn đoán local
ở `data/operator/pubmed-stage-a-attempt-20261126.json`; đây là báo cáo thao tác,
không phải report acquisition thành công. Lượt duyệt duy nhất đã được sử dụng;
cờ `true` trong file không phải quyền tự chạy lại. Cần operator duyệt lượt chẩn
đoán mạng tiếp theo; lệnh pilot bên trên chỉ được dùng lại sau phê duyệt đó.
Không có checkpoint để resume. Stage B chưa được mở do Stage A chưa thành công
và chưa có phạm vi/quyền toàn văn riêng.

Kiểm tra offline phiên này: `796 passed, 2 skipped` (symlink Windows).
`profiles`, `preview --profile melanoma-v1 --limit 20` và `demo` đều chạy;
demo giữ 2 document tổng hợp, 16 observations, integrity pass, 0 network requests.
Lint/format `src tests scripts` đạt (82 file). Lệnh lint toàn workspace vẫn báo
3.171 lỗi, format báo 249 file cần sửa trong dependency local có sẵn dưới
`docs/data/`; không sửa dependency đó. Đoạn PowerShell chuẩn bị thời hạn bên
dưới đã chạy trên fixture local hai lần: giữ nguyên cờ, backup khớp byte mẫu,
lần hai không ghi lại cửa sổ còn hiệu lực. Đặc tả khóa và thay đổi có sẵn của
operator được giữ nguyên.

## 1. Chuẩn bị file phê duyệt

Chạy từ thư mục gốc repository trong PowerShell, với môi trường Python đã cài
project. Mẫu công khai không chứa bí mật hay quyền được bật sẵn:

```powershell
New-Item -ItemType Directory -Path data/operator -Force | Out-Null
if (-not (Test-Path -LiteralPath data/operator/pubmed-approval.json)) {
    Copy-Item -LiteralPath examples/pubmed-approval.example.json -Destination data/operator/pubmed-approval.json
}
notepad data/operator/pubmed-approval.json
```

Không ghi đè file phê duyệt có sẵn. Không đưa file local vào Git.
Chỉ người vận hành có thẩm quyền mới xác nhận các điều kiện sau:

| Điều kiện | Việc phải làm trước khi xác nhận |
|---|---|
| `source_terms_reviewed` | Đọc [E-utilities usage requirements](https://www.ncbi.nlm.nih.gov/books/NBK25497/) và [NCBI usage/API keys](https://eutilities.github.io/site/API_Key/usageandkey/); xác nhận mục đích discovery và lưu metadata nội bộ, cùng từng trường được phép giữ. Truy cập công khai không mặc nhiên cho phép phân phối lại hay sử dụng cho AI. |
| `network_approved` | Đồng ý rõ ràng cho đúng một pilot tối đa 20 bản ghi, query, thư mục đích và thời hạn đã xem. |
| `exclusive_provider_ip` | Xác nhận trong lúc pilot không có job NCBI khác dùng chung IP Internet, kể cả máy khác sau NAT. Local lock không điều phối được nhiều máy/tài khoản/container. Không xác nhận được thì dừng. |

Chỉ đổi từng cờ thành JSON boolean `true` sau khi điều kiện đó thực sự được đáp
ứng. Không dùng chuỗi `"true"` hoặc số `1`. Giữ `revoked=false` chỉ khi quyền
chưa bị thu hồi; không tự bật lại quyền bị thu hồi.

Đặt `valid_from` và `valid_until` theo đồng hồ thực, múi giờ
Asia/Ho_Chi_Minh (UTC+07:00). Mẫu cố định đã hết hiệu lực lúc 00:00 ngày
26/11/2026 UTC+07. Đoạn PowerShell sau chỉ chuẩn bị cửa sổ một giờ nếu
cửa sổ hiện tại không còn hiệu lực; giữ nguyên mọi trường và cờ phê duyệt khác.
Chạy sau khi đã kiểm tra file hiện có, trước khi xin xác nhận pilot. Không dùng
để gia hạn một run đang chạy hoặc tự gia hạn quyền đã được duyệt:

```powershell
$ErrorActionPreference = 'Stop'
$approvalPath = (Resolve-Path -LiteralPath 'data/operator/pubmed-approval.json').Path
$approvalBytes = [IO.File]::ReadAllBytes($approvalPath)
$approvalValue = [Text.Encoding]::UTF8.GetString($approvalBytes) | ConvertFrom-Json
$vietnamZone = [TimeZoneInfo]::FindSystemTimeZoneById('SE Asia Standard Time')
$pilotNow = [TimeZoneInfo]::ConvertTime([DateTimeOffset]::UtcNow, $vietnamZone)
$pilotStart = [DateTimeOffset]::Parse($approvalValue.valid_from)
$pilotEnd = [DateTimeOffset]::Parse($approvalValue.valid_until)
if ($pilotNow -lt $pilotStart -or $pilotNow -ge $pilotEnd) {
    $backupPath = $approvalPath + '.before-' + [guid]::NewGuid() + '.json'
    $approvalValue.valid_from = $pilotNow.ToString('yyyy-MM-ddTHH:mm:sszzz')
    $approvalValue.valid_until = $pilotNow.AddHours(1).ToString('yyyy-MM-ddTHH:mm:sszzz')
    $pendingPath = $approvalPath + '.pending-' + [guid]::NewGuid()
    $utf8 = New-Object Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($pendingPath, ($approvalValue | ConvertTo-Json -Depth 10), $utf8)
    [IO.File]::Replace($pendingPath, $approvalPath, $backupPath)
}
python -m medical_data_crawler.pubmed_cli validate-approval --approval $approvalPath
```

Windows dùng ID `SE Asia Standard Time` cho UTC+07, tương ứng giờ Việt Nam.
Khoảng hiệu lực gồm mốc đầu, không gồm mốc cuối. Bản sao lưu giữ byte file cũ
trong thư mục local đã ignore. Nếu ba cờ còn `false`, kết quả đúng vẫn là
`not_authorized`; việc cập nhật thời gian không cấp quyền.
Kiểm tra đồng hồ hệ thống, quyền đọc/ghi thư mục, bảo vệ file/state bằng ACL.
Validator không chứng minh người sửa file có thẩm quyền, quyền sử dụng nguồn,
khả năng ghi đích hay kết nối DNS/TLS.

Giữ đúng `profile_id=melanoma-v1` và query:

```text
"Melanoma"[MeSH Terms] AND "skin"[Title/Abstract]
```

`fields` là danh sách duy nhất gồm các tên trong mẫu; bắt buộc có `pmid`.
Các trường khác có thể bỏ sau review. Không thêm abstract hoặc nội dung bài.
`operations` phải đúng `['discover_metadata', 'retain_metadata']` theo thứ tự
(trong JSON dùng dấu nháy kép). Đích tương đối tính từ thư mục đang chạy.

## 2. Kiểm tra và xem trước — không gọi Internet

```powershell
python -m medical_data_crawler.pubmed_cli validate-approval --approval data/operator/pubmed-approval.json
python -m medical_data_crawler.pubmed_cli profiles
python -m medical_data_crawler.pubmed_cli preview --profile melanoma-v1 --limit 20
python -m medical_data_crawler.pubmed_cli demo
```

`validate-approval` chỉ đọc file, không tạo output, không đọc API key, không tạo
transport và không cấp quyền. Kết quả không in giá trị cấu hình hay tên key lạ:

| Status / exit code | Ý nghĩa |
|---|---|
| `invalid_configuration` / 2 | Cấu hình sai; sửa theo `issues`. |
| `not_authorized` / 1 | Cấu trúc hợp lệ nhưng thiếu xác nhận, chưa đến giờ, hết hạn hoặc bị thu hồi. |
| `ready` / 0 | Cấu hình sẵn sàng tại lúc kiểm tra; vẫn cần operator chủ động cho chạy. Pilot đọc lại gate độc lập. |

## 3. Kế hoạch pilot để operator duyệt

| Mục | Giới hạn |
|---|---|
| Provider | NCBI PubMed |
| Profile | `melanoma-v1` |
| Mục tiêu | Tối đa 20 bản ghi thư mục thật |
| Thao tác | `discover_metadata`, `retain_metadata` |
| API key | Không cần; không cần email cho demo |
| Worker | 1, không chạy song song |
| Tốc độ cấu hình | Tối đa 3 requests/giây, giãn cách đều, quota không key phải được operator đối chiếu hướng dẫn NCBI hiện hành |
| Request | ESearch một lần; ESummary theo lô tối đa 20 ID; retry hữu hạn theo transport |
| Output | `data/pubmed-live-pilot/` |
| Abstract/PDF/toàn văn | 0 |
| Thời hạn / IP | Theo file đã duyệt; độc quyền IP egress trong cửa sổ chạy |

Phiên này chưa truy cập Internet để kiểm chứng điều khoản hiện hành hay response
thật. Nếu bất kỳ điều kiện nào còn thiếu, giữ **READY FOR OPERATOR REVIEW**.

## 4. Chạy một lần sau khi có phê duyệt rõ ràng

Chỉ sau khi operator hoàn tất review và validator báo `ready`:

```powershell
python -m medical_data_crawler.pubmed_cli pilot --approval data/operator/pubmed-approval.json --enable-network --limit 20
```

Đây là lệnh gọi mạng thật. Không dùng trong pytest/CI. Không chạy lại nhiều lần
để thử vận may, không tăng lên 50 hoặc chạy bulk. Nếu muốn agent chạy thay,
cần xác nhận riêng ba điều kiện trên và cho phép đúng một pilot này.

## 5. Đọc kết quả và nơi lưu

Thay `RUN_ID` bằng ID thực tế CLI trả về:

```powershell
python -m medical_data_crawler.pubmed_cli report --approval data/operator/pubmed-approval.json --run-id RUN_ID
python -m medical_data_crawler.pubmed_cli inspect --approval data/operator/pubmed-approval.json
```

Hai lệnh này không gọi mạng và vẫn yêu cầu quyền hiện hành. Kiểm tra
`network_mode=live`, `status=complete`, `integrity=pass`, `full_text_downloads=0`
và `renditions=0`. `provider_total` là tổng PubMed báo; `found` là số PMID trong
pilot; `accepted` là số mới giữ, `already_known` là số đã biết khi bắt đầu,
`rejected` là số chưa giữ được. Đọc cả `issues`, không suy thành công từ exit
code đơn lẻ. PMID và provenance nằm trong observations và snapshot.

Metadata thật, nếu pilot thành công, nằm ở:

```text
data/pubmed-live-pilot/catalog/catalog.sqlite3
data/pubmed-live-pilot/runs/<run_id>/snapshot.json
data/pubmed-live-pilot/runs/<run_id>/checkpoint.json
data/pubmed-live-pilot/runs/<run_id>/cursor.key
data/pubmed-live-pilot/runs/<run_id>/report.json
```

Demo nằm riêng ở `data/secure-api-demo/catalog/catalog.sqlite3` và
`data/secure-api-demo/report.json`. Đây là dữ liệu tổng hợp; không dùng làm bằng
chứng đã lấy PubMed thật. Demo hai lần vẫn 2 document, 16 observations,
0 rendition, 0 request mạng. `rejected=1` là tình huống thu hồi quyền giả lập.
Report của `run_pilot` phân biệt `live`/`simulated` bằng `network_mode`.

## 6. Lỗi thường gặp và phục hồi

| Mã chẩn đoán | Cách xử lý |
|---|---|
| `approval_missing` / `approval_unavailable` | Tạo file từ mẫu hoặc sửa quyền đọc/đường dẫn. |
| `invalid_json_or_unreadable` | Kiểm tra UTF-8, cú pháp JSON, key trùng, kích thước tối đa 1 MiB và quyền đọc; không dán bí mật vào log. |
| `invalid_schema`, `missing_keys`, `unexpected_keys` | So lại mẫu, không thêm key/email/API key vào approval. |
| `invalid_identifier` / `invalid_profile` / `query_binding_mismatch` | Dùng ID hợp lệ, profile có sẵn và chép đúng query từ `profiles`. |
| `invalid_fields` / `invalid_operations` / `invalid_boolean` | Dùng đúng tên trường, không lặp, đúng hai thao tác, boolean JSON. |
| `invalid_validity_interval` | Hai ngày phải có múi giờ và mốc cuối lớn hơn mốc đầu. |
| `approval_not_yet_valid` / `approval_expired` | Kiểm tra đồng hồ; operator review lại thời hạn, không sửa clock để vượt gate. |
| `permission_revoked` | Dừng; chỉ operator quyết định cấp quyền mới. |
| `source_terms_not_reviewed`, `network_not_approved`, `shared_ip_uncoordinated` | Hoàn tất review tương ứng; không tự đặt cờ. |
| `invalid_output_directory` | Dùng đích thư mục hợp lệ, không dùng file hoặc tên dành riêng của Windows. |
| `approval_changed_or_invalid` | File thay đổi trong lúc kiểm tra hoặc reader từ chối; kiểm tra lại file ổn định. |

Pilot vẫn giữ mã lỗi bảo mật hiện có, gồm `invalid_operator_approval`,
`permission_expired`, `rate_limited`, `response_timeout`, `tls_failure`,
`unsafe_address`, `response_profile_mismatch`. Khi gặp lỗi approval, chạy
`validate-approval` để biết chi tiết. Khi gặp lỗi response/TLS/DNS, giữ nguyên
evidence và báo mã lỗi; không tắt TLS hay nới kiểm tra schema/địa chỉ.
Nếu chưa tạo run ID, không có checkpoint để resume.

Nếu run đã ghim và quyền/binding còn hợp lệ, sau khi xử lý nguyên nhân lỗi:

```powershell
python -m medical_data_crawler.pubmed_cli pilot --approval data/operator/pubmed-approval.json --enable-network --resume RUN_ID
```

Resume không tìm lại ESearch; không sửa snapshot/cursor/key. Nếu đổi thời hạn
làm binding đổi, cần review và lập run mới. Không xóa dữ liệu gốc để thử lại.

## 7. Bằng chứng và bước tiếp theo

Chưa có run thật, chưa kiểm chứng envelope ESearch/ESummary, header/content type,
ngày xuất bản, DNS/TLS hay quota trên dịch vụ thật. Không thu thập abstract,
PDF, XML toàn bài, full text hoặc dữ liệu phục vụ embedding trong phiên này.
Trước mở rộng: hoàn tất pilot được duyệt, kiểm tra PMID/provenance/chất lượng
metadata, báo cáo lỗi tương thích thật nếu có, rồi review quota bền vững và
checkpoint. Chưa chuyển sang Crossref hay mở rộng crawling.

Kiểm thử ngày 25/11/2026: baseline **755 passed, 2 skipped**; validation cuối
**796 passed, 2 skipped** (41 test mới), chạy với
`python -m pytest -q --basetemp data/pytest-session06d1p-final2`.
Hai skip là giới hạn quyền symlink trên Windows. Pytest cần thư mục tạm mới
riêng dưới `data/` vì temp mặc định gặp lỗi ACL `WinError 5`.
`python -m ruff check .` còn 3.171 lỗi ở dependency local có sẵn dưới
`docs/data/`; `python -m ruff format --check .` báo 249 file cần format tại đó.
Không sửa các thư viện này. Cả `python -m ruff check src tests scripts` và
`python -m ruff format --check src tests scripts` đều đạt (82 file).
Lint toàn workspace khi loại `docs/data/` cũng đạt:
`python -m ruff check . --extend-exclude docs/data` và
`python -m ruff format --check . --exclude docs/data`.
