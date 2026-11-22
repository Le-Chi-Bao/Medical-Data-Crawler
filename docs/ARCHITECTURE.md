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

Cần review cách cấp ID bền vững cho từng nguồn, schema của manifest, chính sách rights/PHI, quy tắc công bố storage và bộ mẫu HTML/PDF. Chưa có acquisition, artifact store, extractor, batch runner hay exporter. Các block dạng bảng ở v0.1 mang văn bản, chưa mô hình hóa ô và quan hệ hàng/cột.
