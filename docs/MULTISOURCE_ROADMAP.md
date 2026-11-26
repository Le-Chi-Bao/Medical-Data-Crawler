# Lộ trình triển khai danh mục tài liệu y khoa đa nguồn

## Ưu tiên mới được duyệt trong phiên M0/M1 — 26/11/2026

Lộ trình 06C–06E phía dưới được giữ nguyên để truy vết. Baseline đã có catalog,
PubMed và secure transport. Theo yêu cầu phiên M0/M1, ưu tiên PMC toàn văn trước
Crossref/Europe PMC để thu nội dung phục vụ tổn thương da, tránh phụ thuộc PubMed
đang redirect_denied. M0 tương ứng nền tảng capability/report; M1 thực hiện phần
06D.2b + 06D.3 bằng PMC OAI GetRecord, XML/JATS và kiểm thử offline.

| Phiên | Phạm vi / trạng thái |
| --- | --- |
| M0 | Registry capability, nguồn độc lập, báo cáo — implemented, offline tested |
| M1 | PMC XML, quyền riêng, JATS, catalog, CLI — implemented, offline tested; chờ pilot |
| M2 | MedlinePlus — chưa triển khai |
| M3 | NCBI Bookshelf — chưa triển khai |
| M4 | WHO và nguồn clinical/reference được duyệt — chưa triển khai |
| M5 | Đối sánh liên nguồn, lịch, mở rộng và chất lượng corpus — chưa triển khai |

M2–M5 cần phiên được duyệt riêng. M1 chưa LIVE VERIFIED; AC-15 chờ pilot. Chưa
thay phạm vi K01–K08, category hay triển khai RAG. [Quickstart](MULTISOURCE_QUICKSTART.md)
và [backlog](MULTISOURCE_BACKLOG.md).

Đề xuất ngày 24/11/2026, đối chiếu `main` tại `dfc9169`. Phiên thiết kế kết thúc khi hai tài liệu được rà soát. Mỗi phiên triển khai dưới đây cần phạm vi được phê duyệt riêng. [Kiến trúc đề xuất](MULTISOURCE_ARCHITECTURE.md)

## Quan hệ với Phase 06B–06E

| Phase | Bằng chứng và vị trí đề xuất |
| --- | --- |
| 06B | `dfc9169` và ADR 08 xác nhận đã có gateway/CLI tiếp nhận file nội bộ HTML/HTM/PDF, dry-run, quyền tách khỏi hồ sơ bàn giao, provenance và export xác minh trên fixture. Dùng lại như baseline kỹ thuật. Nghiệm thu với danh tính, phân quyền và tài liệu thật còn chờ đơn vị có thẩm quyền. [ADR 08](ARCHITECTURE.md#adr-08--tiếp-nhận-tài-liệu-nội-bộ-trong-session-06b) · [Hướng dẫn intake](INTERNAL_IMPORT.md) · [Integration tests](../tests/integration/test_internal_import.py) |
| 06C | Đề xuất catalog, ánh xạ dữ liệu v0.1 và discovery trên fixture. |
| 06D | Đề xuất quyền và transport theo profile, bổ sung connector theo từng nguồn, sau đó thử toàn văn và JATS trên fixture. Dùng lại các ràng buộc HTTP của 06A cho URL tài liệu đáp ứng hợp đồng đó. [HTTP 06A](HTTP_ACQUISITION.md) |
| 06E | Đề xuất độ bền vận hành, hàng rào nội bộ, snapshot có kiểm chứng và pilot chất lượng. Việc thử tài liệu thật chỉ bắt đầu sau khi các gate tương ứng hoạt động và được duyệt. |

Phạm vi chính thức của 06C–06E chưa được xác định trong tài liệu, refs và lịch sử Git hiện có. Các mã dưới đây là ánh xạ đề xuất để xác nhận với người phụ trách roadmap trước khi giao việc. Registry hiện có 18 mục `needs_review`, 0 phê duyệt. Pilot 05B dùng bản thủ công từ nguồn công khai đã review để lưu và đánh giá nội bộ. Tài liệu do đơn vị lâm sàng bàn giao đi qua 06B với phê duyệt và miền lưu trữ riêng. Bất kỳ thử nghiệm tự động với nguồn thật nào cần quyết định riêng về hoạt động mạng, dữ liệu và mục đích. [Registry](../config/source_candidates.v0.1.json) · [Trạng thái pilot](PILOT_READINESS.md) · [Chính sách pilot 05B](INTERNAL_PILOT_POLICY.md)

## Phiên triển khai và nghiệm thu

### 06C.1 — Hợp đồng danh mục và định danh

- **Phụ thuộc.** Problem Definition v1.0, record/manifest v0.1 và quyết định về miền quyền, category, khóa logic, quan hệ và provenance.
- **Bàn giao.** Schema catalog phiên bản đầu, ràng buộc khóa domain/source/item, observation, identifier, document, revision, rendition, relation và mô hình quyền. Dữ liệu tổng hợp cho cả bảy nhóm, một mục `unknown` và nhiều phiên bản tài liệu.
- **Nghiệm thu.** Tạo được sách–ấn bản–chương, guideline thay thế, nghiên cứu nhiều biểu diễn và thông báo rút bài với định danh riêng. Thiếu bằng chứng giữ `unknown` hoặc giữ quan sát mâu thuẫn. Các FK và query từ chối liên kết khác miền. Record Structured Raw và manifest v0.1 tiếp tục qua validator hiện tại.
- **Kiểm thử.** Contract test cho thiếu trường, quan hệ sai cấp, namespace/issuer, kết hợp nhãn K01–K08 và audience, cùng ca không ghép sách với chương khi trùng ISBN.

### 06C.2 — Backfill song song từ v0.1

- **Phụ thuộc.** 06C.1 và API `verify_batch()`.
- **Bàn giao.** Công cụ đọc batch và tạo ánh xạ có phiên bản theo chiến lược migration bên dưới. Có dry-run và báo cáo số mục đã nối, chưa đủ căn cứ hoặc mất toàn vẹn.
- **Nghiệm thu.** Chạy hai lần tạo cùng ánh xạ, giữ nguyên ID, byte, checksum, file record và manifest cũ. Mỗi record xác minh được có đường truy đến event/original. Lỗi tham chiếu tạo mục đối soát và chặn snapshot mới tương ứng.
- **Kiểm thử.** Batch fixture hỗn hợp gồm bản ghi cũ khác thời điểm, byte trùng khác nguồn, extraction thất bại, omission, event thiếu và input nội bộ. So sánh hash cả trước và sau.

### 06C.3 — Discovery ngoại tuyến với PubMed

- **Phụ thuộc.** 06C.1 và thiết kế cho phép metadata theo trường.
- **Bàn giao.** Hợp đồng discovery và adapter PubMed đầu tiên chạy bằng payload tổng hợp, transport giả, trường thư mục được lọc và phiên bản mapping có thể truy vết. Giữ link/PMCID ở hàng review.
- **Nghiệm thu.** Có thể tìm lại provenance của thông tin nhập, lặp trang ổn định, giữ quan hệ correction/retraction khi có bằng chứng. Luồng discovery chỉ ghi metadata có quyền lưu. Ca có OA/link, abstract hoặc cursor giả không mở đường fetch.
- **Kiểm thử.** Fixture nhiều trang, record lặp, XML xấu, ID thiếu, quan hệ chưa phân giải, response có trường dư và lỗi tạm thời. Chặn socket/DNS trong suite.

### 06D.1 — Profile API và gate theo thao tác

- **Phụ thuộc.** 06C.3, reviewer xác nhận kênh và mô hình quyền, danh sách endpoint/phạm vi query và kế hoạch quản lý secret. Chạy kiểm thử offline trước mọi đề xuất thử mạng.
- **Bàn giao.** Transport profile API riêng, khóa host/path, typed query và quota, timeout/byte/decompression budget, allowlist header và xử lý lỗi đã lọc. Gate tách discovery, fetch, storage, extract và export theo mục đích, phiên bản, quyền hiện hành và miền. Giữ transport tài liệu 06A cho luồng v0.1.
- **Nghiệm thu.** Permit discovery bị từ chối khi dùng cho toàn văn. Đích đổi, sai phiên bản/tài sản, quyền hết hạn hoặc bị thu hồi trước I/O/công bố làm dừng hành động. Egress, DNS/TLS, redirect, secret redaction và hành vi 06A qua regression tests.
- **Kiểm thử.** Fake transport cho query/redirect ngoài profile, DNS không an toàn, replay, expiry giữa các bước, gzip vượt quota, 429 và `Retry-After`, lỗi xác thực và thay đổi schema response.

### 06D.2 — Thêm connector discovery, mỗi nguồn một phiên

- **Phụ thuộc chung.** 06C.3 và 06D.1. Mỗi phiên thêm fixture đã tổng hợp, profile riêng và quy tắc đối sánh có bằng chứng. Nghiệm thu chung yêu cầu cursor/ID có thể replay, từ chối field chưa cấp quyền, nguồn lỗi bị cô lập và metadata mới giữ provenance.

| Phiên | Bàn giao và kiểm thử nghiệm thu riêng |
| --- | --- |
| 06D.2a — Crossref | Ánh xạ DOI, book/chapter, update và license hint. Fixture DOI trùng giữa nguồn, chapter chưa rõ ấn bản và notice có DOI riêng. TDM link không tạo lệnh tải. |
| 06D.2b — PMC | Ánh xạ PMCID và quyền/phiên bản từ kênh PMC đã chọn. Fixture phân biệt OA hint, tài sản nhúng và bản phát hành thực tế. |
| 06D.2c — Europe PMC | Ánh xạ nguồn/ID và liên kết PMID/PMCID/DOI. Fixture overlap với PMC, record phân trang và trạng thái XML toàn văn chỉ là ứng viên. |
| 06D.2d — OpenAlex | Làm giàu IDs, locations và tín hiệu rút/gỡ bài. Fixture nguồn tổng hợp gom preprint và bản xuất bản, license các location mâu thuẫn, abstract bị loại. |
| 06D.2e — Website | Nạp danh sách mục được duyệt. Xét feed khi có phê duyệt riêng. Fixture URL/redirect lệch binding, HTML thay đổi và link tài sản bên thứ ba. Đường tiếp nhận từng mục vẫn qua gate 06A. |

File bàn giao nội bộ tiếp tục qua 06B. Sau 06C.2 có thể nối báo cáo/event đã kiểm chứng từ gateway vào catalog bằng cùng phép ánh xạ theo miền, dùng fixture và thử truy xuất ngoài miền. [Quy tắc intake](INTERNAL_IMPORT.md)

### 06D.3 — Một đường toàn văn và một profile JATS

- **Phụ thuộc.** 06D.1 và một connector phù hợp từ 06D.2b hoặc 06D.2c. Chọn một kênh PMC hoặc Europe PMC và một dialect JATS trên fixture. Kiểm tra khả năng ghi bằng chứng quyền theo phiên bản và tài sản trước khi chốt profile.
- **Bàn giao.** Hai phần review độc lập. Phần fetch ghi stream gốc + event theo đúng permit, kiểm tra định dạng và quyền trước công bố. Phần parser trích xuất JATS offline với locator XML, giữ thứ tự và báo giới hạn. Đầu ra mới dùng kết quả nội bộ hoặc projection có hợp đồng riêng khi được duyệt.
- **Nghiệm thu.** Quyền đọc/lưu bao phủ byte cho phép công bố original cùng event. Nếu thiếu quyền extract, kết quả dừng ở original và event. Khi quyền extract hợp lệ, provenance chỉ ra đúng hash byte response và quan hệ giữa response với tài liệu. `partial`/`failed` có chứng cứ và file dẫn xuất mang tham chiếu input. Structured Raw v0.1 giữ đường xuất HTML/PDF và khả năng đọc batch cũ.
- **Kiểm thử.** JATS artifact đơn, response envelope có mục thiếu quyền, lưu original khi thiếu quyền extract, revision thay đổi, giấy phép thiếu, MIME/bytes lệch, từ chối thực thể ngoài/DTD, kích thước/cấu trúc vượt giới hạn và parser mất section. Tất cả dữ liệu thử là fixture.

### 06E.1 — Điều phối bền vững và đối soát

- **Phụ thuộc.** 06C.2, 06C.3 và các profile acquisition dự định đưa vào pilot. Có thể làm song song với 06D.2 sau khi hợp đồng job được thống nhất.
- **Bàn giao.** Ledger trạng thái, cursor/watermark giao dịch, idempotency, lease có fencing, lịch retry và quota theo nguồn, đối soát artifact/event/manifest và báo cáo orphan. Ghi quyết định ở từng thao tác, hỗ trợ revocation trong batch.
- **Nghiệm thu.** Rerun không nhân bản phiên bản logic. Mỗi lần thử có sự kiện riêng. Content thay đổi được lưu bất biến. `304` có validator và bản đã xác minh chỉ làm mới quan sát. Crash hoặc worker chạy song song không công bố snapshot thiếu và không tiến cursor qua dữ liệu chưa commit. Job lỗi được tách khỏi batch.
- **Kiểm thử.** Fault injection tại các ranh giới trước/sau lưu byte, event, giao dịch catalog, manifest và checkpoint. Tranh lease, quota nhiều worker, 304 thiếu bản trước, nhiều kỳ polling không có validator, cursor hết hạn, bản sửa muộn, mất quyền trong lúc retry và manifest đã công bố khi ACK bị mất.

### 06E.2 — Ranh giới vận hành nội bộ

- **Phụ thuộc.** Baseline 06B, 06C.1, 06D.1 và quyết định tổ chức về danh tính, miền, steward, PHI và lưu giữ.
- **Bàn giao.** Tích hợp identity/RBAC và hồ sơ cấp phép do operator kiểm soát, tách store, key, temp, queue, audit, backup và export theo miền. Quy trình cách ly, thu hồi và phục hồi nội bộ được thử trên fixture.
- **Nghiệm thu.** Submitter không tự cấp quyền. Tài khoản ngoài miền hoặc đường xuất công khai không thể liệt kê, tìm trùng, đọc hay phân giải citation nội bộ. Consumer dùng cổng kiểm tra quyền kể cả khi đọc batch v0.1. File và CLI trực tiếp chỉ dành cho vai trò vận hành được chỉ định. Backup/restore giữ nguyên ACL, miền và quyết định quyền. Tài liệu nghi PHI bị từ chối khỏi luồng bình thường hoặc đi đúng vùng cách ly được duyệt.
- **Kiểm thử.** Ca âm cho export/cache/log/temp/backup, metadata/hash leak, file path và grant không khớp, thu hồi giữa các bước và worker nội bộ không có egress. Các ca audit dùng mã nhận diện tổng hợp.

### 06E.3 — Publication có truy vết và đánh giá chất lượng

- **Phụ thuộc.** 06C.2, 06E.1 và 06E.2 cho đầu ra nội bộ. Chỉ đưa vào thử nghiệm định dạng có parser/profile đã kiểm chứng.
- **Bàn giao.** Snapshot có manifest giữ tương thích, chỉ mục locator riêng có phiên bản, ràng buộc với batch/record/event/original, review policy khi publish/read và neo hash theo miền. Chuẩn hóa báo cáo quality theo schema/rights, fidelity, provenance, độ bao phủ và lỗi xử lý.
- **Nghiệm thu.** Reader cũ vẫn đọc batch v0.1. Reader mới truy block đến đúng bản nguồn và trạng thái, từ chối locator thiếu căn cứ hoặc khác miền. Snapshot bị loại nếu sidecar, hash, hoàn tất ledger hoặc quyền không khớp. Lịch sử chứng minh được nguồn khi bản đã rút/thay thế bị hạn chế theo policy hiện hành.
- **Kiểm thử.** Sửa manifest, sidecar hoặc original, bỏ record khỏi inventory, tạo locator sai trang/phiên bản và thu hồi quyền sau publish. Đối chiếu số mục xuất lẫn omission với sổ job. Fixture hỗn hợp chạy cùng verifier offline hiện tại.

### 06E.4 — Nghiệm thu pilot có phê duyệt riêng

- **Phụ thuộc.** 06E.1–06E.3, reviewer có thẩm quyền, phạm vi K01–K08, các approval còn hiệu lực và bộ mẫu đại diện đã được duyệt cho từng luồng. Tách biên bản/ngưỡng cho pilot thủ công nguồn công khai, thử tự động có phạm vi và hồ sơ nội bộ. Nhánh thử tự động cần phê duyệt mạng độc lập.
- **Bàn giao.** Báo cáo chất lượng theo định dạng/nguồn, coverage có căn cứ, tính đầy đủ metadata/rights, tỷ lệ thành công/mất cấu trúc, truy vết trích dẫn và sự cố phục hồi. Phân biệt trạng thái đo được và chưa đo. Dùng tiêu chí lịch sử AC-01–AC-10 và hồ sơ pilot để đối chiếu.
- **Nghiệm thu.** Tính lại SHA-256, xác minh toàn vẹn và provenance của toàn bộ mục được chấp nhận, mỗi mục đều có trạng thái. Mẫu đánh giá fidelity và K01–K08 được reviewer xác nhận. Chốt ngưỡng sau khi có tập đại diện. Khi điều kiện còn thiếu, phần nghiệm thu thật tiếp tục ở trạng thái chờ.
- **Kiểm thử.** Suite tự động dùng fixture cục bộ. Đợt nghiệm thu đo trên tài liệu được duyệt chạy riêng ngoài CI. Ghi rõ phạm vi quyết định và các ca định dạng, quyền, parser, revision và phục hồi đã được đo. [Tiêu chí MVP](MVP_VERIFICATION.md) · [Kế hoạch pilot](PILOT_PLAN.md) · [Phiếu đánh giá](PILOT_EVALUATION.md)

### Sau 06E — DOCX, EPUB và mở rộng phạm vi

Xét DOCX nội bộ và EPUB/sách theo hai phiên riêng sau khi có kết quả pilot, căn cứ Progressive Scope và quyền theo định dạng. Mỗi phiên thêm profile kiểm tra file, parser offline, locator, fixture package hợp lệ/hỏng, quota ZIP và ca tham chiếu ngoài. Nghiệm thu DOCX gồm thứ tự đoạn/mục và bảng đơn giản. Nghiệm thu EPUB gồm liên kết ấn bản–chương, thứ tự spine và locator entry/fragment. Review OCR/PDF phức tạp trong phiên riêng nếu mẫu đánh giá có nhu cầu. Quyết định về AI/RAG thuộc công việc tiêu thụ dữ liệu trong tương lai.

## Migration và quay lại reader cũ

1. Kiểm kê bản ghi, manifest, provenance và originals theo miền thực tế được xác nhận. Dùng `verify_batch()` với đúng store, kiểm tra checksum và quy quyền hiện hành riêng. Batch thiếu dữ liệu hoặc chưa rõ miền vào danh sách đối soát có kiểm soát. Tập hợp nguồn legacy từ registry/review/event đã biết.
2. Tạo catalog song song, đọc v0.1 qua API/hợp đồng đang dùng. Giữ ánh xạ `(domain_id, legacy_document_id)` và các tham chiếu từng lần xuất qua `(batch_id, record_sha256, event_id, original_sha256)`. Chỉ backfill `logical_key` từ hồ sơ đáng tin có giá trị gốc. Event v0.1 chứa `document_id` đã băm và thiếu `logical_key`. Giữ lọc scope K01–K08 và audience như cũ, để category/phiên bản/quyền chưa đủ căn cứ là `unknown`, đánh dấu locator chi tiết là thiếu nếu chưa có bằng chứng.
3. Chạy dry-run và backfill lặp trên fixture. So sánh hash manifest/record/original với baseline, xác minh tính đầy đủ mapping, kiểm tra alias và quyền miền bằng ca âm. Kiểm thử cả reader cũ và reader mới đối với record `partial`/`failed`, nil locator và omissions. Đối chiếu kết quả song song trước khi mở reader mới cho người đã được cấp quyền.
4. Chuyển reader/writer mới theo cấu hình từng miền khi nghiệm thu. Giữ v0.1 và phiên bản sidecar tách nhau, công bố projection mới bằng commit riêng có kiểm chứng. Khi phát hiện vấn đề, ngắt publish mới, chuyển reader phù hợp về snapshot đã xác minh theo quyền hiện hành, bảo toàn originals/batch cũ và giữ ledger phục vụ đối soát. Quay lại cấu hình cũ vẫn phải thực thi quyền thu hồi đã ghi.

## Kiểm tra chung và các quyết định cần chốt

- Mỗi phiên chạy `python -m pytest -q`, `python -m ruff check .` và `python -m ruff format --check .` trong môi trường repo. Với thay đổi hợp đồng, chạy contract và regression trên cả dữ liệu legacy và projection mới. Giữ fixture/synthetic cho tất cả kiểm thử tự động, cùng network guard hiện tại. Xem staged diff theo phạm vi phiên, giữ source approvals, secret và dữ liệu ngoài commit. [Hướng dẫn kiểm tra](DEVELOPMENT.md#kiểm-tra-trước-commit) · [Fixture và network guard](../tests/conftest.py) · [CI](../.github/workflows/quality.yml)
- Xác nhận tên/phạm vi 06C–06E và quyền mở các nhóm, định dạng hoặc đề tài mới trước khi chốt kế hoạch triển khai. Cần chốt issuer/luật đối sánh, authoritative source cho đính chính/rút bài, vòng đời quyền và retention nội bộ, storage/catalog backend, tiêu chí pilot và ngân sách vận hành. [Rủi ro và quyết định mở](MULTISOURCE_ARCHITECTURE.md#đánh-đổi-rủi-ro-và-quyết-định-mở)
