# PMC full-text XML — M1

Trạng thái: IMPLEMENTED, OFFLINE TESTED; chưa LIVE VERIFIED. Không có tài liệu thật
được tải trong phiên phát triển. Pilot cần operator phê duyệt riêng.

## Nguồn chính thức đã đối chiếu ngày 26/11/2026

- [Developer services](https://pmc.ncbi.nlm.nih.gov/tools/developers/)
- [OAI-PMH](https://pmc.ncbi.nlm.nih.gov/tools/oai/)
- [Article datasets và thay đổi 2026](https://pmc.ncbi.nlm.nih.gov/tools/textmining/)
- [Copyright](https://pmc.ncbi.nlm.nih.gov/about/copyright/)
- [Open subset](https://pmc.ncbi.nlm.nih.gov/tools/openftlist/)

Endpoint duy nhất: https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/
Không dùng legacy OA Web Service. API hỗ trợ ListIdentifiers, ListRecords,
GetRecord và resumption token; các format oai_dc, pmc_fm và pmc. Connector M1
chỉ triển khai GetRecord metadataPrefix=pmc cho danh sách operator review 1–3 PMCID.
Không cần PubMed, API key, tìm kiếm hoặc phân trang toàn bộ collection.
pmc-open là tín hiệu truy cập, không phải quyền AI hay phân phối.

## Giới hạn và bảo mật

Một worker, khoảng cách tối thiểu một giây, chung ProviderBudget và process lease
với transport NCBI hiện có. Operator phải xác nhận IP egress không dùng chung job
NCBI khác. DNS hệ thống có timeout, kiểm tra mọi IP, kết nối tới IP đã kiểm tra,
TLS hostname/CA xác minh bằng wire 06A. Chặn mọi redirect. Tổng request 30 giây,
connect 5 giây, read 10 giây, response tối đa 4 MiB. Chỉ XML UTF-8 và encoding
identity trong profile đầu tiên. API có hỗ trợ compression; profile này chọn
không nén để giữ byte XML response và giới hạn đơn giản.

429/503 trả rate_limited; không retry tự động và không gửi tiếp các mục sau khi
pilot gặp lỗi. Vì không retry, không có lần gửi sớm hơn Retry-After. Cần phê duyệt
mới để chạy lại; CLI ghi marker một lần theo hash toàn bộ approval dưới output.
Không xóa marker để lách giới hạn. Không tự tải ảnh, phụ lục hoặc publisher links.

## Quyền theo tài liệu

OperationPolicyGate hiện có kiểm tra fetch_document, retain_metadata, store_original
và extract_content độc lập, binding source=pmc, domain=pmc-pilot,
purpose=internal_skin_lesion_corpus, resource=PMCID, profile=pmc-oai-jats-v1.
FileGate đọc lại approval tại các ranh giới; approved=false hoặc sửa file làm dừng.
Grant metadata PubMed không có hiệu lực cho PMC.

Inspection response chỉ trong RAM, giới hạn 4 MiB; envelope phải đúng OAI GetRecord,
đúng header PMCID, pmc-open và article-id. Chỉ chấp nhận dialect JATS không namespace.
Trước lưu cần đúng một license URI tường minh và khớp review của operator, quyền
retain_original, evidence và third_party_reviewed. Thiếu/không rõ thì bỏ byte khỏi
luồng lưu. Không suy license từ host hay PMCID. Operator chịu trách nhiệm kiểm tra
nội dung evidence và tài sản bên thứ ba, kể cả nội dung nhúng trong XML.
extract_text cần cả review và grant riêng. Không cấp reuse, distribution hoặc AI.
Đầu ra rights.reuse=restricted phản ánh phạm vi nội bộ này.

Approval là cấu hình tin cậy do operator giữ ngoài Git, không nhận từ nguồn tải.
Đây chưa phải RBAC/service cấp quyền doanh nghiệp. Thu hồi không tự xóa original;
operator xử lý retention theo chính sách, bảo toàn lịch sử. Reader file trực tiếp
chỉ dành cho operator có quyền; verifier không cấp quyền đọc/phân phối cho consumer.

## Byte, catalog và đầu ra

- originals/SHA256 là byte response XML chính xác, gồm envelope; không serialize lại
  article rồi gọi đó là original. Encoding HTTP identity, framing HTTP không lưu.
- events/UUID.json dùng ProvenanceStore; mỗi lần tiếp nhận có event riêng.
- catalog/ chứa SQLite hiện có, miền pmc-pilot độc lập; schema không đổi.
- runs/UUID/PMCID.json là Structured Raw v0.1 qua validator hiện hành.
- runs/UUID/PMCID.txt giữ các block văn bản theo thứ tự.
- runs/UUID/report.json chứa quyền, license evidence, IDs, trạng thái, locator
  từng block và hash record dẫn xuất.

Document/source item ổn định theo PMCID; SHA-256 dùng lại original, response đổi
tạo revision/rendition mới. OAI responseDate thay đổi có thể tạo revision quan sát
mới dù article không đổi; không tuyên bố đó là bản phát hành mới. DOI/PMID giữ
observation có evidence, không tự hợp nhất công trình giữa nguồn; đối sánh liên
nguồn dành M5. Category/scope/audience giữ unknown khi chưa có căn cứ. Catalog ghi
license observation, policy reference và rendition; không thay bảy category cũ.

Parser chặn DTD/entity/XInclude, XML hỏng, quá byte/node/depth. Hỗ trợ title,
abstract, headings, paragraphs, lists, captions, table text và references. Locator
là đường phần tử tương đối article trong envelope gốc. Inline text không diễn giải
lại phát biểu. List lồng có thể flatten và cảnh báo; bảng chỉ giữ văn bản hàng/cột.
Ảnh/công thức/element chưa xác minh trả partial; không có text trả failed.
Schema v0.1 không thêm trường: locator chi tiết nằm report sidecar cùng record hash.

Storage, provenance, catalog và derived files chưa có giao dịch xuyên filesystem.
Crash có thể để original/event chưa liên kết; giữ để đối soát, không xóa original.
Verifier kiểm tra hash, schema, text, event và catalog; chưa chống sửa đồng bộ toàn bộ
chứng cứ bởi người có quyền filesystem. Không dùng manifest export v0.1 cho run PMC.
Chưa đo fidelity/corpus coverage trên bài thật; profile namespace/size có thể cần
review sau pilot. Không tuyên bố đã đáp ứng AC-15 trước pilot được duyệt.
