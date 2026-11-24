# Kế hoạch corpus pilot

Pilot có tối đa 16 tài liệu được chọn từ 18 ứng viên. Registry ghi nhận 17 HTML và 1 PDF theo định dạng dự kiến. Tám hồ sơ ưu tiên gồm sáu mục NCI, NIAMS và NHS cùng hai ứng viên CDC bổ sung riêng cho K06. Mọi mô tả dạng tài liệu, bố cục và phạm vi dưới đây là giả thuyết tuyển mẫu. [Registry ứng viên](../config/source_candidates.v0.1.json) · [Hồ sơ thẩm định](PILOT_APPROVAL_PACK.md)

Pilot dùng bản thủ công đã được duyệt để lưu nội bộ, đánh giá extraction HTML/PDF, kiểm chứng SHA-256/provenance và đo chất lượng, coverage và lỗi. [Chính sách pilot nội bộ](INTERNAL_PILOT_POLICY.md)

## Ma trận tuyển mẫu

| Đặc tính cần đánh giá | Ứng viên để kiểm tra khi được duyệt | Tình trạng |
| --- | --- | --- |
| HTML đơn giản | NHS moles, skin tags | Chưa xác nhận DOM hoặc độ dài. |
| HTML phức tạp | NCI PDQ bản chuyên môn, các trang điều trị NIAMS | Kiểm tra nhiều phần, trích dẫn, thành phần điều hướng và vùng nội dung chính. |
| Danh sách và tiêu đề lồng nhau | NCI PDQ và NHS melanoma | Kiểm tra cấp heading và danh sách trên original. |
| PDF có text layer | NCI `anyone-can-get-skin-cancer.pdf` | Có báo cáo redirect sang HTML, `NOT VERIFIED`. Chặn import và giữ định danh PDF hiện có. |
| PDF nhiều cột hoặc bảng | Chưa có ứng viên được xác nhận | Nếu thiếu mẫu PDF phù hợp, đề xuất ứng viên mới với định danh riêng và review trong giới hạn pilot. |
| Metadata thiếu hoặc mơ hồ | Kiểm tra trên các original được duyệt | Chọn trường hợp thiếu tác giả, ngày hoặc ngôn ngữ và ghi căn cứ giữ `null`. |
| Bản sửa đổi | Hai snapshot hợp lệ của cùng mục NCI hoặc NIAMS nếu có | Chưa có cặp original đã xác minh. Giữ cùng ID logic, từng checksum và từng sự kiện provenance. |
| Đa dạng bệnh da | NCI/NHS ung thư, NHS moles/skin tags, NIAMS acne/atopic dermatitis/psoriasis/pemphigus | Bao gồm ứng viên cho ung thư, tổn thương lành tính, bệnh viêm và tự miễn. |

## Phân bổ dự kiến theo phạm vi

Một tài liệu có thể xuất hiện ở nhiều hàng. Số lượng lấy từ `scope_candidates` và dùng để ưu tiên review.

| Phạm vi | Ứng viên | Mẫu hoặc khoảng trống |
| --- | ---: | --- |
| K01 Hình thái | 3 | NHS moles, skin tags và triệu chứng melanoma. |
| K02 Phân loại | 2 | NHS moles và skin tags để kiểm tra mô tả phân loại. Chưa có mẫu tổng quan hệ phân loại nguyên phát/thứ phát. |
| K03 Biểu hiện | 5 | Các trang tổng quan NIAMS và triệu chứng melanoma của NHS. |
| K04 Nguy cơ/căn nguyên | 4 | NCI phòng ngừa và các trang tổng quan NIAMS. |
| K05 Chẩn đoán | 4 | NCI screening, NHS xét nghiệm và NIAMS chẩn đoán/điều trị. |
| K06 Chẩn đoán phân biệt | 2 | CDC TMVII và CDC Monkeypox. Reviewer cần xác nhận phạm vi từ đoạn có căn cứ sau khi tài liệu được duyệt. |
| K07 Quản lý/điều trị | 6 | NCI PDQ, NHS điều trị melanoma và các trang NIAMS. |
| K08 Phòng ngừa/giáo dục | 4 | NCI phòng ngừa, booklet và hai bài NHS. |

## Trình tự pilot sau khi được duyệt

1. Chọn tập mẫu và ghi rõ khoảng trống. Duyệt từng tài liệu cho manual pilot, bao gồm quyền cho original, văn bản trích xuất, tài sản và privacy. [Chính sách pilot nội bộ](INTERNAL_PILOT_POLICY.md)
2. Chốt ánh xạ một `source_id` cho mỗi tài liệu, dùng một `logical_key` cố định cho tài liệu đó qua các phiên bản. Dùng URL công khai đã duyệt làm `locator`. Ghi phiên bản registry và thông tin review làm căn cứ bên ngoài Structured Raw.
3. Kiểm tra gate offline với đúng `source_id`, locator, định dạng và thời điểm import. Khi nhận `ELIGIBLE`, giữ nguyên byte và lưu sự kiện nguồn theo pipeline offline. Nếu URL, định dạng, điều khoản, nội dung hoặc thành phần nhúng ảnh hưởng đến phê duyệt, đưa mục về review trước khi sử dụng bản mới. Dùng hash và sự kiện để phân biệt các phiên bản.
4. Review nhãn theo đoạn/trang thật và ghi locator căn cứ vào phiếu đánh giá. Khi chưa đủ căn cứ, giữ `unknown`. Dùng quy trình [đánh giá extraction](PILOT_EVALUATION.md) trên tập original được duyệt và ghi riêng các thiếu hụt của corpus.
