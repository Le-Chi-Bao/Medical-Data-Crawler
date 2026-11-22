# Structured Raw v0.1

Đây là đề xuất kỹ thuật cho review liên repo. [Schema trong package](../src/medical_data_crawler/schemas/structured-raw-0.1.json) xác định cấu trúc đầy đủ. [Fixture tối thiểu](../tests/fixtures/record.json) dùng nội dung tổng hợp `abc`.

Một record mô tả kết quả của một lần trích xuất từ một original hợp lệ. Caller đưa đối tượng JSON vào `medical_data_crawler.contract.validate_record`. Hàm trả về `None` khi hợp lệ và ném `RecordValidationError` khi vi phạm. Validator đọc schema cục bộ.

| Trường | Ý nghĩa và quy tắc |
| --- | --- |
| `schema_version`, `document_id` | Version là chuỗi `"0.1"`. ID logic do producer cấp và giữ lại qua các lần xử lý cùng tài liệu. Thay extractor hoặc lần chạy không tạo ID logic mới. Cách ánh xạ khóa nguồn cần được thống nhất trước acquisition. |
| `source` | Gồm nguồn, locator, thời điểm thu thập RFC 3339 có múi giờ và ngữ cảnh hoặc null. |
| `original` | Tham chiếu bất biến, media type, kích thước byte dương và 64 ký tự hex thường của SHA-256. Storage chịu trách nhiệm kiểm chứng tham chiếu và byte thực tế. |
| `content` | Mảng theo thứ tự đọc. Vị trí trong mảng xác định thứ tự, kể cả khi hai block có cùng văn bản. Mỗi block có loại, cấp cấu trúc hoặc null, cùng nguyên văn. Xác định nguồn block qua record cha. |
| `metadata` | Giữ khóa title, language, authors, published_on. Dùng null khi thiếu căn cứ. Ngày xuất bản dạng chuỗi có thể giữ mức chi tiết của nguồn, kể cả khi chỉ có năm. |
| `scope`, `scope_evidence` | `unknown` khi thiếu căn cứ, mảng rỗng khi đã xác định không có nhãn phù hợp, hoặc các nhãn K01–K08 không lặp. Mảng có nhãn cần căn cứ. |
| `audience`, `audience_evidence` | general, medical, mixed hoặc unknown. Phải có căn cứ cho ba nhãn xác định. |
| `extraction` | Trạng thái, phương pháp, phiên bản, mã profile cấu hình, warnings và errors. Profile phải trỏ tới cấu hình có thể khôi phục khi triển khai extractor. |
| `rights` | Ghi căn cứ truy cập và trạng thái reuse. Với permitted hoặc restricted phải có bằng chứng. unknown không cấp quyền phân phối. Producer phải kiểm tra chính sách thực tế. |

| Trạng thái | Content | Thông tin bắt buộc |
| --- | --- | --- |
| success | Ít nhất một block | Danh sách errors rỗng |
| partial | Ít nhất một block dùng được | Có warning mô tả phần thiếu |
| failed | Mảng rỗng | Có error và đủ source/original |

Các object từ chối khóa ngoài schema. Khi thay đổi cấu trúc, tạo schema có version mới, giữ validator cũ cho dữ liệu cũ và chạy fixtures của từng version trước tích hợp. Schema kiểm tra hình dạng một record. Việc kiểm tra ID ổn định giữa nhiều lần chạy, checksum khớp artifact và tính xác thực của căn cứ thuộc về storage và producer.
