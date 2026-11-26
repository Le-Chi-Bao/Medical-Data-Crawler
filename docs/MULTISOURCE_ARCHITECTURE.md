# Kiến trúc danh mục tài liệu y khoa đa nguồn

## Triển khai M0/M1 ngày 26/11/2026

Capability registry bổ sung trong multisource.py, độc lập và không thay registry
URL v0.1. PubMed và PMC implemented; năm nguồn tương lai candidate/pending_review
không có connector hoạt động. Capability không cấp quyền. Mỗi connector dùng
transport riêng, dùng chung OperationPolicyGate, ArtifactStore, ProvenanceStore
và Catalog khi phù hợp. Không tạo plugin framework.

PMC nhận danh sách 1–3 PMCID, PMCTransport trả byte; jats.py parse/inspect/extract;
pmc.py điều phối quyền/lưu/catalog/report; CLI quản lý approval và chạy.
Luồng này độc lập với lỗi redirect PubMed. [Chi tiết M1](PMC_FULLTEXT_ACQUISITION.md)
và [quickstart](MULTISOURCE_QUICKSTART.md) mô tả hợp đồng/profile đã triển khai.
Các phần đề xuất phía dưới được giữ để truy vết, không phải toàn bộ đã triển khai.

Đề xuất ngày 24/11/2026, đối chiếu `main` tại `dfc9169`. Lộ trình triển khai và điều kiện nghiệm thu nằm trong [MULTISOURCE_ROADMAP.md](MULTISOURCE_ROADMAP.md).

## Phạm vi và hợp đồng

Danh mục hỗ trợ bảy nhóm tài liệu để phục vụ một Medical RAG dành cho bác sĩ, vận hành độc lập với Computer Vision. Đó là đích của hệ thống tiêu thụ về sau. Pipeline này dừng ở danh mục, byte gốc, provenance, trích xuất kỹ thuật và xuất dữ liệu có kiểm chứng. Problem Definition v1.0 vẫn điều chỉnh MVP với phạm vi tổn thương da K01–K08 và các nhãn `general`, `medical`, `mixed`, `unknown` theo PD-04. Phân loại tài liệu, nhãn kiến thức và nhãn độc giả là ba trục độc lập, mỗi nhãn đã biết cần căn cứ. Kích hoạt nhóm, loại dữ liệu hoặc phạm vi kiến thức ngoài phê duyệt hiện tại cần biên bản Progressive Scope theo đặc tả khóa.

Structured Raw v0.1, export manifest v0.1, thuật toán `document_id` hiện hành và registry nguồn v0.1 tiếp tục dùng theo hợp đồng đã lập. Catalog và chỉ mục truy vết trích dẫn được thiết kế như dữ liệu có phiên bản riêng, liên kết qua ID và hash. Số nhóm hỗ trợ trong catalog thể hiện năng lực mô hình hóa. Việc tiếp nhận, đánh giá, tái sử dụng, dùng cho AI và phân phối được quyết định riêng theo tài liệu và mục đích. [Hợp đồng dữ liệu](DATA_CONTRACT.md) · [Chính sách pilot nội bộ](INTERNAL_PILOT_POLICY.md)

## Kiểm tra hệ thống hiện có

| Thành phần | Nền tảng dùng lại | Năng lực cần bổ sung |
| --- | --- | --- |
| Acquisition | `DocumentRequest`, `AcquisitionAdapter` và `AcquisitionResult` tách tiếp nhận khỏi trích xuất. `LocalDocumentAdapter` đọc file chỉ định, gồm entry point nhận snapshot đã kiểm tra. | Discovery, catalog đa nguồn, lập lịch và sổ theo dõi công việc. Cổng ứng dụng phải thực thi quyền trước khi đi vào primitive local. [acquisition.py](../src/medical_data_crawler/acquisition.py) |
| HTTP | 06A triển khai GET từng URL HTTPS được duyệt, tắt mặc định, chặn địa chỉ DNS ngoài tập công khai được hỗ trợ, kết nối tới IP đã kiểm tra và xác minh TLS bằng hostname. Mỗi đích redirect cần mục registry đã duyệt riêng cho cùng định dạng và User-Agent. Adapter giới hạn byte, timeout, retry và khoảng cách yêu cầu theo host trong một instance. | Profile API riêng cho endpoint/query cố định, phân trang, quota chung, secret, ETag và `304`. Profile hiện tại chỉ nhận HTML/PDF có `Content-Length` và encoding `identity`, từ chối query và dùng snapshot review tĩnh. [HTTP_ACQUISITION.md](HTTP_ACQUISITION.md) · [http_acquisition.py](../src/medical_data_crawler/http_acquisition.py) · [_https_transport.py](../src/medical_data_crawler/_https_transport.py) |
| Chính sách nguồn | Registry và gate kiểm tra review còn hiệu lực, đúng URL/UA, terms thủ công hoặc tự động, robots, quyền theo tài sản/hành động và tài sản nhúng. HTML preflight ngoại tuyến cung cấp dấu hiệu cho reviewer. | Quyền discovery và lưu từng lớp metadata, quyết định có phiên bản ở cấp tài liệu/biểu diễn, thu hồi khi hệ thống đang chạy, và gate đầu ra theo mục đích. `document_type` của registry v0.1 là hint định dạng HTML/PDF. [source_policy.py](../src/medical_data_crawler/source_policy.py) · [source registry schema](../src/medical_data_crawler/schemas/source-registry-0.1.json) · [HTML_PREFLIGHT.md](HTML_PREFLIGHT.md) |
| Tiếp nhận nội bộ | `dfc9169` và ADR 08 chứng minh baseline 06B. Gateway/CLI tách hồ sơ quyền tin cậy khỏi khai báo người bàn giao, kiểm tra đường dẫn/định dạng/hạn quyền, snapshot giới hạn với SHA-256, hỗ trợ dry-run và chỉ lưu original khi thiếu quyền extract. | Xác thực chủ thể, dịch vụ cấp quyền/thu hồi và phân vùng vận hành được kiểm chứng. Gateway hiện dựa vào người vận hành và quyền filesystem. [INTERNAL_IMPORT.md](INTERNAL_IMPORT.md) · [internal_import.py](../src/medical_data_crawler/internal_import.py) · [_intake_files.py](../src/medical_data_crawler/_intake_files.py) |
| Storage và provenance | `ArtifactStore` stream tới file tạm, kiểm tra SHA-256/kích thước, `fsync` rồi công bố bằng hard link. `ProvenanceStore` lưu event UUID riêng cho mỗi lần tiếp nhận có đủ định danh, kể cả bản trùng byte. `document_id` băm cặp `source_id`, `logical_key`. | Phân vùng storage theo miền quyền, định danh logic liên nguồn, theo dõi phiên bản, phục hồi khi storage và event công bố lệch nhau. API hiện cần root tin cậy và filesystem hỗ trợ hard link, thiếu transaction xuyên store và bảo đảm phục hồi mất điện. [storage.py](../src/medical_data_crawler/storage.py) · [provenance.py](../src/medical_data_crawler/provenance.py) |
| Trích xuất và schema | `OfflinePipeline` đọc snapshot đã kiểm tra, áp quyền trích xuất theo định dạng khi adapter cung cấp, dùng `Extractor` cho HTML/PDF và dựng record có validation khi đủ căn cứ truy cập. Trích xuất có `success`, `partial`, `failed`. PDF giữ biên trang nội bộ, HTML/PDF giữ cảnh báo và giới hạn. | Bộ phân luồng định dạng mở rộng, parser có quota tài nguyên và locator từng block. v0.1 dùng schema đóng và metadata hẹp. `process_many()` tuần tự, giữ kết quả trong bộ nhớ. [pipeline.py](../src/medical_data_crawler/pipeline.py) · [extraction.py](../src/medical_data_crawler/extraction.py) · [HTML](../src/medical_data_crawler/html_extraction.py) · [PDF](../src/medical_data_crawler/pdf_extraction.py) · [Structured Raw v0.1](../src/medical_data_crawler/schemas/structured-raw-0.1.json) |
| Xuất và xác minh | `export_batch()` đối chiếu record, schema, provenance và original, thống kê cả omissions, công bố `manifest.json` cuối cùng. `verify_batch()` đối chiếu lại inventory, hash, schema và tham chiếu. | Kiểm tra quyền khi xuất/đọc, đối chiếu tổng số đầu vào với sổ job, snapshot catalog và bằng chứng chống sửa đồng bộ. Tính nhất quán kỹ thuật hiện tại dựa trên bộ file và root đã cấu hình. [export.py](../src/medical_data_crawler/export.py) · [Export manifest v0.1](../src/medical_data_crawler/schemas/export-manifest-0.1.json) |
| Kiểm thử và pilot | Unit, contract và integration tests bao phủ luồng local, DNS/HTTP giả lập, policy, parser, integrity, intake và export. Fixture chung chặn socket và DNS. CI chạy pytest và Ruff trên Python 3.11/3.12. | Theo registry hiện tại và hồ sơ readiness, 18 ứng viên đều `needs_review`, 0 mục được duyệt và chất lượng trên corpus thật chưa được đo. Xác minh MVP lịch sử ghi 9 PASS, AC-10 PARTIAL trên fixture. [Tests](../tests) · [CI](../.github/workflows/quality.yml) · [Registry](../config/source_candidates.v0.1.json) · [PILOT_READINESS.md](PILOT_READINESS.md) · [MVP_VERIFICATION.md](MVP_VERIFICATION.md) |

## Thành phần và luồng xử lý đề xuất

```text
Nguồn metadata → Gate discovery → Connector discovery → Quan sát có căn cứ → Catalog
                                                                            ↓
                                                               Ứng viên để review
                                                                            ↓
Nguồn ngoài → Gate full text → Connector fetch ────────────────→ Original + provenance
File nội bộ → Gate nội bộ   → Gateway 06B, miền riêng ─────────→ Original + provenance miền nội bộ
                                                                            ↓
                                       Gate extract → Parser → Kiểm tra kỹ thuật → Record + locator
                                                                            ↓
                                          Gate xuất theo mục đích → Snapshot có phiên bản → Verify
```

- **Catalog** quản lý ID, các quan sát nguyên trạng theo nguồn, quan hệ, quyền và phiên bản. Chế độ quan sát metadata trước tạo ứng viên có thể tra cứu nội bộ. Mọi yêu cầu full text đi qua lệnh tiếp nhận có quyết định riêng.
- **Bộ điều phối** chia công việc theo nguồn, profile truy cập và miền quyền, cấp ngân sách, ghi cursor và trạng thái. Connector chỉ trả dữ liệu theo hợp đồng. Bộ điều phối quyết định thời điểm ghi catalog, trích xuất và xuất.
- **Cổng chính sách** phân giải điều khoản nguồn, căn cứ quyền và cấp phép theo mục đích. Bộ lưu trữ nhận stream đã qua gate, ghi byte bất biến và liên kết với event. Parser xử lý snapshot đã xác minh theo quyền và quota.
- **Bộ xuất** materialize snapshot cố định, ghi rõ mục được xuất hoặc loại cùng lý do, công bố kết quả sau xác minh. Bộ đọc áp lại quyền hiện hành theo miền và mục đích. Một snapshot lịch sử lưu quyết định tại thời điểm tạo để truy vết.

## Mô hình dữ liệu logic

`domain_id` là một phần của mọi khóa lưu trữ và khóa tham chiếu. Các liên kết trong catalog chỉ được tạo trong cùng miền quyền. Kiểm tra ràng buộc ở lớp ghi và truy xuất.

| Thực thể | Nội dung và ràng buộc |
| --- | --- |
| `AccessDomain`, `Source`, `SourceItem` | Miền bảo mật chứa nguồn. `Source` nhận diện tổ chức, dịch vụ và kênh qua cấu hình connector có phiên bản. `SourceItem` nhận diện mục gốc qua `(domain_id, source_id, native_key)`, có locator đã làm sạch, các locator cũ và liên kết review đúng đích. `source_id` v0.1 của registry web ánh xạ vào mục nguồn, vì nó chỉ một URL và định dạng. |
| `Observation` | Một nguồn ghi một giá trị cho một trường, kèm nguồn cung cấp, locator/trường chứng cứ, thời điểm quan sát UTC, phiên bản connector và mức xác minh. Giữ giá trị thô khi được phép lưu và giá trị chuẩn hóa. Khi có xung đột, giữ các quan sát và lý do chọn giá trị hiển thị. Mẫu metadata discovery đã lọc là mặc định. Lưu payload gốc của API cần quyền riêng. |
| `Document` | ID catalog bất biến trong miền, liên kết các mục nguồn đã đối sánh. `category` nhận bảy giá trị ở bảng dưới hoặc `unknown`, kèm căn cứ. Metadata dùng chung gồm tiêu đề, tác giả/tổ chức, ngôn ngữ, phạm vi, độc giả, venue hoặc publisher. Giữ độ chính xác gốc của ngày và dùng `null`/`unknown` khi thiếu căn cứ. |
| `Identifier` và `Relation` | Lưu namespace, giá trị thô/chuẩn hóa, issuer, cấp sở hữu (tài liệu hoặc phiên bản) và chứng cứ. Hỗ trợ DOI, PMID, PMCID, ISBN theo ấn bản, mã guideline, mã protocol/report nội bộ. Quan hệ có bằng chứng và có thể nối tài liệu hoặc phiên bản, gồm `edition_of`, `chapter_of`, `supersedes`, `translation_of`, `preprint_of`, `corrects`, `retracts`, `withdraws`, `expression_of_concern_for`. Có thể giữ đích chưa phân giải theo identifier. |
| `Revision` | Một phiên bản phát hành hay phiên bản quan sát được của tài liệu. Giữ mã phiên bản từ nguồn khi có, thời điểm công bố/hiệu lực/hết hiệu lực có độ chính xác, thời điểm quan sát và căn cứ trạng thái. Một phiên bản có thể có nhiều biểu diễn. Một thông báo đính chính hoặc rút bài có thể là tài liệu riêng với ID và quan hệ đến phiên bản bị ảnh hưởng. |
| `Rendition`, `Artifact` | `Rendition` là biểu diễn cụ thể của một phiên bản hoặc mục nguồn, giữ file format và MIME công bố/phát hiện, vai trò như full text hay phụ lục, binding quyền và tham chiếu acquisition. `Artifact` là byte bất biến, khóa vật lý tối thiểu `(domain_id, sha256)`, kèm kích thước. HTML, XML và PDF của một bài có thể là các biểu diễn cùng phiên bản khi có căn cứ. |
| `LicenseEvidence`, `PolicyDecision` | `LicenseEvidence` lưu tuyên bố giấy phép thô, loại/URI khi biết, nguồn, phiên bản, tài sản, thời điểm và điều kiện. `PolicyDecision` ghi chủ thể, tài sản, hành động, cách truy cập, mục đích, điều kiện, kết quả, căn cứ, reviewer hoặc authority, hiệu lực, thu hồi và revision chính sách. Đính quyết định vào lần thực thi. |
| `AcquisitionAttempt`, `ExtractionRun`, `Publication` | Lần tiếp nhận ghi phương thức (`https_document`, `provider_api`, `manual_import`, `internal_handoff`), connector, thời điểm, đích an toàn, kết quả và mã lỗi. Một request logic có thể có nhiều lần thử. `ExtractionRun` ghi input và version/profile/parser, trạng thái và locator block. `Publication` ghim phiên bản catalog/chính sách, ID batch và các tham chiếu đã xác minh. |

| Nhóm tài liệu | Đơn vị và metadata đặc thù |
| --- | --- |
| Medical Textbooks | Bộ sách, ấn bản và chương. Chương trỏ đúng ấn bản và có số/thứ tự, tiêu đề, tác giả, trang hoặc locator. Mỗi chương và ấn bản có thể có quyền riêng. |
| Clinical Guidelines | Bộ guideline của tổ chức ban hành, mã, phiên bản, quốc gia/phạm vi áp dụng, dân số mục tiêu nếu nêu rõ, ngày hiệu lực và quan hệ thay thế. |
| Research Papers | DOI/PMID/PMCID và quan hệ giữa preprint, bản chấp nhận, bản xuất bản. Giữ venue, publication type và thông báo sau xuất bản. |
| Systematic Reviews | Mục tổng quan có căn cứ về phương pháp/phân loại từ nguồn, thông tin giao thức đăng ký nếu có và quan hệ cập nhật. Có thể công bố ở dạng bài báo. |
| Medical Reference Websites | Mục/trang của nhà xuất bản, khóa bền vững nếu có, thời điểm cập nhật do nguồn khai báo và chuỗi snapshot của từng trang. Một guideline đăng dạng trang web vẫn có thể được phân loại Clinical Guidelines theo căn cứ. |
| Hospital Protocols | Mã quy trình, cơ sở/khoa quản lý, bản được ban hành, ngày hiệu lực/hết hiệu lực và quan hệ thay thế. Tài liệu bàn giao nội bộ dùng mã trung tính và ở trong miền của đơn vị có thẩm quyền. Quy trình do cơ sở công bố chính thức được review qua kênh nguồn và tài liệu đã công bố. |
| Medical Reports | Báo cáo chuyên môn/tổ chức có phạm vi và phiên bản xác định. Báo cáo công bố đi qua quyền theo tài liệu, báo cáo nội bộ đi qua miền nội bộ. Hồ sơ/case report riêng của từng bệnh nhân nằm ngoài luồng tiếp nhận thông thường của MVP. |

### Đối sánh và lịch sử

- Chuẩn hóa ID theo namespace để tìm ứng viên. Auto-link chỉ áp dụng nơi quy tắc issuer/version đã được duyệt và quan sát khớp duy nhất, đúng cấp. Trùng tiêu đề, URL, hash, ISBN của sách hoặc ID tổng hợp chỉ tạo dấu hiệu. Khi mâu thuẫn, giữ các mục độc lập đến lúc review. Hợp nhất logic bằng alias có lịch sử và có thể đảo, giữ mọi khóa cũ, quyền và quan sát.
- So sánh SHA-256 và kích thước trước khi dùng lại original trong cùng miền. Hai nguồn cùng byte vẫn có quan sát, event và căn cứ quyền riêng. Gần trùng chỉ hỗ trợ review, có thể trì hoãn. Cách ly tham chiếu mất toàn vẹn và giữ original để điều tra.
- Cùng `SourceItem` nhưng byte đổi tạo `Rendition` mới. Nếu chưa xác nhận đó là cách trình bày khác của cùng phiên bản, ghi `Revision` quan sát được và đánh dấu phiên bản phát hành chưa rõ. Thay đổi metadata đơn thuần thêm `Observation`. Thu hồi quyền, rút bài hoặc guideline hết hiệu lực cập nhật eligibility và giữ lịch sử bất biến. Tín hiệu mâu thuẫn hoặc rút bài chờ review loại phiên bản khỏi snapshot đủ điều kiện hiện hành. Việc nguồn tạm thời lỗi hoặc vắng một trang kết quả cần xác nhận trước khi đánh dấu withdrawal.

## Hợp đồng connector và đánh giá nguồn

Các chữ ký sau mô tả dữ liệu qua ranh giới kiến trúc. Connector công bố capability, phiên bản adapter, endpoint/format được phép, cách phân trang, chính sách quota và lớp lỗi. Mặc định tắt khả năng mạng, khóa profile theo cấu hình review và dùng transport được cấp vào.

| Hợp đồng | Đầu vào → đầu ra và điều kiện |
| --- | --- |
| `discover(request, permit)` | `request` gồm phạm vi đã duyệt, thời gian quan sát, cursor opaque và giới hạn trang. `permit` chỉ cho thao tác metadata và các trường được lưu. Trả `DiscoveryPage` với source keys, quan sát, link ứng viên đã lọc, dấu mốc cập nhật, cursor kế và trạng thái hoàn tất. Lỗi schema/quota có mã cố định. Abstract cần căn cứ và lớp tài sản riêng, mặc định loại khỏi lưu trữ. |
| `fetch(intent, permit)` | `intent` ghim mục nguồn, phiên bản mong muốn, đích được duyệt, định dạng, ngân sách và mục đích. Cổng cấp `permit` toàn văn giới hạn theo miền, tài sản, phương thức, locator và hạn. Trả stream giới hạn cùng trace đã lọc, hoặc kết quả như `not_modified`, `blocked`, `retryable_failure`, `terminal_failure`. Stream chỉ được công bố sau đọc đủ, đối chiếu byte/format và kiểm tra quyền lưu tại điểm công bố. Mỗi hop phải qua kiểm tra quyền của profile. |
| `intake(declaration, trusted_authorization)` | Hồ sơ bàn giao độc lập với phê duyệt tin cậy cho đúng provider, file, checksum nếu có, hành động, hạn và vùng lưu. Gateway chỉ mở file trong root được duyệt. Trả báo cáo và tham chiếu đã kiểm chứng trong miền nội bộ. Caller ứng dụng dùng gateway 06B. |
| `extract(snapshot, profile, permit)` | Snapshot bất biến đã xác minh, profile parser và quyền xử lý theo tài sản. Trả các block theo thứ tự nguồn, locator, metadata có bằng chứng và trạng thái/cảnh báo/lỗi. Parser chỉ xử lý offline. |

| Nguồn | Vai trò đề xuất và giới hạn cần review |
| --- | --- |
| PubMed | Ưu tiên discovery qua NCBI E-utilities, lấy dữ liệu thư mục như PMID, publication type, định danh liên kết và quan hệ đính chính/rút bài nếu có. Link toàn văn là ứng viên cho connector riêng. Abstract có thể chịu bản quyền. [NLM PubMed](https://pubmed.ncbi.nlm.nih.gov/about/) · [E-utilities và quyền](https://www.ncbi.nlm.nih.gov/books/NBK25497/) · [Trường dữ liệu PubMed](https://pubmed.ncbi.nlm.nih.gov/help/) |
| PubMed Central (PMC) | Metadata và ứng viên JATS từ kênh được PMC hỗ trợ, ưu tiên đánh giá OAI-PMH hoặc PMC Cloud Service hiện hành. Kiểm tra quyền của chính bài, phiên bản, tệp và tài sản trước fetch/lưu. `pmc-open` hỗ trợ sàng lọc. OA Web Service cũ đã dừng. [PMC OAI-PMH](https://pmc.ncbi.nlm.nih.gov/tools/oai/) · [PMC Cloud Service](https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/) · [Trạng thái OA Web Service](https://pmc.ncbi.nlm.nih.gov/tools/oa-service/) |
| Europe PMC | Discovery bằng REST, lưu cặp mã cơ sở nguồn/ID và đối chiếu PMID/PMCID/DOI. XML toàn văn từ tập được hỗ trợ là ứng viên sau khi review endpoint và giấy phép từng tài liệu. Ưu tiên một kênh toàn văn cho một biểu diễn trong pilot, giữ quan sát discovery của cả PMC và Europe PMC. [Europe PMC REST](https://dev.europepmc.org/RestfulWebService) · [Europe PMC Copyright](https://dev.europepmc.org/Copyright) |
| OpenAlex | Discovery đối sánh và bổ sung metadata qua Works API, external IDs, locations, OA và tín hiệu rút/gỡ bài. Một work tổng hợp có thể chứa nhiều phiên bản. License gắn với từng location và có thể thiếu. Phạm vi phiên đầu dùng trường thư mục đã cấp quyền. Khi đối soát rút bài, lấy cả kết quả đã bị rút/gỡ theo tham số của nguồn và xác minh loại thông báo. [Works attributes](https://help.openalex.org/data/works/attributes/) · [Open access](https://help.openalex.org/data/works/open-access/) · [Pulled works](https://help.openalex.org/data/works/pulled/) |
| Crossref | Discovery và làm giàu DOI, sách/chương, publisher, license hint và update/Retraction Watch/Crossmark. TDM URL là locator ứng viên với phiên bản và mục đích cần review. Quyền của abstract và full text cần căn cứ riêng. [Crossref metadata](https://www.crossref.org/documentation/retrieve-metadata/) · [Crossmark](https://www.crossref.org/documentation/crossmark/) · [Full-text links](https://www.crossref.org/documentation/retrieve-metadata/rest-api/text-and-data-mining-for-researchers/) |
| Website tham chiếu được phép | Nhập danh sách mục có cấu hình. Chỉ dùng sitemap/feed/index như discovery khi chức năng đó đã được duyệt. Dùng adapter 06A cho từng URL HTML/PDF được duyệt nếu đáp ứng giới hạn hiện có. Review terms, robots, redirect, quyền từng tài sản và thay đổi bố cục. [Chính sách nguồn](SOURCE_POLICY.md) |
| File được bàn giao | Dùng 06B cho HTML/HTM/PDF nội bộ theo khai báo và phê duyệt độc lập. Mở rộng DOCX/EPUB qua review định dạng riêng. Quyền nội bộ áp dụng cho metadata, bản gốc, bản trích xuất, locator và bản sao lưu. [INTERNAL_IMPORT.md](INTERNAL_IMPORT.md) |

Giữ profile HTTP 06A cho URL tài liệu đã review. Profile API tương lai dùng host/path và tham số có kiểu đã cấu hình, kiểm tra DNS/TLS và giới hạn egress tương đương, giới hạn kích thước trước/sau giải nén, thời gian đọc và quota theo kênh. Với response toàn văn nhiều mục, quyền đọc và quyền lưu nguyên response phải bao phủ mọi mục và tài sản nhúng. Nếu chỉ có quyền theo từng tài liệu, chọn yêu cầu trả đúng mục đã duyệt. Redirect chỉ được xử lý trong profile với review đích. Secret không đi qua redirect, log hoặc event. Cursor, URL trả về và tham số từ nguồn được xử lý như đầu vào không tin cậy. Khóa API được giữ trong kho secret của miền tương ứng. Kiểm tra lại tài liệu và điều khoản chính thức khi triển khai từng connector.

## Quyền, bảo mật và vòng đời

**Mỗi hành động có quyết định riêng.** Discovery tự động cần đồng ý về endpoint, điều khoản, phạm vi query và metadata được lưu. Fetch/read cần quyền trên đúng tài liệu, đích, phương thức và phiên bản. Lưu original cần căn cứ bao phủ toàn bộ byte, kể cả tài sản nhúng/bên thứ ba. Extract và lưu kết quả cần quyền theo định dạng/tài sản. Xuất nội bộ, reuse, AI và phân phối cần các quyết định tương ứng. AI cần quyền reuse và AI cho đúng mục đích. OA flag, license hint, robots và đường dẫn truy cập được là dữ kiện độc lập. Quyền thiếu, chưa xác minh, hết hạn, bị thu hồi hoặc điều kiện chưa đáp ứng đóng gate cho hành động đó.

**Kiểm tra ở điểm sử dụng.** Ghi revision quyết định tại lúc lên kế hoạch, kiểm tra lại trước I/O, sau thay đổi đích, trước công bố original, khi extract và lúc xuất/đọc. Nếu chưa thể ràng buộc giấy phép với phiên bản trước khi tải, reviewer phải có căn cứ cho phép tiếp nhận có giới hạn trước khi mở mạng. Khi nội dung nhận về lệch điều kiện, dừng công bố và áp dụng xử lý staging theo chính sách được duyệt. Quyền lưu lịch sử và quyền tiếp tục xử lý kiểm tra riêng. Thu hồi đóng đường đọc/xuất, phát hành dấu trạng thái theo miền, đối soát cache và kết quả dẫn xuất. Xử lý lưu giữ hoặc yêu cầu xóa theo quyết định quản trị đã duyệt và hợp đồng bảo toàn original.

**Miền tài liệu lâm sàng nội bộ.** Tách tài khoản dịch vụ, RBAC theo đơn vị và mục đích, cấu hình/secret, kho original, catalog/index, event, hàng đợi, thư mục tạm, cache, backup và đích export. Người bàn giao chỉ cung cấp request. Reviewer có thẩm quyền cấp quyền, người vận hành dùng cấu hình tin cậy độc lập. Trong triển khai có quản trị, chỉ tài khoản vận hành được chỉ định mới gọi CLI/primitive v0.1 trực tiếp hoặc mở các file của store. Consumer đọc qua cổng kiểm tra quyền hiện hành, kể cả với batch v0.1. Tắt egress ở worker intake/extraction nội bộ. Route xuất công khai loại mọi dữ liệu miền nội bộ, kể cả metadata/hash và dấu hiệu trùng. `reuse=permitted` trong record v0.1 chỉ phản ánh căn cứ đã ghi. Không gửi PHI, đường dẫn vận hành, URL ký, raw exception, nội dung hoặc dữ liệu nhạy cảm vào log/telemetry. Tài liệu nghi có PHI bị từ chối khỏi luồng thông thường hoặc chuyển vào miền cách ly được phê duyệt, có quyền, lưu giữ và audit riêng. Việc khử định danh và cho phép tiếp nhận thuộc quy trình của tổ chức.

**Input và audit.** Giới hạn MIME, byte, thời gian, RAM/CPU và độ sâu parser. Dùng snapshot/quarantine được kiểm soát, parser worker quyền tối thiểu và tắt mạng. Lưu timestamp UTC, ID job/attempt, mã lỗi, checksum, phiên bản policy/connector/parser, căn cứ và liên kết manifest bằng trường đã lọc. Audit append-only theo miền với quyền ghi/đọc tách biệt. Khi xuất ở cấp vận hành, đối chiếu snapshot qua hash manifest và bản neo tin cậy độc lập, ví dụ chữ ký theo miền. Xác minh hash/schema chỉ chứng minh toàn vẹn kỹ thuật trong phạm vi bằng chứng đã ghi.

## Cập nhật, retry và công bố

- Chia luồng discovery theo `(domain, connector, profile revision, query fingerprint)` và lưu cursor/watermark. Chỉ tiến con trỏ sau khi quan sát và công việc phát sinh đã commit cùng giao dịch catalog. Đồng bộ theo `updated_at` hoặc change feed của nguồn khi có, dùng overlap và ID ổn định để quét lại trang cuối. Nếu token hết hiệu lực, quay về watermark đã commit. Đối soát định kỳ cho nguồn có dữ liệu sửa/rút nhưng thiếu feed đầy đủ.
- Đối với full text, dùng ETag/Last-Modified theo đúng đích và profile đã duyệt khi nguồn hỗ trợ. Chỉ chấp nhận `304` nếu biểu diễn đã xác minh còn sẵn và quyền còn hiệu lực. Nếu phản hồi mới có byte trùng, ghi lần quan sát mới và liên kết artifact cũ trong cùng miền. Metadata/license/retraction vẫn được theo dõi riêng với lịch nhận byte.
- Khóa idempotency của job gồm miền, thao tác, mục nguồn, kỳ quan sát hoặc intent được lập, phiên bản/validator đã biết, mục đích và profile. Cùng job được giao lại giữ khóa logic, mỗi lần thực thi có attempt ID mới. Kỳ đồng bộ mới vẫn được chạy khi nguồn thiếu validator. Tính duy nhất của phiên bản và artifact được kiểm tra độc lập. Dùng claim có thời hạn và fencing token để worker hết lease không commit. Retry lỗi tạm thời với backoff, jitter, ngân sách theo job và quota theo nguồn, tôn trọng `Retry-After` hợp lệ hoặc lên lịch chờ. Lỗi quyền, định dạng và binding chuyển review hoặc lỗi cuối. Từng tài liệu hỏng được cô lập khỏi phần còn lại của batch.
- Ghi trạng thái bền vững theo bước và xác minh trước khi publish. Catalog dùng giao dịch cho state và work queue/outbox. Original, event và manifest nằm ngoài giao dịch đó. Khi restart, đối chiếu intent, artifact đã công bố, event và snapshot. Chỉ tiếp tục khi hash và tham chiếu khớp. Đánh dấu orphan để xử lý có thẩm quyền. Giữ manifest-last cho batch v0.1 và dùng commit riêng cho snapshot catalog/locator. Consumer thấy snapshot mới khi cả manifest và tham chiếu sidecar bắt buộc đã xác minh. Rerun dùng artifact đã được xác nhận, giữ lịch sử công bố.

## Định dạng, chất lượng và provenance trích dẫn

| Định dạng | Chiến lược theo giai đoạn |
| --- | --- |
| HTML | Dùng lại DOM extractor và preflight. Chuẩn hóa profile theo cấu trúc thực tế của nguồn khi đã có fixture. Giữ heading, thứ tự, list và bảng đơn giản. Dùng fragment/DOM path gắn với hash. |
| PDF | Dùng text layer hiện có, gắn số trang vật lý và khoảng block qua `PageBoundary`, ghi cảnh báo bố cục/scan/mã hóa. OCR và tái tạo bảng phức tạp là quyết định sau đánh giá pilot. |
| JATS/XML | Ưu tiên JATS cho bài đủ quyền. Trích section/title/body/list/bảng khi hỗ trợ và giữ XML ID/path. Giới hạn dialect và tài nguyên. Parser vô hiệu thực thể ngoài, tải DTD, XInclude và truy cập mạng. PubMed XML metadata và envelope OAI là định dạng đầu vào khác với bài JATS. Khi lấy bài từ envelope đã được phép lưu, giữ byte response chính xác và quy nguồn đến record/phần tử, ghi dữ liệu tách ra là dẫn xuất. [NLM JATS](https://jats.nlm.nih.gov/) |
| DOCX | Bổ sung sau thử nghiệm riêng. Parse OOXML offline, ghi part/paragraph hoặc section, giữ danh sách/bảng đơn giản. Giới hạn ZIP và chặn tham chiếu ngoài, mã thực thi, embedded object chưa duyệt. |
| EPUB | Bổ sung sau thử nghiệm riêng. Duyệt spine/manifest theo thứ tự, liên kết chương–ấn bản và ghi entry/fragment. Giới hạn ZIP, traversal, tài nguyên ngoài và từ chối nội dung bảo vệ chưa hỗ trợ. |

Locator trích dẫn được ghi theo `(domain_id, revision_id, rendition_id, sha256, extraction_run_id, block_index)` cùng tọa độ nguồn phù hợp định dạng. Locator có trạng thái khi parser thiếu bằng chứng. Chỉ mục có phiên bản liên kết locator đến `record_sha256` và `event_id` của output v0.1. Trích dẫn phiên bản lịch sử cần ghi trạng thái đính chính/rút/thay thế và kiểm tra lại quyền hiển thị locator, đoạn trích và tài liệu. Dữ liệu nội bộ dùng reference trung tính trong miền.

Quality gate tách các kết quả có thể đo gồm byte/hash, parsing, schema, độ đầy đủ metadata/quyền, locator truy được, fidelity văn bản/thứ tự/heading/list/bảng theo lấy mẫu, tỷ lệ `success`/`partial`/`failed` theo định dạng và bao phủ K01–K08 có căn cứ. Khi trích xuất lỗi sau khi có original hợp lệ, giữ event/record lỗi theo hợp đồng và loại khỏi snapshot nội dung đủ điều kiện. Reviewer thiết lập ngưỡng sau khi có tập đánh giá đại diện và đã duyệt. Độ trung thực kỹ thuật và tính cập nhật do nguồn báo cáo là hai tín hiệu riêng. [Phiếu đánh giá pilot](PILOT_EVALUATION.md)

## Đánh đổi, rủi ro và quyết định mở

| Rủi ro hoặc đánh đổi | Quyết định thiết kế và việc còn mở |
| --- | --- |
| ID liên nguồn dễ ghép sai bản, sai chương | ID nội bộ và alias có lịch sử tăng công review, giữ nguyên ID v0.1. Cần chốt quy tắc tự ghép theo issuer, xử lý ID nhiều phiên bản và thẩm quyền xử lý xung đột. |
| Discovery phong phú dễ dẫn tới cấp quyền quá rộng | Tách profile discovery và fetch, lọc trường và ràng buộc quyền theo tài sản. Cần xác định reviewer, quyền metadata/abstract, tiêu chí quyền AI sau pilot và cách ghi căn cứ khi nguồn sửa giấy phép. |
| Tài liệu nội bộ, PHI và bằng chứng nhạy cảm | Giữ miền riêng kể cả bản sao và audit. Cần chốt chủ thể phê duyệt, mô hình miền/tenant, ACL, khóa, xử lý sự cố, lưu giữ và cơ chế thu hồi theo từng tổ chức. |
| Đính chính/rút bài và thay thế guideline có thể đến muộn | Đối soát nhiều nguồn, giữ tín hiệu mâu thuẫn và đưa vào review. Cần chọn thứ tự tin cậy theo trường, SLA cập nhật và quy trình xử lý tài liệu đã xuất khi có thay đổi. |
| Mất điện, worker bị dừng, sửa đồng bộ dữ liệu | Tận dụng store cục bộ và manifest-last, đầu tư ledger, neo hash và phục hồi trước vận hành. Đề xuất catalog quan hệ với giao dịch và khóa duy nhất. Chọn SQLite khi một process ghi hoặc PostgreSQL khi cần nhiều worker sau khi đo tải. Cần chốt storage theo miền, backup/RPO/RTO và trust anchor. |
| Định dạng và fidelity không đồng đều | Ưu tiên dùng lại HTML/PDF rồi thêm JATS với profile giới hạn. Giữ `partial` và lỗi có thể đánh giá. Cần chốt profile locator mới, chuẩn xuất riêng cho định dạng ngoài v0.1, tiêu chí OCR và rubric khi có mẫu đại diện. |
| Drift API, quota và chi phí | Adapter tách biệt, fixture có phiên bản và profile quota. Cần chọn connector ưu tiên, nhịp polling, ngân sách, nguyên tắc thử nghiệm network và mức tải nghiệm thu sau review. |
| Phạm vi và phê duyệt roadmap | K01–K08 là phạm vi hiện tại. Cần xác nhận ánh xạ 06C–06E, taxonomy chính thức và các biên bản thay đổi nếu mở loại dữ liệu/phạm vi ngoài MVP. [Lộ trình](MULTISOURCE_ROADMAP.md) |
