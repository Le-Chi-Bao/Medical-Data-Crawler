# Trạng thái chuẩn bị pilot nội bộ · Session 05B-1

| Hạng mục | Trạng thái |
| --- | --- |
| Ứng viên trong registry | 18, gồm NCI 5, NIAMS 6, NHS 5 và CDC 2. |
| Hồ sơ ưu tiên | 8 hồ sơ đã soạn, chờ reviewer xác minh. |
| Hàng chờ review | 18 mục `needs_review`, 0 mục `candidate`. |
| Đã duyệt | 0 thủ công, 0 tự động. |
| Bị bác bỏ | 0. |
| Gate import thủ công | 18 `BLOCKED`, 0 `ELIGIBLE`. |
| Original y khoa đã import hoặc đánh giá | 0. Chất lượng extraction, coverage thực tế và lỗi trên corpus thật đều `NOT MEASURED`. |

Chưa có căn cứ đã xác minh cho redirect, định dạng thực tế, truy cập thủ công, quyền đọc/lưu byte gốc và văn bản, quyền tài sản nhúng và ảnh/media bên thứ ba, hoặc rà soát privacy/PHI. Mã reviewer, thời điểm review, hạn tái duyệt và quyết định cuối cùng còn thiếu. Các URL chính sách hiện dùng làm đầu mối cho reviewer. [Registry](../config/source_candidates.v0.1.json) · [Hồ sơ thẩm định](PILOT_APPROVAL_PACK.md)

Phân bổ nhãn dự kiến lần lượt từ K01 đến K08 là 3, 2, 5, 4, 4, 2, 6 và 4. Hai ứng viên CDC chỉ bổ sung khả năng đánh giá K06. K02 vẫn thiếu mẫu tổng quan tổn thương nguyên phát/thứ phát. Hồ sơ PDF NCI ghi nhận báo cáo chuyển hướng sang HTML và chờ reviewer xác minh lại. Chưa có PDF có text layer, PDF nhiều cột/bảng hoặc cặp phiên bản đã kiểm chứng. [Kế hoạch pilot](PILOT_PLAN.md) · [Phiếu đánh giá](PILOT_EVALUATION.md)

## Việc còn chờ trước khi nhận tài liệu thật

1. Chỉ định reviewer có thẩm quyền. Đối chiếu URL cuối, redirect, định dạng và căn cứ cho truy cập thủ công, quyền đọc/lưu original, quyền đọc/lưu văn bản, tài sản nhúng và quyền bên thứ ba theo từng tài liệu.
2. Rà privacy/PHI, chốt nơi lưu giữ nội bộ và quyền truy cập, ghi quyết định, mã reviewer và hạn tái duyệt vào hồ sơ. Ghi quyền được xác minh riêng theo tài sản và hành động. Nếu chưa có căn cứ reuse, giữ `reuse=unknown`.
3. Kiểm tra bản cập nhật registry và chỉ tiếp nhận bản thủ công khớp locator và định dạng khi gate offline trả `ELIGIBLE`. Schema và kiểm thử chỉ xác nhận cấu trúc và hành vi gate. Đánh giá căn cứ pháp lý vẫn thuộc reviewer. [Chính sách pilot nội bộ](INTERNAL_PILOT_POLICY.md)
