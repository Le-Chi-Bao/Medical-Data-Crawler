# Trạng thái chuẩn bị pilot · Session 05A

| Hạng mục | Trạng thái |
| --- | --- |
| Ứng viên trong registry | 16, gồm NCI 5, NIAMS 6 và NHS 5. |
| Hàng chờ review | 16 mục `needs_review`, 0 mục ở trạng thái `candidate`. |
| Đã duyệt | 0 thủ công, 0 tự động. |
| Bị bác bỏ | 0. |
| Original y khoa đã import hoặc đánh giá | 0. Chất lượng extraction và coverage thực tế đều `NOT MEASURED`. |

Registry dựa trên URL và đầu mối chính sách được cung cấp. Terms of Service, robots.txt, quyền lưu original, giấy phép văn bản/media, các điều kiện dùng cho AI và ngoại lệ theo từng tài liệu còn chờ review. PDF có thể chứa ảnh hoặc thành phần bên thứ ba. NCI và NIAMS cần thêm căn cứ điều khoản truy cập đã xác minh. NHS có đầu mối điều khoản và danh mục ngoại lệ cần đối chiếu. Mọi nguồn đều có `automated_acquisition=unknown` và gate đóng. Xem [registry](../config/source_candidates.v0.1.json) và [chính sách](SOURCE_POLICY.md).

Ứng viên theo giả thuyết tuyển mẫu có K01: 3, K02: 2, K03: 5, K04: 4, K05: 4, K06: 0, K07: 6 và K08: 4. K06 cần ứng viên mới, K02 thiếu tổng quan hình thái nguyên phát/thứ phát. PDF có text layer, PDF nhiều cột/bảng, HTML với cấu trúc lồng nhau, trường metadata thiếu và cặp phiên bản chưa có mẫu thật đã kiểm chứng. Dùng [ma trận corpus](PILOT_PLAN.md) và [phiếu đánh giá](PILOT_EVALUATION.md) khi có tập approved.

## Quyết định trước khi tiếp nhận tài liệu thật

1. Chỉ định người review và duyệt từng tài liệu cho pilot thủ công hoặc fetch tự động. Chốt phạm vi đọc, lưu byte gốc, trích xuất, lưu nội bộ, tái sử dụng, phân phối và AI. Chốt ngoại lệ tài sản nhúng, quyền bên thứ ba và lịch tái review.
2. Duyệt bộ mẫu, cách xử lý khoảng trống K06/PDF layout, quy tắc định danh và quy trình từ chối/cách ly dữ liệu nhạy cảm. Chốt phân quyền, lưu giữ và nơi ghi căn cứ hoặc annotation để giữ original và provenance an toàn.
3. Trước HTTP, xác nhận điều khoản tự động, robots cho từng URL và user agent, giới hạn truy cập, cách xử lý redirect và lỗi, cũng như thời điểm dừng và review lại. Chỉ sử dụng revision registry được duyệt với phạm vi cho phép đã ghi.
4. Mở phiên triển khai HTTP riêng sau khi có thẩm quyền. Tích hợp gate trước mỗi yêu cầu và đường dẫn chuyển hướng, kiểm tra an toàn transport và dữ liệu đầu vào, kiểm thử bằng fixture rồi duyệt đợt chạy thật. Các API offline của 05A chỉ đánh giá quyết định đã ghi trong registry.
