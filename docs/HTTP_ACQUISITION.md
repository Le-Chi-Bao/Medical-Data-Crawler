# Tiếp nhận tài liệu qua HTTPS

`HTTPDocumentAdapter` nhận từng `DocumentRequest` có `path=None`, `source_id`,
`logical_key` bền vững và `locator` là URL HTTPS đã duyệt. Caller chọn adapter khi
tạo `OfflinePipeline`. Tài liệu do nhân sự có thẩm quyền bàn giao vẫn dùng
`LocalDocumentAdapter` với đường dẫn cục bộ và locator đã loại thông tin nhạy cảm.

## Cấu hình và quyền truy cập

Caller bật mạng bằng `HTTPAcquisitionSettings(enabled=True, user_agent=...)` khi
khởi tạo adapter. Các giá trị sau là cấu hình Python của adapter.

| Tham số | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `enabled` | `False` | Cho phép truy cập mạng sau khi qua cổng phê duyệt |
| `user_agent` | `MedicalDataCrawler` | Token ASCII gửi nguyên dạng và so khớp chính xác với review robots |
| `connect_timeout` | 5 giây | Ngân sách chung cho TCP và TLS |
| `read_timeout` | 10 giây | Thời gian chờ mỗi lần đọc socket hoặc gửi request |
| `request_timeout` | 30 giây | Deadline cho mỗi kết nối TCP/TLS và phản hồi, tính cả header và body |
| `max_bytes` | 16 MiB | Giới hạn phần thân phản hồi, cấu hình tối đa 128 MiB |
| `max_redirects` | 3 | Số lần chuyển hướng tối đa, giới hạn cấu hình 0–5 |
| `max_retries` | 2 | Số lần thử lại chung cho cả chuỗi, giới hạn cấu hình 0–4 |
| `min_host_interval` | 1 giây | Khoảng nghỉ sau mỗi lần thử trên cùng host trong một adapter, cấu hình từ 0,01 đến 60 giây |

Để bật một website trong tương lai, lập mục registry cho từng URL theo quy trình
review của dự án. Reviewer cần ghi căn cứ Terms of Service, robots cho đúng User-Agent,
quyền đọc và lưu nội bộ `original_bytes`, phạm vi tài sản nhúng, kiểm tra quyền riêng
tư và thời điểm hết hạn. Dùng trạng thái `approved_for_automated_fetch` khi quyết
định review đã hoàn tất. Chuyển mục về `needs_review` theo quy trình khi căn cứ
thay đổi, rồi khởi tạo lại adapter bằng snapshot mới trước khi tiếp tục.
[Chính sách nguồn](SOURCE_POLICY.md)

Khởi tạo ở entry point của ứng dụng sau khi nạp snapshot registry đã duyệt.

```python
from medical_data_crawler.config import load_settings
from medical_data_crawler.http_acquisition import HTTPAcquisitionSettings, HTTPDocumentAdapter
from medical_data_crawler.logging_setup import configure_logging
from medical_data_crawler.pipeline import OfflinePipeline

configure_logging(load_settings())
adapter = HTTPDocumentAdapter(
    artifacts,
    provenance,
    reviewed_registry,
    settings=HTTPAcquisitionSettings(enabled=True, user_agent=reviewed_user_agent),
)
pipeline = OfflinePipeline(artifacts, adapter)
```

`allows_automated_fetch()` kiểm tra chính xác cặp source ID và URL, trạng thái,
căn cứ bắt buộc và thời hạn. Adapter kiểm tra trước DNS, trước khi mở kết nối
và ngay trước khi gửi GET. Mỗi URL chuyển hướng phải có mục được duyệt riêng
cho cùng định dạng và User-Agent. URL gửi đi dùng hostname DNS và đường dẫn slug
như registry. Credentials, query, fragment, escape, port tường minh và IP literal
bị từ chối.

Quyền lưu original cho phép adapter tiếp nhận tài liệu. Pipeline còn yêu cầu
quyền đọc và lưu nội bộ `html_text` hoặc `pdf_text` cho URL đầu và URL cuối
trước khi trích xuất. Caller cung cấp `RecordRights` có căn cứ để dựng record
v0.1 và để `reuse=unknown` khi chưa xác minh quyền tái sử dụng. Phê duyệt fetch
chỉ có hiệu lực trong phạm vi hành động đã ghi trong registry.

## Byte gốc và giới hạn phản hồi

Original là đúng các byte thân phản hồi HTTP `200` trong phạm vi `Content-Length`.
Header, status line và bản ghi framing TLS nằm ngoài original. Adapter yêu cầu
một `Content-Length` dương, đúng giới hạn, và một `Content-Type` khớp định dạng
được review là `text/html` hoặc `application/pdf`. Adapter gửi
`Accept-Encoding: identity`, chấp nhận `Content-Encoding` vắng mặt hoặc
`identity`, và lưu byte nguyên trạng. Chunked, phản hồi không xác định độ dài,
phản hồi range và các content encoding khác bị từ chối. Tham số charset trong
Content-Type không chuyển đổi byte lưu trữ. Bộ trích xuất HTML suy ra encoding
từ snapshot như luồng cục bộ.

Stream được đọc theo khối tối đa 64 KiB vào file tạm của ArtifactStore. Store
chỉ công bố file theo SHA-256 sau khi nhận đủ byte và kết thúc kết nối. Lỗi
trong lúc tải hủy file tạm. Provenance xác minh lại artifact và pipeline đọc
snapshot đã kiểm tra trước khi parse. Nếu lưu provenance thất bại sau khi
download thành công, original đầy đủ có thể còn trong store để điều tra.
Pipeline chỉ dựng record khi acquisition có event thành công.

## Kết nối, chuyển hướng và retry

Transport dùng kết nối TLS trực tiếp tới một IP số từ tập kết quả DNS đã kiểm tra.
Toàn bộ kết quả DNS phải là địa chỉ công khai được hỗ trợ. Cổng đích cố định 443.
TLS dùng hostname đã duyệt cho SNI và xác minh chứng chỉ từ CA bundle của
`certifi`. Transport dùng kết nối mới cho từng GET và bỏ qua proxy, CA override,
netrc và TLS key logging qua biến môi trường.

Adapter chỉ theo 301, 302, 303, 307 và 308, với URL HTTPS tuyệt đối hoặc đường
dẫn tuyệt đối trên host hiện tại. Mỗi hop được kiểm tra trước DNS và lưu dấu để
phát hiện vòng lặp. Body của phản hồi chuyển hướng và phản hồi lỗi không được
lưu. Retry áp dụng cho lỗi DNS/kết nối, timeout, đọc phản hồi không hoàn tất và
các status 408, 429, 500, 502, 503, 504. Backoff bắt đầu từ 0,5 giây và nhân đôi
mỗi lần. Adapter tôn trọng `Retry-After` hợp lệ đến 30 giây và dừng retry khi
giá trị này không hợp lệ hoặc yêu cầu chờ lâu hơn. Mọi lần thử lại và chuyển
hướng đều chịu throttle của host đích.

## Lỗi và provenance

| Mã | Tình huống |
| --- | --- |
| `http_disabled`, `http_authorization_denied` | Chưa bật hoặc chưa có phê duyệt hợp lệ |
| `http_invalid_identity`, `http_invalid_url` | Định danh hoặc locator không hợp lệ |
| `http_unsafe_address`, `http_connection_failure` | Kết quả DNS không an toàn hoặc lỗi DNS/kết nối |
| `http_tls_failure`, `http_timeout` | Lỗi TLS hoặc hết thời gian |
| `http_4xx`, `http_5xx`, `http_unexpected_status` | Phản hồi lỗi hoặc status ngoài hợp đồng |
| `http_redirect_rejected` | Chuyển hướng sai, không có quyền, vượt giới hạn hoặc tạo vòng lặp |
| `http_unsupported_media_type`, `http_unexpected_content_encoding` | Định dạng hoặc encoding chưa được hỗ trợ |
| `http_unsupported_framing`, `http_response_too_large`, `http_incomplete_response` | Framing không được hỗ trợ, quá giới hạn hoặc đọc thiếu |
| `http_storage_failure`, `http_provenance_failure` | Lỗi lưu artifact hoặc ghi sự kiện |

Event nội bộ vẫn dùng trạng thái và mã lỗi v0.1 chung. Trường `http` bổ sung
User-Agent, mã kết quả và danh sách lần thử có thời điểm, URL đã review và
status nếu đã nhận header. Đầu vào không quy được về đúng mục trong snapshot
hợp lệ trả mã lỗi mà không ghi locator. Adapter không ghi log nội dung, exception
text, response header hay URL bị từ chối. Khi dùng pipeline, gọi
`configure_logging()` ở entry point để chặn logger của parser chuyển chẩn đoán
vào root logger. Ứng dụng tự gắn handler trực tiếp cho parser hoặc log request
chịu trách nhiệm lọc dữ liệu trước khi ghi.

## Giới hạn vận hành

Deadline áp dụng sau DNS. DNS dùng resolver hệ điều hành và chịu timeout của
môi trường triển khai. Throttle chỉ áp dụng trong một adapter và không điều phối
nhiều process. Snapshot là bằng chứng phê duyệt tĩnh. Việc cập nhật robots,
Terms of Service và kiểm tra PHI trong tài liệu thuộc quy trình review, không
diễn ra trong mỗi lần fetch. Production cần kiểm soát DNS và egress phù hợp
với hạ tầng. Giới hạn byte tải không thay thế giới hạn tài nguyên của parser
HTML/PDF.

Demo và tests dùng dữ liệu tổng hợp, DNS và transport giả lập. Chạy
`python scripts/demo_http_acquisition.py` để xem luồng kiểm chứng end-to-end.
[Hướng dẫn phát triển](DEVELOPMENT.md#kiểm-tra-http-acquisition-ngoại-tuyến)
