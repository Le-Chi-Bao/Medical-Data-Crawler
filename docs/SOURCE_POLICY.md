# Chính sách nguồn cho pilot

[Registry v0.1](../config/source_candidates.v0.1.json) quản lý từng tài liệu ứng viên. `source_id` gắn với một URL HTTPS và định dạng dự kiến. `scope_candidates`, `audience_candidate` và `document_type` là giả thuyết để chọn mẫu. `copyright_policy_urls` và `access_terms_urls` là đầu mối kiểm tra do người dùng cung cấp. Căn cứ cho từng quyết định nằm trong trường `evidence_url` tương ứng. Một danh sách đầu mối rỗng cần được bổ sung khi review.

## Trạng thái và thẩm quyền

| Trạng thái | Ý nghĩa |
| --- | --- |
| `candidate` | Đã đề xuất, chờ đưa vào hàng review. |
| `needs_review` | Chờ xác minh hoặc tái duyệt trước khi import hay fetch. |
| `approved_for_manual_pilot` | Đã duyệt truy cập thủ công và lưu original nội bộ theo phạm vi ghi nhận. |
| `approved_for_automated_fetch` | Đã duyệt riêng việc lấy original tự động cho đúng URL và user agent. Truy cập thủ công vẫn cần `terms.manual=allowed`. |
| `rejected` | Đã bác bỏ và giữ lại mục để truy vết. |

Luồng duyệt là `candidate → needs_review → approved_for_manual_pilot` hoặc `approved_for_automated_fetch`. Có thể bác bỏ từ mọi trạng thái trước đó. Mục đã duyệt phải quay về `needs_review` trước khi thay đổi căn cứ, quyền hoặc loại phê duyệt. Giữ review trước đó khi quay về hàng chờ và ghi thời điểm review mới hơn khi duyệt lại. Mục mới bắt đầu ở `candidate` hoặc `needs_review`. `source_id`, URL và định dạng làm khóa nhận diện của mục hiện có. Nếu cần thay URL hoặc định dạng, giữ mục cũ trong lịch sử và lập mục mới để review.

Người có thẩm quyền lưu quyết định qua quy trình review của dự án. Ghi mã nội bộ `reviewer-…`, `reviewed_at` và `review_again_at` theo UTC, điền căn cứ đã đối chiếu và đóng các mục `pending_decisions` tương ứng. Thời điểm hết hạn do reviewer xác định. Tái duyệt ngay khi nhận thấy thay đổi về URL/redirect, Terms of Service, robots.txt, giấy phép, nội dung hoặc tài sản nhúng ảnh hưởng đến quyết định, user agent, phương thức hoặc mục đích sử dụng. Nếu phát hiện sai khác, đình chỉ sử dụng phê duyệt của snapshot cũ và đưa mục về `needs_review`.

## Phạm vi quyền

| Loại tài sản | Phạm vi cần review |
| --- | --- |
| `html_text`, `pdf_text` | Văn bản của tài liệu theo định dạng. |
| `original_bytes` | Toàn bộ byte nhận được. Lưu nội bộ đòi hỏi căn cứ bao phủ cả tài sản nhúng. |
| `images` | Hình ảnh, minh họa và đồ họa. |
| `external_media` | Media được liên kết hoặc tải riêng. Đánh giá từng URL riêng trước một yêu cầu HTTP. |
| `third_party_assets` | Tài sản có quyền thuộc bên thứ ba, kể cả tài sản nhúng ngay trong PDF hoặc HTML. |

Ghi riêng `read`, `internal_storage`, `reuse`, `distribute` và `ai_use` cho từng loại tài sản. Trạng thái thiếu hoặc `unknown` nghĩa là chưa xác minh. `restricted`, `denied` và `unknown` đều đóng gate cho hành động tương ứng. Mỗi quyết định đã biết cần URL căn cứ đã được reviewer đối chiếu. Dùng `restricted` cùng căn cứ khi quyền có điều kiện chưa được xử lý. Sử dụng cho AI cần cả `reuse` và `ai_use` được phép, với mục đích cụ thể nằm trong căn cứ đã duyệt.

Quyền lưu văn bản PDF chỉ áp dụng cho văn bản. Lưu PDF nguyên bản đòi hỏi quyền đọc và lưu `original_bytes`, cùng `embedded_assets.status=cleared_for_internal_storage` có căn cứ bao phủ tài sản nhúng hoặc xác nhận chúng vắng mặt. Quyết định lưu nội bộ này chỉ áp dụng cho original được review. Phân phối original, kể cả toàn bộ PDF, cần quyền `distribute` riêng với căn cứ bao phủ toàn bộ thành phần.

`terms.manual` và `terms.automated` ghi quyết định riêng và dùng căn cứ trong `access_terms_urls`. Đối với fetch tự động, reviewer còn phải đối chiếu `robots.txt` của đúng host cho đường dẫn và user agent đã ghi. Điều khoản truy cập, robots và quyền tác giả đều được kiểm tra riêng, kể cả với tài liệu được xác định là public domain.

## API offline

- `validate_registry()` kiểm tra JSON Schema và các ràng buộc về định danh, URL, quyền và căn cứ. `validate_registry_update()` kiểm tra snapshot đề xuất so với snapshot trước. Cả hai báo mã lỗi cố định.
- `allows_manual_import()` kiểm tra đúng source ID, URL, review còn hiệu lực, quyền đọc/lưu original, tài sản nhúng và điều khoản truy cập thủ công. Trước khi trích xuất và lưu Structured Raw, caller còn phải kiểm tra quyền đọc và lưu văn bản trích xuất cho đúng định dạng.
- `allows_automated_fetch()` yêu cầu thêm phê duyệt fetch tự động, điều khoản tự động và robots cho chính user agent đã duyệt. Sau này adapter phải kiểm tra từng yêu cầu và xử lý redirect như URL cần quyết định riêng.
- `allows_asset_use()` kiểm tra một hành động trên một loại tài sản đã tiếp nhận. Ba API quyền đều từ chối khi registry sai, nguồn chưa duyệt, URL không khớp chính xác, review hết hạn hoặc quyền cần thiết chưa được cấp. Truyền `at` có múi giờ và chọn snapshot đang có hiệu lực.

Registry là đầu vào tin cậy đã được review qua Git. Validator kiểm tra cấu trúc và tính nhất quán của căn cứ. Xác minh nội dung bằng chứng và thẩm quyền reviewer thuộc quy trình phê duyệt. Validator chỉ nhận locator dạng HTTPS công khai với hostname DNS và đường dẫn slug giới hạn, từ chối credentials, query, fragment, port, escape và các path có dấu hiệu định danh nhạy cảm. Quy tắc định dạng chỉ sàng lọc dấu hiệu thường gặp. Reviewer vẫn kiểm tra các slug và mã định danh trước khi lưu, giữ bí mật, dữ liệu bệnh nhân, đường dẫn nội bộ và nội dung nguyên bản ngoài registry và log. Khi URL cần query hoặc cấu trúc ngoài whitelist, đưa trường hợp đó vào review trước khi thêm nguồn.

Session 05A cung cấp gate cho caller. Adapter offline và `RecordRights` tiếp tục theo hợp đồng hiện hành. Caller pilot phải quyết định quyền trước khi gọi `LocalDocumentAdapter` và chỉ truyền locator công khai đã kiểm tra. Dữ liệu nghi chứa thông tin định danh cần được từ chối khỏi pipeline thông thường và chuyển xử lý theo quy trình cách ly được phê duyệt. Xem [hợp đồng dữ liệu](DATA_CONTRACT.md).
