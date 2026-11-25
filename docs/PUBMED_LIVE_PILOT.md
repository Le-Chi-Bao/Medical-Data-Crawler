# Thử PubMed metadata có kiểm soát

Phiên 06D.1 bổ sung lệnh tìm PubMed công khai và lưu thông tin thư mục vào SQLite.
Không cần API key, tài liệu bệnh viện, thuê bao trả phí hoặc PDF có sẵn. **Chưa chạy
pilot thật trong phiên lập trình**; toàn bộ kết quả kiểm thử là dữ liệu tổng hợp.

Metadata là PMID, DOI/PMCID khi có, tiêu đề, tác giả, tạp chí, ngày xuất bản và
publication type. Không tải abstract, PDF, XML bài báo hay truy cập link publisher.
PMCID/OA không phải quyền tải bài. Chương trình không có RAG, embeddings hoặc chẩn đoán.

## Cài đặt và xem trước

Tại root repo, dùng Python 3.11 hoặc 3.12 và PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e '.[dev]'
python -m medical_data_crawler.pubmed_cli --help
python -m medical_data_crawler.pubmed_cli profiles
python -m medical_data_crawler.pubmed_cli preview --profile melanoma-v1 --limit 20
python -m medical_data_crawler.pubmed_cli demo
```

`profiles`, `preview`, `demo` không gọi Internet. Hai profile là `melanoma-v1`
và `skin-lesions-v1`; query là cấu hình ứng dụng để reviewer xem xét trong phạm vi
tổn thương da K01–K08. Tên profile không tự phê duyệt quyền nguồn. CLI không nhận
query/URL tự do cho live. Demo có thể chạy lại; output dưới `data/secure-api-demo/`.

## File phê duyệt của người vận hành

Operator là người có quyền quyết định được dùng nguồn, trường nào được lưu và
lưu vào đâu. Chỉ operator được sửa file phê duyệt và dữ liệu local. Request tìm
kiếm không được làm file cấp quyền. Không đưa file local này lên Git.

Tạo thư mục `data/operator/`, lưu JSON sau thành
`data/operator/pubmed-approval.json`. `data/` được ignore. Đây là **mẫu đang chặn
live**, không phải phê duyệt nguồn thật:

```json
{
  "approval_id": "pubmed-metadata-review-01",
  "domain_id": "public-medical-metadata",
  "profile_id": "melanoma-v1",
  "approved_query": "\"Melanoma\"[MeSH Terms] AND \"skin\"[Title/Abstract]",
  "fields": ["pmid", "doi", "pmcid", "title", "authors", "journal", "published_on", "publication_type", "category", "status"],
  "valid_from": "2026-11-25T00:00:00+07:00",
  "valid_until": "2026-11-26T00:00:00+07:00",
  "operations": ["discover_metadata", "retain_metadata"],
  "revoked": false,
  "source_terms_reviewed": false,
  "network_approved": false,
  "exclusive_provider_ip": false,
  "output_dir": "data/pubmed-live-pilot"
}
```

Trước khi đổi ba cờ cuối sang `true`, operator phải:

1. Đọc [điều kiện E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25497/) và
   [hướng dẫn quota NCBI](https://eutilities.github.io/site/API_Key/usageandkey/),
   xác nhận chỉ discovery và lưu metadata nội bộ là phù hợp.
2. Xem query bằng `profiles`, chọn đúng profile và chép query chính xác. Chọn
   các trường được giữ; `pmid` bắt buộc. Không có trường abstract/full text.
3. Đặt thời hạn ngắn theo ngày chạy, múi giờ tường minh và đích output được quản lý.
4. Xác nhận không có chương trình/máy khác gọi NCBI sau cùng IP Internet trong lúc
   pilot. Nếu có NAT dùng chung không điều phối được thì chưa đủ điều kiện chạy.

Không key mặc định tối đa 3 requests/giây, một worker. Local OS lock chặn process
live thứ hai trong cùng tài khoản/temp namespace; không thay được điều phối
nhiều tài khoản hoặc nhiều máy. Không đặt
`exclusive_provider_ip=true` nếu chưa đáp ứng điều kiện đó.

Email liên hệ tùy chọn dùng `$env:MDC_NCBI_EMAIL` trong phiên PowerShell local;
không cần cho demo hoặc luồng không key cơ bản. Key tùy chọn có thể cấp qua
`MDC_NCBI_API_KEY`; không ghi key/email vào file repo, command URL hay report.
CLI vẫn giữ ceiling bảo thủ 3 kể cả có key. Không cần tạo key để dùng phiên này.

## Lệnh pilot 20 bản ghi

Sau khi operator hoàn tất review và cập nhật file phê duyệt:

```powershell
python -m medical_data_crawler.pubmed_cli pilot --approval data/operator/pubmed-approval.json --enable-network --limit 20
```

Đây là lệnh **có gọi Internet thật**. Bỏ `--enable-network` sẽ bị chặn. Mặc định
20, tối đa 50; không có worker song song, tự động mở rộng hoặc thu hoạch toàn bộ.
Chỉ hai endpoint ESearch/ESummary của NCBI được truy cập. Mọi redirect bị từ chối.

ESearch trả một danh sách PMID; chương trình giữ đúng thứ tự nguồn, kiểm tra đủ
ID của cửa sổ được yêu cầu rồi ghim lại cho run đó. Các trang ESummary chỉ dùng
ID đã ghim. Nếu PubMed có nhiều kết quả hơn limit, report ghi `limited=true`.
`provider_total` là tổng nguồn báo, `found` chỉ là số được chọn trong pilot.
Không coi prefix 20 ID là toàn bộ kết quả hay tự vượt cửa sổ 10.000 của PubMed.

Report có `run_id`, `accepted` (mới giữ trong run), `already_known` (đã có lúc
bắt đầu), `rejected`, `issues` và `integrity`. `complete` nghĩa xử lý đủ **tập đã
chọn**, không có nghĩa tìm hết PubMed hoặc dữ liệu y khoa đã được kiểm chứng.

## Đọc kết quả và phục hồi

```text
data/pubmed-live-pilot/
  catalog/catalog.sqlite3
  runs/<run_id>/snapshot.json
  runs/<run_id>/cursor.key
  runs/<run_id>/checkpoint.json
  runs/<run_id>/report.json
```

Snapshot giữ PMID, query công khai được duyệt, tổng kết quả và thời gian. Khóa
cursor là khóa local, phải bảo vệ cùng state. Không có original, PDF hay rendition
được tạo bởi pilot này. SQLite observation giữ provider, nguồn trường, thời gian,
mapping version, fingerprint snapshot và approval reference. Trường thiếu giữ
`null`/không tạo identifier; không suy đoán DOI hoặc gộp bài chỉ vì cùng title.

Thay `RUN_ID` bằng giá trị report vừa in:

```powershell
python -m medical_data_crawler.pubmed_cli report --approval data/operator/pubmed-approval.json --run-id RUN_ID
python -m medical_data_crawler.pubmed_cli inspect --approval data/operator/pubmed-approval.json
python -m medical_data_crawler.pubmed_cli pilot --approval data/operator/pubmed-approval.json --enable-network --resume RUN_ID
```

`inspect` liệt kê tối đa 100 document và 1.000 observations trong miền đã duyệt;
`documents_listed` là số hiển thị, không phải count toàn database khi vượt giới
hạn. Count pilot chính xác nằm trong report. Cả report/inspect đều không gọi mạng.
Không cho phép inspect khi quyền hiện hành bị thu hồi/hết hạn.

Khi trang lỗi, cursor không tiến; resume replay trang đó và giữ item tốt đã commit.
Không chạy lại ESearch khi resume. Run đã complete resume không gọi mạng. Run mới
có thể thấy cùng PMID và metadata đã cập nhật: giữ document cũ, thêm observations
có evidence mới, không ghi đè khẳng định cũ. Không cam kết một observation duy nhất
xuyên các snapshot khác nhau.

`permission_expired`: xin review thời hạn mới và lập run mới nếu binding đổi.
`permission_revoked`: dừng, không tự bật lại. Operator có thể đặt `revoked=true`
bằng atomic replace để chặn lượt tiếp theo và commit chưa công bố. `rate_limited`/
`provider_unavailable`/`response_timeout`: chương trình đã retry hữu hạn; kiểm tra
quota/mạng rồi resume khi được phép. `response_profile_mismatch`, `invalid_headers`,
`content_type_denied`, `tls_failure`, `unsafe_address`: dừng để kiểm tra response,
CA/DNS hoặc contract; không bỏ xác minh TLS hay nới allowlist cho chạy qua.
Checkpoint thiếu/sai thì fail closed; giữ dữ liệu và chạy run mới, không tự sửa
snapshot hoặc cursor. Không chạy hai CLI vào cùng state.

## Mức sẵn sàng và hướng tiếp theo

Đã triển khai đường live có bật tường minh và kiểm thử offline, gồm lỗi bảo mật
và resume. Chưa xác minh DNS/TLS/POST/content-type/shape với NCBI thật, quyền
nguồn thật hay chất lượng corpus; không có test external-service nào được chạy.
Pilot nhỏ sau phê duyệt riêng là bước xác minh tiếp theo, có thể gặp drift phải
sửa theo bằng chứng thực. Xem [giới hạn bảo mật](SECURE_API_TRANSPORT.md).

Sau pilot, ưu tiên ledger/checkpoint và quota bền vững trước khi tăng lượng thu
thập. Các phiên discovery tương lai có thể review Crossref (DOI), Europe PMC/PMC
(liên kết metadata và quyền theo bài), OpenAlex (làm giàu định danh). Các connector
đó chưa được triển khai; toàn văn và JATS cần phiên phê duyệt riêng.
