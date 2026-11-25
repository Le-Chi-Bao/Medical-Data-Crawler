# PubMed metadata discovery · Session 06C.3

> Tài liệu này ghi thiết kế replay 06C.3. Session 06D.1 đã bổ sung
> [secure transport](SECURE_API_TRANSPORT.md) và [CLI pilot](PUBMED_LIVE_PILOT.md)
> có bật mạng tường minh, authority thu hồi quyền và snapshot theo thứ tự nguồn.
> Hành vi fixture/offline mô tả bên dưới vẫn được giữ tương thích.

Connector ngoại tuyến mô phỏng `ESearch → ESummary` với `db=pubmed`, JSON và
ESummary profile 2.0. Dữ liệu thư mục tổng hợp đi vào Medical Document Catalog
SQLite v1. Không thay schema catalog, Structured Raw v0.1, export manifest v0.1
hoặc identity của pipeline tiếp nhận hiện có.

## Kiến trúc và API

```text
DiscoveryRequest + trusted DiscoveryPermit + pinned SearchSnapshot
  → validate/authorize
  → injected MetadataTransport: fixed ESearch/ESummary endpoints
  → bounded JSON parser + response consistency checks
  → PubMedMetadataMapper: field policy + namespace normalization
  → CatalogDiscoveryWriter: domain check + per-item transaction
  → SanitizedDiscoveryReport + continuation cursor
```

`discovery.py` định nghĩa hợp đồng, allowlist và gate. `pubmed.py` xử lý API shape,
phân trang và mapping. `catalog/discovery.py` dùng `Catalog`/`DomainCatalog` hiện
có; không tạo đường ghi SQL riêng. Transport mặc định luôn báo `network_disabled`.
Ứng dụng tin cậy phải chủ động cấp transport; phiên này chỉ cung cấp replay fixture.
Không có HTTP client production mới, EFetch, ELink hay đường tải URL trả về.

Sau khi cài package theo README:

```python
from medical_data_crawler.catalog.discovery import CatalogDiscoveryWriter

# scope: DomainCatalog do operator chọn; connector: PubMedDiscoveryConnector
# request, permit, snapshot và transport được chuẩn bị độc lập bởi ứng dụng tin cậy.
outcome = CatalogDiscoveryWriter(scope, connector).run(request, permit)
consume_report(outcome.report)
# Chỉ dùng outcome.next_cursor sau khi trang đã được ghi thành công.
```

Ví dụ hoàn chỉnh, chạy được nằm trong
[`scripts/demo_pubmed_discovery.py`](../scripts/demo_pubmed_discovery.py).

## Quyền và ranh giới tin cậy

`DiscoveryRequest` không cấp quyền. `DiscoveryPermit` là đối tượng do operator
tin cậy tạo, không deserialize từ request của người gửi. Gate kiểm tra đồng thời:

- Source `pubmed`, domain và profile khớp request/snapshot.
- Query khớp chính xác profile đã duyệt; query snapshot khác rỗng, tối đa 512 byte
  UTF-8, không có ký tự điều khiển.
- Operation `discover_metadata`, purpose `internal_catalog_review` và phiên bản
  `pubmed-bibliography-v1`.
- Cả `allow_discovery` và `allow_retention` phải là `True`.
- Thời gian có múi giờ, trong khoảng `[valid_from, valid_until)`.
- Tập trường là `frozenset`, thuộc allowlist và có `pmid` để bảo toàn identity.

Quyền được kiểm tra trước/sau mỗi exchange và ngay trước mỗi item commit. Miền
được chọn phải khớp handle catalog trước khi gọi transport. Permit và snapshot
là cấu hình của tiến trình tin cậy; đây chưa phải xác thực người dùng, RBAC hay
dịch vụ thu hồi quyền. Policy reference chỉ giữ fingerprint và phiên bản; operator
cần giữ hồ sơ permit đã duyệt bên ngoài catalog để đối soát đầy đủ.

Discovery/lưu metadata không cấp quyền dùng abstract, đọc/lưu full text, extract,
phân phối hoặc AI. OA hint, DOI, PMCID và link không phải căn cứ cho các hành động
đó. Không tự tạo license grant hoặc `license_uri`.

## Allowlist theo trường

Mapping cố định: `pubmed-esummary-2.0-v1`. Policy: `pubmed-bibliography-v1`.
Permit có thể thu hẹp tập mặc định, không thể mở rộng nó.

| Trường catalog | Căn cứ ESummary | Xử lý |
| --- | --- | --- |
| `pmid` | `uid`, đối chiếu `articleids` loại `pubmed` | Native key bắt buộc, chuẩn hóa số nguyên dương |
| `doi` | `articleids` loại `doi` | Chuẩn hóa riêng namespace DOI |
| `pmcid` | `articleids` loại `pmc` | Chuẩn hóa `PMC` + số dương |
| `title` | `title` | Giữ chuỗi thư mục có giới hạn |
| `authors` | `authors[].name` | Chỉ giữ tên, không giữ affiliation/trường dư |
| `journal` | `fulljournalname` | Giữ tên venue do nguồn khai báo |
| `published_on` | `pubdate` | Giữ nguyên độ chính xác/chuỗi ngày nguồn |
| `publication_type` | `pubtype` | Mỗi loại là observation có căn cứ riêng |
| `category` | `pubtype` đã được phép lưu | Phân loại theo quy tắc bên dưới |
| `status` | `pubtype` đã được phép lưu | Chỉ unresolved review candidate |

Source attribution nằm ở `Source(provider=NCBI PubMed)`, `SourceItem` và evidence
trỏ profile/PMID/path. Trường thiếu title/journal/date ghi `None` khi được phép;
identifier thiếu không được dựng thay thế. `pubdate` là observation chuỗi, không
ép thành ngày ISO hoặc tạo Revision khi chưa đủ bằng chứng.

Abstract, full text, XML bài báo, PDF, OA flags, license hints, link publisher,
trường không biết và trường ngoài permit đều bị loại; `dropped_fields` đếm số
trường bị loại, không lặp tên hoặc giá trị của chúng vào report. Các trường dư
trong author/article identifier cũng bị loại. `idtypen` chỉ là discriminator
của envelope, không được lưu. Payload gốc chỉ tồn tại tạm trong bộ nhớ.

Chuỗi metadata tối đa 1.024 byte, tên tác giả 512 byte, publication type 128 byte;
tối đa 64 tác giả, 32 article identifiers và 32 publication types mỗi record.
Catalog tiếp tục áp giới hạn metadata JSON 16 KiB. Record vượt hạn bị cô lập.

## Category và correction/retraction

Chỉ `Systematic Review` tường minh trong publication type mới suy ra
`systematic_reviews`. `Journal Article` và không có `Review` suy ra
`research_papers`. Generic `Review` hoặc thiếu type giữ `unknown`; keyword trong
title/query không dùng để phân loại. Khi `publication_type` không được phép lưu,
không tạo category/status dẫn xuất. Category đã biết luôn có evidence `path=pubtype`.
Scope K01–K08 và audience giữ `unknown`.

`Published Erratum`, `Retraction of Publication`, `Retracted Publication`,
`Expression of Concern` và `Corrected and Republished Article` tạo observation
`status=unresolved_review_candidate: <publication type>` khi permit cho phép.
Profile JSON này không có hợp đồng đã xác minh cho endpoint/hướng quan hệ thông
báo. Vì vậy không tạo `corrects`/`retracts`, kể cả khi hai PMID đã có trong catalog;
không đoán từ title, thứ tự trang hay trường `related` chưa duyệt. Không đổi clinical
reliability hoặc giả lập withdrawal. Tích hợp quan hệ có hướng cần một profile
nguồn chứng cứ được review riêng. Fixture bao phủ correction, notice rút bài và
bài có type `Retracted Publication`; test chặn suy diễn quan hệ.

## Phân trang và identity

`SearchSnapshot` ghim toàn bộ PMID tổng hợp, duy nhất và giảm dần theo số. Đây là
quy ước replay cục bộ; API request dùng `sort=pub_date`. Fixture được tạo để đáp ứng
cả thứ tự đã ghim và ngày tổng hợp. Không giả định hai lần search trực tiếp có thứ
tự giống nhau. Mỗi trang phải khớp chính xác inventory snapshot; không tự sort lại
một response sai hoặc bỏ PMID lặp.

Page size từ 1 đến 100, `retstart` bắt đầu từ 0, `retmax` request là page size;
response `retmax` phải bằng số mục thực sự trả, gồm trang cuối ngắn hoặc rỗng.
Count phải khớp snapshot. ESummary có thể trả thứ tự khác; kết quả mapping luôn
theo ESearch đã ghim. Thiếu summary tạo issue theo index; dư/trùng UID, thiếu key
hoặc count/order sai tạo lỗi có kiểm soát. Không âm thầm tiến qua dữ liệu thiếu.

Cursor dạng `offset.HMAC-SHA256` ràng buộc snapshot fingerprint, domain, page size,
permit fingerprint, profile và mapping version. Key do operator cung cấp, tối
thiểu 32 byte; demo/test dùng key công khai tổng hợp, không phải credential thật.
Cùng cấu hình/key cho cursor xác định qua restart. Đổi key/permit/snapshot làm
cursor cũ không hợp lệ. Cursor không chứa query, không cấp quyền và không thay
checkpoint bền vững. Khi có lỗi item, writer không phát cursor tiếp theo; chạy lại
cùng request/cursor đầu trang sau khi xử lý lỗi.

PubMed ESearch chỉ truy hồi cửa sổ đầu 10.000 kết quả. Count lớn hơn 10.000 bị
chặn `retrieval_window_exceeded`; snapshot cũng không thể chứa quá 10.000 PMID.
Không tự phân hoạch query hoặc thu hoạch lớn. Contract test đi hết 100 trang,
mỗi trang 100 mục đến đúng biên 10.000; cũng kiểm tra trang cuối ngắn và search rỗng.
[Tham số và giới hạn ESearch/ESummary của NCBI](https://www.ncbi.nlm.nih.gov/books/NBK25499/)

Local ID băm domain + source `pubmed` + loại thực thể + PMID. DOI/PMCID/PMID có
namespace riêng. Không gộp document theo title, DOI hint, tác giả, ngày hoặc URL.
PMID đã thuộc document khác tạo `identity_conflict`. DOI/PMCID đã có chủ được
giữ như observation trên item mới, không đổi ownership hoặc tự merge.

## Persistence, provenance và lỗi một phần

Mỗi item tạo/replay `PolicyReference`, `Source`, `Document`, `SourceItem`,
`Identifier` và `Observation` bằng `DomainCatalog.write()` trong một giao dịch
có giới hạn. Không tạo `Rendition`, Artifact, SHA-256 original hoặc legacy event
vì không có acquisition. Không có schema migration.

Evidence giữ profile ESummary 2.0, PMID, fingerprint snapshot/permit, mapping
version và path nguồn. Observation ID gồm field/value/evidence; rerun giữ đúng
observation và timestamp đầu tiên, kể cả mở lại database. Metadata thay đổi thêm
observation mới, không ghi đè giá trị cũ. Document/category ban đầu bất biến;
category thay đổi được giữ qua observation cho reviewer, chưa tự chọn giá trị mới.

Giao dịch item hỏng rollback item đó; item tốt vẫn được commit. Một lỗi toàn
response chặn cả trang trước khi ghi. Rerun an toàn sau lỗi/mất ACK; chưa có
checkpoint transaction xuyên trang hay bảo đảm điều phối nhiều writer. Operator
cục bộ tin cậy và handle catalog được dùng theo hợp đồng một connection/thread.
Không bypass FK liên miền. Không dùng SQL do response/request cung cấp.

Report version `0.1` chỉ có status, counts và mã lỗi/index; không có query, title,
URL trả về, credentials, body hoặc raw exception. `complete` chỉ nghĩa trang cuối
đã xử lý đủ; `page_committed` nghĩa còn trang; `incomplete` nghĩa có item cần retry;
`failed` nghĩa trang bị chặn. Trạng thái review candidate không tự làm discovery lỗi.

| Mã lỗi | Ý nghĩa |
| --- | --- |
| `invalid_configuration`, `invalid_snapshot`, `invalid_request` | Cấu hình/đầu vào sai hợp đồng |
| `unauthorized`, `domain_mismatch` | Permit hoặc miền không hợp lệ/hết hiệu lực |
| `network_disabled`, `transport_failure` | Chưa cấp transport hoặc exchange lỗi; không tự retry mạng |
| `invalid_cursor` | Cursor sai/bị sửa/không cùng binding |
| `response_too_large`, `invalid_payload` | Vượt 256 KiB hoặc sai kiểu payload |
| `invalid_json`, `duplicate_json_key` | JSON hỏng, nonfinite hoặc key lặp |
| `response_profile_mismatch`, `response_inconsistent` | Header/count/order/UID/key không khớp |
| `retrieval_window_exceeded` | Tổng kết quả vượt cửa sổ 10.000 |
| `invalid_identifier`, `summary_identity_mismatch` | Identifier sai hoặc UID mâu thuẫn |
| `invalid_metadata`, `missing_summary` | Record sai kiểu/giới hạn hoặc thiếu record |
| `identity_conflict`, `catalog_write_failed` | Binding mâu thuẫn hoặc item không commit được |

Parser chỉ nhận JSON, từ chối XML/DTD/entities; không có XML parser, entity
resolution, URL fetch hay SQL động trong connector. Fake/injected transport là
ranh giới tin cậy và phải giới hạn byte trong lúc đọc; parser kiểm tra lại quota.

## Demo và kiểm chứng

```powershell
python scripts/demo_pubmed_discovery.py
python scripts/demo_pubmed_discovery.py
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

Demo ghi database/report vào `data/pubmed-discovery-demo/` đã được ignore. Ba trang
ban đầu tạo 6 document, 50 observations; replay không tăng count. Payload cập nhật
thêm title/date observations thành 52, sau đó trang thiếu summary báo `incomplete`
và không có cursor. Có 2 title observations, 0 renditions và 0 network requests.
Chạy script lần hai giữ cùng trạng thái và report. Demo cố định clock/permit tổng
hợp để có thể tái lập; không phải phê duyệt cho nguồn thật.

Suite chung chặn socket và DNS. Integration test chạy demo hai lần trong subprocess
có guard riêng, đối chiếu kết quả và kiểm tra SQLite không chứa sentinel field bị
cấm/query. Trên Windows nếu pytest báo lỗi ACL thư mục tạm mặc định, dùng thư mục
mới trong `data/` theo [DEVELOPMENT.md](DEVELOPMENT.md#kiểm-tra-trước-commit).

| Acceptance criterion | Kiểm chứng ngoại tuyến |
| --- | --- |
| AC-01–AC-03 | Unit search/summary/pagination; contract replay nhiều page size |
| AC-04–AC-05 | Namespace normalization, category có publication-type evidence |
| AC-06–AC-08 | Allowlist/permit tests; kiểm tra toàn bộ bảng SQLite không giữ field cấm |
| AC-09–AC-10 | Rerun, mở lại DB, title/date update và observation evidence |
| AC-11–AC-12 | Domain/FK, malformed JSON, timeout, rollback từng item |
| AC-13 | Notice chỉ thành unresolved candidate, không dựng relation từ hint |
| AC-14 | Socket/DNS guard ở suite và subprocess demo |
| AC-15 | Toàn bộ regression suite catalog/backfill/HTTP/intake/export |
| AC-16 | Demo hai lần cho cùng report/state |

Kết quả validation ngày 25/11/2026 trên Python 3.12/Windows: **649 passed,
2 skipped**, gồm 126 test PubMed đạt. Hai ca regression symlink có sẵn
(`test_internal_import.py:320`, `test_html_preflight.py:212`) không chạy do thiếu
quyền tạo symlink; phần này của AC-15 chưa xác minh trên môi trường hiện tại.
Ruff lint và format check đều đạt; demo hai lần giữ kết quả như trên. Lượt baseline
ban đầu gặp lỗi ACL thư mục pytest mặc định; lượt cuối dùng `PYTEST_DEBUG_TEMPROOT`
trỏ tới thư mục đã ignore trong `data/`. Schema và định nghĩa khóa đã được đối
chiếu; thay đổi chuyển vị trí DEFINE_PROBLEM có sẵn được để ngoài commit phiên này.

## Giới hạn và điều kiện tích hợp thật

Đây là kiểm chứng trên dữ liệu fictional, chưa xác minh kết nối thật, drift API,
chất lượng metadata corpus thật, hiệu năng production hoặc quyền nguồn thật.
Không triển khai Session 06D, abstract ingestion, full-text acquisition, embeddings
hoặc RAG. Test không cần tải citation/abstract hay thông tin bệnh nhân.

Phiên tiếp theo có thể review phạm vi 06D.1 riêng: permit đã xác thực/thu hồi, endpoint
và query contract, DNS/TLS/SSRF/redirect, deadline, decompression budget, quota chung,
retry/backoff `429`/`Retry-After`, secret redaction và cơ chế snapshot live. Mạng phải
giữ tắt cho đến khi có phê duyệt vận hành riêng và các test bảo mật tương ứng.

Hướng dẫn NCBI cho tích hợp tương lai: tối đa 3 requests/giây/IP không có key,
mặc định 10 requests/giây khi có key; dùng batching, tool/email phù hợp và bố trí
job lớn theo khung NCBI khuyến nghị. Secret chỉ do operator cấp, không lưu catalog,
log, fixture hoặc Git. Phiên này không nhận/thêm API key hoặc contact thật.
[NCBI usage/API keys](https://eutilities.github.io/site/API_Key/usageandkey/)

Metadata công khai không đồng nghĩa quyền tái sử dụng abstract/full text/AI.
Cần review điều khoản và quyền từng lớp tài sản trước khi mở tính năng mới.
[E-utilities introduction](https://www.ncbi.nlm.nih.gov/books/NBK25497/) ·
[PubMed help và publication types](https://pubmed.ncbi.nlm.nih.gov/help/)
