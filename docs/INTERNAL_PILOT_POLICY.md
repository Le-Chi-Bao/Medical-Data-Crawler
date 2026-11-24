# Chính sách pilot nội bộ · Session 05B-1

Pilot chỉ dùng tài liệu đã được duyệt cho việc lưu trữ nội bộ, đánh giá trích xuất HTML/PDF, kiểm chứng SHA-256 và provenance, đo chất lượng, coverage và lỗi của pipeline. Có thể lưu bản ghi và kết quả đánh giá trong khu vực nội bộ đã phân quyền theo quyết định của reviewer.

Phạm vi này cấm dùng dữ liệu trong Medical RAG, tạo embeddings hoặc vector database, huấn luyện hoặc fine-tune model, công bố hoặc phân phối dataset, và tự động fetch/crawl nguồn thật. Quyết định phê duyệt thuộc reviewer có thẩm quyền.

## Điều kiện tiếp nhận từng tài liệu

| Điều kiện | Căn cứ cần có |
| --- | --- |
| Duyệt thủ công và còn hiệu lực | Trạng thái `approved_for_manual_pilot`, mã reviewer thật, thời điểm bắt đầu và hạn tái duyệt theo UTC. Kiểm tra trong khoảng `reviewed_at ≤ at < review_again_at`. |
| Truy cập thủ công | `terms.manual=allowed` kèm căn cứ áp dụng cho URL và cách truy cập. Khả năng mở trang công khai chỉ cho biết trang có thể được truy cập. |
| Byte gốc | `original_bytes.read` và `original_bytes.internal_storage` đều `allowed` với căn cứ bao phủ toàn bộ byte được nhận. |
| Văn bản trích xuất | `read` và `internal_storage` đều `allowed` cho `html_text` hoặc `pdf_text` theo đúng định dạng đã kiểm chứng. |
| Tài sản nhúng và bên thứ ba | `embedded_assets.status=cleared_for_internal_storage` có căn cứ bao phủ tài sản nhúng, bao gồm ảnh/media bên thứ ba, hoặc xác nhận chúng vắng mặt. Với media tải riêng, pilot không thực hiện yêu cầu mạng. |
| Privacy / PHI | Reviewer ghi nhận đã rà bản tài liệu và xử lý hết rủi ro trước khi đóng `privacy_review`. Từ chối tài liệu có rủi ro còn mở khỏi luồng thông thường và dùng quy trình xử lý đã phê duyệt nếu cần. |
| Định danh và định dạng | `source_id`, locator và định dạng quan sát được phải khớp mục review. Xác minh final URL, redirect và định dạng thực tế. Nếu URL hoặc định dạng thay đổi, dừng import và dùng quy trình duyệt ứng viên mới. |

Quyền đọc và lưu nội bộ chỉ áp dụng cho tài sản và hoạt động được ghi trong căn cứ. Quyền phân phối, quyền tái sử dụng và quyền AI có quyết định riêng. Pilot nội bộ có thể chạy khi các quyền nội bộ đã được xác minh và các quyền ngoài phạm vi còn bỏ ngỏ. Giữ `reuse=unknown` khi thiếu căn cứ và chỉ dùng `reuse=permitted` trong Structured Raw khi có quyền reuse được xác minh riêng. Không suy ra quyền sao chép, lưu nội bộ hoặc dùng lại từ việc tài liệu được đọc công khai.

## Quy trình phê duyệt và import

1. Reviewer điền [hồ sơ thẩm định](PILOT_APPROVAL_PACK.md) cho đúng tài liệu, hình thức truy cập và bản nội dung. Ghi nguồn căn cứ và điều kiện cho từng quyền. Khép các mục `access_terms`, `document_rights`, `embedded_assets` và `privacy_review` sau khi đã giải quyết.
2. Khi sửa registry, gọi `validate_registry()` để kiểm tra schema và căn cứ đã ghi. Dùng `validate_registry_update(previous, proposed, at=...)` với snapshot trước và thời điểm có hiệu lực của bản cập nhật để kiểm tra luồng trạng thái và lịch sử định danh. Giữ tham chiếu đến revision được duyệt trong hồ sơ.
3. Trước khi gọi adapter cục bộ, dùng `evaluate_internal_pilot_import(registry, source_id, url, document_type=..., at=...)` từ `medical_data_crawler.source_policy` với snapshot được duyệt, locator chính xác, định dạng đã xác minh (`html` hoặc `pdf`) và thời điểm import có múi giờ. Caller đối chiếu định dạng của bản thủ công với định dạng adapter sẽ xử lý. Helper kiểm tra điều kiện lưu original qua `allows_manual_import()` và quyền văn bản qua `allows_asset_use()`. `BLOCKED` dừng bước import. `ELIGIBLE` áp dụng riêng cho thao tác thủ công này theo căn cứ đã ghi.
4. Sau khi đủ điều kiện, dùng bản thủ công được phép lưu, bảo toàn toàn bộ byte, ghi locator đã duyệt và provenance, rồi kiểm tra SHA-256. Chỉ lưu kết quả extraction và đánh giá trong phạm vi được duyệt. Khi phát hiện thay đổi có ảnh hưởng đến quyết định, dừng tiếp nhận và chuyển hồ sơ về `needs_review`. [Kế hoạch pilot](PILOT_PLAN.md) · [Phiếu đánh giá](PILOT_EVALUATION.md)

Gate đọc quyết định từ snapshot tin cậy. Reviewer xác nhận nội dung căn cứ, thẩm quyền, định dạng, redirect, tài sản và privacy trước khi ghi phê duyệt. [Chính sách nguồn](SOURCE_POLICY.md)
