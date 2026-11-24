# Trạng thái chuẩn bị pilot nội bộ · Session 05B-3

| Hạng mục | Trạng thái |
| --- | --- |
| Ứng viên trong registry | 18, gồm NCI 5, NIAMS 6, NHS 5 và CDC 2. |
| Hồ sơ ưu tiên | 8 hồ sơ đã soạn, chờ reviewer xác minh. |
| Hàng chờ review | 18 mục `needs_review`, 0 mục `candidate`. |
| Đã duyệt | 0 thủ công, 0 tự động. |
| Bị bác bỏ | 0. |
| Gate import thủ công | 18 `BLOCKED`, 0 `ELIGIBLE`. |
| Original y khoa đã import hoặc đánh giá | 0. Chất lượng extraction, coverage thực tế và lỗi trên corpus thật đều `NOT MEASURED`. |
| HTML preflight ngoại tuyến | Đã kiểm tra bằng fixture tổng hợp. Original NIAMS Acne chưa được quét. Nguồn ở `needs_review`. |

Chưa có căn cứ đã xác minh cho redirect, định dạng thực tế, truy cập thủ công, quyền đọc/lưu byte gốc và văn bản, quyền tài sản nhúng và ảnh/media bên thứ ba, hoặc rà soát privacy/PHI. Mã reviewer, thời điểm review, hạn tái duyệt và quyết định cuối cùng còn thiếu. Các URL chính sách hiện dùng làm đầu mối cho reviewer. [Registry](../config/source_candidates.v0.1.json) · [Hồ sơ thẩm định](PILOT_APPROVAL_PACK.md)

Phân bổ nhãn dự kiến lần lượt từ K01 đến K08 là 3, 2, 5, 4, 4, 2, 6 và 4. Hai ứng viên CDC chỉ bổ sung khả năng đánh giá K06. K02 vẫn thiếu mẫu tổng quan tổn thương nguyên phát/thứ phát. Hồ sơ PDF NCI ghi nhận báo cáo chuyển hướng sang HTML và chờ reviewer xác minh lại. Chưa có PDF có text layer, PDF nhiều cột/bảng hoặc cặp phiên bản đã kiểm chứng. [Kế hoạch pilot](PILOT_PLAN.md) · [Phiếu đánh giá](PILOT_EVALUATION.md)

## Việc còn chờ trước khi nhận tài liệu thật

1. Chỉ định reviewer có thẩm quyền và xác minh căn cứ truy cập thủ công và quyền đọc bản gốc. Khi đã có bản HTML hợp pháp trên ổ cục bộ, dùng inspector để ghi checksum, trạng thái phân tích và dấu hiệu cần rà. [HTML preflight](HTML_PREFLIGHT.md)
2. Đối chiếu chứng cứ HTTP của đúng bản để xác minh đích cuối, redirect, status, Content-Type và header. Xác minh quyền đọc/lưu original và văn bản, quyền tài sản nhúng và bên thứ ba. Rà privacy/PHI và chốt nơi lưu giữ nội bộ cùng quyền truy cập.
3. Ghi quyết định, mã reviewer và hạn tái duyệt vào hồ sơ. Ghi quyền đã xác minh riêng theo tài sản và hành động. Nếu chưa có căn cứ reuse, giữ `reuse=unknown`.
4. Kiểm tra bản cập nhật registry và chỉ tiếp nhận bản thủ công khớp locator và định dạng khi gate offline trả `ELIGIBLE`. Đánh giá căn cứ pháp lý vẫn thuộc reviewer. [Chính sách pilot nội bộ](INTERNAL_PILOT_POLICY.md)
