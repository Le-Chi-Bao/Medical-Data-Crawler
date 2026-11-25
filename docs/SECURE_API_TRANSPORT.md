# Secure metadata API transport · Session 06D.1

Hệ thống có transport HTTPS cho metadata PubMed, gate quyền theo thao tác và
pilot tối đa 50 bản ghi. Mạng vẫn tắt mặc định. Phiên triển khai chỉ dùng HTTP
giả lập; chưa xác nhận kết nối PubMed thật. Cách dùng cho người mới nằm trong
[PUBMED_LIVE_PILOT.md](PUBMED_LIVE_PILOT.md).

## Kiến trúc và cấu hình

```text
File phê duyệt do operator quản lý + --enable-network
  → FileDecisionProvider / OperationPolicyGate
  → SecureMetadataTransport.exchange(endpoint, parameters, max_bytes)
  → DNS công khai → IP ghim → TLS xác minh → HTTP POST giới hạn
  → ESearch: ghim một tập PMID trong thứ tự nguồn
  → ESummary: chỉ đọc tập PMID đã ghim
  → mapper 06C.3, lọc trường và giữ evidence
  → CatalogDiscoveryWriter → kiểm tra quyền ngay trước SQLite commit
```

`api_transport.py` thực thi `MetadataTransport`. `APISettings.enabled=False`
là mặc định. Các dependency được cấp vào như wire/resolver/clock/budget là
ranh giới **tin cậy của operator**, phục vụ kiểm thử ngoại tuyến; không lấy từ
request người dùng. Không có network I/O lúc import. Primitive TLS và hàm kiểm
tra IP từ 06A được dùng lại; GET tài liệu cũ giữ nguyên hợp đồng.

Mặc định: connect 5 giây, read 10 giây, mỗi attempt 20 giây, toàn exchange
60 giây gồm DNS, chờ quota, retry và backoff. Tối đa 2 retry, tức 3 attempt.
Giới hạn response nén và giải nén đều tối đa 256 KiB; caller có thể giảm quota.
Deadline này áp cho từng exchange, không phải một transaction mạng cho cả job.
Một pilot mới cần một ESearch và các ESummary theo lô 20 ID. Không chạy song song.

## Ranh giới quyền

Các thao tác độc lập là `discover_metadata`, `retain_metadata`, `fetch_document`,
`store_original`, `extract_content`, `export_data`, `ai_use`. Quyền bind chính xác
domain, source, operation, purpose, resource, profile, policy version và khoảng
hiệu lực `[valid_from, valid_until)`. Resource là fingerprint permit, gồm cả query,
field allowlist và thời hạn. Một grant discovery không thể dùng cho retention
hay bất kỳ thao tác nào khác.

`OperatorPolicyAuthority` nhận các grant tin cậy riêng với request và hỗ trợ
revoke trong tiến trình. Có thể inject `DecisionProvider` độc lập. CLI dùng
`FileDecisionProvider`, đọc lại file operator trước mỗi exchange, trước gửi request,
sau response và trước từng item commit. Đổi binding/đích output, thiếu file, hết
hạn, revoke hoặc lỗi provider đều đóng gate. Đặt `revoked=true` tồn tại qua restart.
File mẫu không chứa quyết định được bật sẵn; CLI không tạo phê duyệt từ query.

Writer kiểm tra quyền trước ghi và qua callback **bên trong giao dịch**, sau khi
ghi các row nhưng trước SQLite commit. Lỗi gate rollback toàn item; các item đã
commit hợp lệ trước đó được giữ nguyên. Thu hồi không tự xóa dữ liệu lịch sử.

Đây chưa phải xác thực người dùng/RBAC. Operator quản lý ACL cho file cấu hình,
database, checkpoint, khóa cursor, temp và process. Người có quyền sửa cấu hình
hoặc gọi trực tiếp primitive Python nằm trong trust boundary. Update file nên
dùng atomic replace. Quyết định từ file và SQLite commit không có transaction
phân tán: vẫn có khoảng đua rất ngắn sau lần kiểm tra cuối. Muốn thu hồi tuyến
tính qua nhiều dịch vụ cần authority/fencing khác ở 06E. Không có đường full text
mới; các gateway legacy tiếp tục theo chính sách riêng, không nhận permit mới này.

## Bảo vệ mạng và response

- Chỉ hai URL HTTPS chính xác tại `eutils.ncbi.nlm.nih.gov`: ESearch, ESummary.
  Từ chối port, userinfo, fragment, query gắn sẵn, EFetch và endpoint khác.
- Tham số cố định `db=pubmed`, JSON, `sort=pub_date` hoặc summary `version=2.0`.
  Query phải khớp permit; offset/page size/PMID có kiểu và giới hạn. Không nhận
  `url`, `api_key`, `email`, `tool` từ caller hay URL trong response.
  ESummary phải nằm trong inventory đã bind bởi capture/connector tin cậy; request
  không được tự mở rộng tập PMID. Một transport không đổi sang inventory khác.
- Tất cả DNS answers phải thuộc tập địa chỉ công khai được 06A hỗ trợ. Kết nối
  trực tiếp IP đã kiểm tra, đối chiếu peer IP, TLS SNI/hostname dùng host gốc;
  không resolve hostname lần nữa khi connect. Retry resolve và kiểm tra lại.
  DNS hệ thống chạy trong tối đa 4 daemon threads để caller không mắc kẹt vượt
  deadline; DNS bị treo có thể chiếm slot và làm các yêu cầu sau fail closed.
- CA bundle `certifi`, `CERT_REQUIRED`, hostname verification và TLS tối thiểu
  1.2. Không dùng proxy, CA override hay TLS key logging từ environment.
- Từ chối mọi redirect, kể cả cùng host. Không chuyển tiếp credential sang đích khác.
- Chỉ JSON content type. Header bị lỗi, trùng framing, folding/control characters,
  range response, encoding không hỗ trợ và quota header vượt giới hạn bị chặn.
  Đọc có Content-Length, chunked hoặc close-delimited với byte budget trong lúc đọc.
- Hỗ trợ identity/gzip; giải nén bằng quota output hữu hạn, kiểm tra EOF/CRC, từ
  chối gzip bị cắt, stream nối tiếp và dữ liệu thừa. Không lưu payload HTTP thô.
- Parser JSON 06C.3 tiếp tục chặn key trùng, nonfinite, XML, response sai profile,
  PMID/summary mâu thuẫn. Không tải DTD, entity hay link publisher.

## Quota, retry và secret

Không key: tối đa 3 request/giây. Có key do operator cấp: ceiling cấu hình tối đa
10; mặc định vẫn là 3, có thể chọn `requests_per_second=10` trong ứng dụng tin cậy.
Đây là ceiling bảo thủ; code chỉ kiểm tra định dạng key, không chứng thực key
trước với NCBI. Key sai nhận lỗi và không tự tăng quota.

Các transport dùng một `ProviderBudget` chung trong process; ceiling thấp nhất
đã đăng ký thắng đến lúc restart. Khoảng cách đều, không burst. Live exchange được
serialize giữa các thread. OS file lock cố định chỉ cho **một process live trong
cùng tài khoản/temp namespace**, không có tham số đổi tên lock trong CLI. Process
fork kế thừa bị chặn.
Lock được giữ đến khi process thoát; file còn lại không đồng nghĩa lock còn giữ.

Local lock không điều phối các máy khác sau cùng NAT. Live chỉ được bật khi operator
xác nhận `exclusive_provider_ip=true`: không có job NCBI khác dùng chung IP egress.
Không đáp ứng điều này thì chưa được chạy live; cần coordinator theo IP trước.
Temp namespace khác nhau/container khác nhau cũng cần điều phối bên ngoài.

`429` và `500/502/503/504` retry với exponential backoff hữu hạn, jitter và
`Retry-After` (số giây hoặc HTTP date). Cooldown được chia sẻ trong process.
Delay vượt deadline làm dừng, không cắt ngắn Retry-After rồi gửi sớm.
Timeout/connection interrupted có retry giới hạn; TLS, quyền, redirect, schema,
header và quota lỗi là terminal. Sau exhaustion trả mã cố định.

Key/email tùy chọn chỉ lấy từ cấu hình tin cậy hoặc environment cục bộ, giữ trong
RAM và gửi form POST qua TLS. Không nằm trong URL, repr settings, SQLite, report
hoặc log của chương trình. Không ghi raw exception/body. Debugger, process dump,
phần mềm giám sát ngoài ứng dụng vẫn thuộc trách nhiệm operator.

Hướng dẫn NCBI được đối chiếu ngày 25/11/2026: 3 requests/giây không key, mặc định
10 với key; ưu tiên batching, job lớn cuối tuần hoặc 21:00–05:00 giờ Eastern.
Thông tin tool/email cần phù hợp và phải đăng ký với NCBI trong quy trình khôi
phục truy cập bị chặn. Phiên này không đăng ký hay gửi email.
[NCBI usage/API keys](https://eutilities.github.io/site/API_Key/usageandkey/)

## Snapshot live và khả năng tái lập

Snapshot replay cũ vẫn dùng PMID giảm dần, giữ nguyên fingerprint/HMAC. Snapshot
live có `sort=provider-pub-date`, `total_results`, `captured_at` và inventory theo
đúng thứ tự ESearch. Không tự sort/deduplicate. Một response duy nhất ghim prefix
được yêu cầu: mặc định 20, tối đa 50. Số ID phải đúng `min(provider_total, limit)`;
retstart/retmax/ID, warning/error và tính duy nhất đều được kiểm tra trước công bố.

`provider_total` có thể lớn hơn 10.000 nhưng pilot chỉ lấy prefix đã yêu cầu,
report ghi `limited=true`; không tuyên bố đã ghim toàn bộ search. Transport chặn
request vượt cửa sổ ESearch 10.000, không phân hoạch query hoặc thu hoạch phần còn
lại. [Giới hạn ESearch của NLM](https://www.nlm.nih.gov/pubs/techbull/so22/so22_updated_pubmed_e_utilities.html)

ESummary chỉ dùng pinned IDs, giữ thứ tự inventory dù response đổi thứ tự.
Checkpoint/HMAC giữ binding snapshot, permit, page size, profile và mapping.
Chỉ tiến cursor sau trang commit đủ; trang lỗi được replay, item tốt đã ghi dùng
lại. Snapshot/signing key không ghi đè. Resume không chạy lại ESearch. Mất checkpoint
hoặc mismatch thì dừng; có thể lập run mới theo cùng phê duyệt còn hiệu lực.

Danh sách ID ổn định không có nghĩa metadata ở nhiều ESummary là snapshot cùng
thời điểm: nguồn có thể sửa metadata giữa các request. Mỗi observation có evidence
và thời gian riêng. Một lần chạy mới có snapshot/evidence mới, có thể thêm observation
cho cùng giá trị; document/source-item/identifier không nhân bản. Chưa tự gộp claim
liên run hay xác nhận withdrawal khi PMID vắng.

## Kiểm thử, demo và giới hạn trước live

```powershell
python scripts/demo_secure_api_transport.py
python scripts/demo_secure_api_transport.py
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

Demo lưu dưới `data/secure-api-demo/`: 2 document, 16 observations, 2 retry giả,
1 yêu cầu công bố bị thu hồi, 5 thao tác khác bị từ chối, 0 rendition, 0 network
requests. Hai lần chạy giữ cùng report/state. `accepted` là số item được xử lý
hợp lệ trong lượt, `already_known` là số item của lượt replay; yêu cầu bị revoke
được đếm riêng trong `rejected`, không phải một document mới.

Suite chặn socket/DNS; subprocess demo cũng có guard. Fault injection bao phủ
endpoint/query, SSRF/rebinding/peer mismatch, TLS cert/hostname failure, header,
gzip bomb, byte quota, deadline, 429/date Retry-After, 5xx exhaustion, interrupted
body, expiry/revoke, retention, miền, resume và rollback sau revoke trong transaction.
OS lock được kiểm tra bằng hai process thật, không gọi mạng. Test TLS dùng socket
giả để xác nhận cấu hình xác minh và inject lỗi; chưa đo handshake với NCBI thật.

Trước pilot: operator review terms/fields/query/output, phê duyệt thời hạn ngắn,
xác nhận egress độc quyền, ACL state/approval, clock/CA và môi trường DNS/TLS hoạt
động. Chạy tối đa 20 trước, đánh giá response thực tế, báo cáo drift và provenance.
Không suy ra pilot thành công từ fixture. Chưa có auth/RBAC doanh nghiệp, scheduler,
quota đa máy, kiểm tra chất lượng metadata corpus thật, abstract/full text/JATS,
export mới hoặc AI. Source approvals hiện hành và schema v0.1/v1 không đổi.

Validation ngày 25/11/2026, Python 3.12/Windows: **755 passed, 2 skipped**;
`python -m ruff check .` và `python -m ruff format --check .` đều đạt (80 file).
Baseline là 649 passed, 2 skipped; 106 test mới đạt. Hai skip legacy là
`test_internal_import.py:320` và `test_html_preflight.py:212`, do thiếu quyền
tạo symlink trên Windows. Không bỏ qua test nào vì dịch vụ ngoài: không có test
live và không chạy pilot. Demo hai lần cho cùng report như trên. Lượt pytest mặc
định ban đầu lỗi ACL temp; validation dùng `PYTEST_DEBUG_TEMPROOT` riêng dưới
`data/` hoặc `--basetemp` theo [DEVELOPMENT.md](DEVELOPMENT.md#kiểm-tra-trước-commit).
