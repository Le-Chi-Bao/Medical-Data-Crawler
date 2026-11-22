# Kiến trúc pipeline thu thập tài liệu

## Quyết định đã áp dụng trong Session 01

| ADR | Quyết định | Lý do và hệ quả |
| --- | --- | --- |
| 01 | Một Python package, yêu cầu Python 3.11 trở lên | Dùng được `tomllib`, `hashlib`, `logging` và kiểm thử từng hàm bằng dữ liệu cục bộ. |
| 02 | JSON Schema Draft 2020-12 là nguồn quy tắc duy nhất cho bản ghi | Validator và consumer dùng cùng schema trong package. `jsonschema` kiểm tra các ràng buộc giữa trạng thái và content. `rfc3339-validator` kiểm tra thời điểm thu thập. |
| 03 | Hàm băm nhận `BinaryIO`, cấu hình có thể nhận `Mapping`, validator nhận giá trị JSON đã giải mã | Các interface này dùng được với stream và cấu hình trong bộ nhớ. Chỉ thêm protocol riêng khi có caller cần thay thế adapter. |

`config` đọc TOML và biến môi trường. `logging_setup` nhận Settings từ caller. `integrity` chỉ đọc stream. `contract` phụ thuộc vào schema đóng gói. Cả config và contract báo lỗi qua `errors`. Import package không khởi chạy pipeline. Chiều phụ thuộc dự kiến đi từ bộ điều phối tới các adapter và các hàm nền tảng.

## Luồng và ranh giới đề xuất cho giai đoạn sau

| Bước | Đầu vào → đầu ra | Trách nhiệm |
| --- | --- | --- |
| Acquisition | Mục trong danh sách nguồn → byte và sự kiện truy xuất | Xác minh quyền, áp dụng giới hạn của nguồn, ghi trạng thái từng lần thử. |
| Original storage | Stream → tham chiếu bất biến, kích thước và SHA-256 | Ghi file tạm, kiểm tra toàn vẹn trước khi công bố. Reader chỉ đọc artifact đã hoàn tất. |
| Exact deduplication | Hash → artifact hiện có hoặc mới | Khi nội dung trùng, tái sử dụng artifact đã kiểm chứng và giữ sự kiện nguồn riêng. |
| Extraction | Artifact → dãy block theo thứ tự nguồn | Giữ nguyên ngôn từ, đánh dấu cấu trúc mất và lưu phương pháp, phiên bản, cấu hình. |
| Metadata và provenance | Sự kiện nguồn + kết quả đọc → record có ID | Liên kết từng block qua record với original và source. Giữ căn cứ của nhãn, biểu diễn trường thiếu. |
| Validation | File và record → kết quả kiểm tra | Kiểm tra byte, hash, tham chiếu và schema trước export. Session 01 chỉ cung cấp hàm băm và validator schema. |
| Export | Record hợp lệ → Structured Raw và manifest có phiên bản | Ghi rõ trạng thái mỗi record, đối chiếu tham chiếu trước khi công bố cả batch. |

Đề xuất lưu originals trên filesystem theo SHA-256. Hai nguồn có byte giống nhau có thể dùng cùng artifact. Khi byte tại cùng nguồn thay đổi, lưu artifact mới và giữ lịch sử. Storage cần kiểm thử ghi gián đoạn, ghi đồng thời và chạy lại trước khi dùng với dữ liệu thật.

## Xử lý lỗi và kiểm thử

Lỗi cấu hình dùng `ConfigurationError` và cần được xử lý trước batch. Validator trả `RecordValidationError` với đường dẫn quy tắc schema. Caller tương lai chịu trách nhiệm cô lập lỗi theo tài liệu. Nếu đã có original hợp lệ, lỗi extraction phải để lại record truy vết. Nếu acquisition thất bại trước khi có byte, ghi sự kiện thất bại riêng. Log chỉ nên mang mã lỗi, trạng thái và ID nội bộ an toàn. Nội dung, PHI, token và URL chứa thông tin xác thực phải được loại khỏi log.

Unit tests kiểm tra byte nhị phân, nguồn cấu hình và logging. Contract tests dùng fixture tự tạo, thay đổi từng trường để kiểm tra các trạng thái hợp lệ và không hợp lệ. CI kiểm tra cả bản cài package thông thường. Các phase sau cần test liên kết record với file thật, hash tính lại, batch hỗn hợp, retry và fidelity trên mẫu được phép.

## Quyết định còn mở

Cần review khóa logic cho từng nguồn, schema của manifest, chính sách rights/PHI và bộ mẫu HTML/PDF đại diện. Session 03 có acquisition cục bộ, extractor và điều phối offline; chưa có HTTP crawling, scheduler hay exporter/manifest. Các block dạng bảng ở v0.1 mang văn bản, chưa mô hình hóa ô và quan hệ hàng/cột.

## ADR 04 — Storage và identity trong Session 02

Đã triển khai ArtifactStore với put(bytes hoặc BinaryIO), verify(checksum) và
copy_to(checksum, destination). Caller giữ vòng đời input stream, được đọc từ vị trí hiện tại.
File rỗng bị từ chối để phù hợp original.byte_length của contract v0.1.
Artifact nằm tại root/SHA-256. Temporary file cùng filesystem được flush, fsync
và công bố bằng os.link. Hard link chỉ tạo tên mới, từ chối thay thế tên đã có.
Nếu filesystem không hỗ trợ hard link, thao tác báo StorageError.
Các lần ingest trùng kiểm tra hash, kích thước và so sánh byte.
File hỏng được giữ lại để điều tra, thao tác thất bại an toàn.

Lựa chọn ID theo content hash sẽ đổi khi nội dung đổi. UUID ngẫu nhiên cần registry
để giữ ổn định qua rerun. Session 02 chọn hàm document_id(source_id, logical_key)
băm cặp chuỗi JSON UTF-8 bằng SHA-256. Caller cung cấp khóa bền vững theo nguồn,
không tự chuẩn hóa URL. Phiên bản nội dung dùng hash artifact riêng.
Sự kiện provenance có UUID riêng cho mỗi lần gọi record, kể cả nguồn và byte trùng.
ProvenanceStore kiểm tra artifact trước khi công bố từng JSON bằng hard link.
Sự kiện failed lưu mã lỗi an toàn cùng tham chiếu null. Schema export v0.1 giữ nguyên.

Root storage cần nằm trong vùng do ứng dụng tin cậy quản lý. Cơ chế bất biến áp dụng
cho API, quyền filesystem vẫn cho phép tác nhân ngoài sửa file. Đọc và dedup phát hiện
thay đổi byte. copy_to có thể ghi một phần vào đích nếu lỗi giữa chừng, caller chỉ công bố
đích sau khi hàm thành công. Không bảo đảm chống tác nhân sửa file đồng thời có chủ đích.
Crash cấp process có thể để lại file .pending- hoặc artifact chưa có event.
Chưa có transaction xuyên hai store, fsync thư mục hay cam kết phục hồi mất điện.
Không tự dọn original hoặc pending của process khác.

record chỉ nhận locator/source identifier đã loại secrets và PHI từ caller.
Không lưu free-text exception, không ghi log nội dung. Các mã lỗi được hỗ trợ hiện tại
là read_error và invalid_input. Chính sách sanitization theo nguồn và cơ chế phục hồi
artifact mồ côi cần được review trước acquisition.

## ADR 05 — Acquisition và extraction offline trong Session 03

Luồng đã triển khai: `DocumentRequest → LocalDocumentAdapter → ArtifactStore →
ProvenanceStore → ArtifactStore.copy_to → format detection → HTML/PDF extractor →
PipelineResult`. Adapter nhận path riêng với `source_id`, `logical_key`, `locator`;
không suy ra identity từ tên file, không chuẩn hóa locator, không liệt kê filesystem.
Caller chịu trách nhiệm xác minh quyền truy cập và loại secrets/PHI khỏi thông tin nguồn.
`AcquisitionAdapter` và `Extractor` là hai protocol nhỏ; chưa có HTTP adapter.

Adapter nhận `.html`, `.htm`, `.pdf`, không phân biệt hoa thường, đọc binary và chỉ
ghi qua store Session 02. Mỗi lần gọi hợp lệ về identity/locator đều thử ghi một event,
kể cả byte trùng hoặc lỗi file. Kết quả nội bộ phân biệt missing/empty/unsupported/read/
storage/provenance errors; event giữ vocabulary cũ `read_error` hoặc `invalid_input`.
Identity/locator không hợp lệ không thể tạo event có căn cứ, nên trả lỗi rõ ràng.
Provenance ghi thất bại không được coi là acquisition thành công; artifact đã lưu
vẫn được giữ nguyên để điều tra. Chưa có transaction hoặc tự phục hồi artifact mồ côi.

Pipeline chỉ đọc lại artifact qua `copy_to` đã kiểm chứng checksum. Chữ ký `%PDF-`
được ưu tiên; suffix PDF vẫn chuyển tới PDF parser để báo PDF hỏng. HTML dùng hint
từ suffix, chấp nhận fragment/plain text; từ chối một số chữ ký binary phổ biến và
NUL không có Unicode BOM. Đây là nhận diện giới hạn, không phải bộ phân loại mọi
định dạng. Lệch suffix/chữ ký có warning, không đổi identity hay byte gốc.

`ExtractionResult` giữ loại tài liệu, tuple block có thứ tự, method/version/profile,
status, warnings/errors, metadata và thông tin trang/encoding nội bộ. Không deduplicate
text. `success` nghĩa là có text và không phát hiện phần mất trong phạm vi extractor;
không chứng nhận fidelity tuyệt đối. `partial` có text cùng phần mất/cấu trúc không
đáng tin cậy; `failed` không có block và có error. Lỗi parser không chứa exception
text tự do; lỗi từng trang/tài liệu không làm dừng các mục còn lại.

### Các profile có thể khôi phục

| Profile | Cấu hình cố định và giới hạn |
| --- | --- |
| `html-dom-v1` | BeautifulSoup + stdlib `html.parser`; bytes được parser nhận diện encoding, ghi encoding nội bộ; chuẩn hóa whitespace của HTML flow, giải entities, giữ `br` và `pre`. Duyệt DOM, h1–h6 giữ level; list item giữ độ sâu, có thể tách item trước/sau nested list để bảo toàn thứ tự. Bảng đơn giản dùng tab giữa ô, newline giữa hàng; bảng gộp ô, lồng nhau, không đều hoặc nội dung ô phức tạp có warning và `partial`. |
| `pdf-plain-v1` | `pypdf.PdfReader(strict=True)`, từ chối PDF mã hóa; `extract_text(extraction_mode="plain", orientations=(0,90,180,270))` theo chỉ số trang. Tách paragraph bằng dòng trống, giữ newline nội bộ, không nối từ ngắt dòng. Text origin cách nhau ít nhất 72 point trên cùng hàng (sai số 2 point) là dấu hiệu layout phức tạp và `partial`. Luôn có `pdf_layout_unverified`. |
| `offline-dispatch-v1` | Không chuyển đổi nội dung; tạo kết quả failed khi không nhận diện được định dạng hoặc extractor ném lỗi ngoài dự kiến. |

Version ghi cả phiên bản implementation `1.0` và dependency thực dùng. BeautifulSoup
được chọn để xử lý HTML không hoàn chỉnh mà không tự viết parser; pypdf đọc text layer
và sinh được fixture PDF trong test, không cần OCR hay dependency dựng PDF khác.

HTML loại script/style/head, nav/role navigation, form/control, template/noscript,
hidden/aria-hidden; giữ header/footer có thể chứa nội dung tài liệu. Không chạy JS,
CSS hay tải linked resources; CSS layout/visibility không được diễn giải. Ảnh, SVG,
canvas và media được bỏ với warning/partial; không suy diễn nội dung hình. Metadata
chỉ lấy từ title, html lang, meta author và trường ngày xuất bản tường minh. HTML hỏng
được parse best-effort; không đảm bảo cây DOM tương đương trình duyệt. Encoding tự
nhận diện có thể sai với file không khai báo; cần kiểm tra fidelity bằng mẫu đại diện.

PDF giữ số trang và khoảng block nửa mở `[block_start, block_end)` cho từng trang,
kể cả trang lỗi/rỗng. Trang không có text có warning; tất cả trang không có text thì
failed, không phân biệt chắc chắn trang trống với scan và không chạy OCR. Heuristic
layout có thể bỏ sót hoặc báo dư; không dựng lại cột, ô bảng, hình, heading hoặc danh
sách PDF. Font, thứ tự content stream và bố cục phức tạp có thể làm text sai/mất.
Ngày tạo PDF không được dùng làm ngày xuất bản, author string không tự tách tên.

### Record v0.1 và ranh giới export

`OfflinePipeline.process`/`process_many` trả kết quả trong bộ nhớ, không có exporter
hay manifest. Acquisition thất bại hoặc artifact không còn toàn vẹn không tạo record.
Thiếu `RecordRights.access_basis` từ caller thì giữ extraction nội bộ, trả warning
`record_not_built_missing_rights`. Khi caller cung cấp rights, pipeline dựng record
v0.1 (kể cả extraction failed), giữ nhãn scope/audience là `unknown`, gọi
`validate_record()` và chỉ trả record qua validation. `reuse=unknown` không cấp quyền
phân phối; permitted/restricted cần evidence theo schema cũ.

`source.context` chứa `provenance_event:<event_id>`, original reference là hash tương
đối với root của ArtifactStore. Pipeline giữ toàn bộ warnings/errors của extractor.
Schema v0.1 không có trường page count/boundary/encoding hay cấu trúc ô bảng: chúng
được giữ trong extraction nội bộ; record PDF thêm warning
`v0.1_page_boundaries_internal_only`. Không thêm trường trái schema hoặc tạo metadata,
nhãn, quyền truy cập giả. Structured Raw batch export và cách xuất thông tin trang
cần quyết định trong phiên sau; chưa thể coi đây là nghiệm thu toàn bộ MVP.
