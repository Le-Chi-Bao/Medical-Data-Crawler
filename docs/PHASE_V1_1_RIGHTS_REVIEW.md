# Phase V1.1 — review quyền từng tài liệu

Ngày kiểm tra: **26/11/2026**. Đây là metadata nghiên cứu; không chứa original/toàn văn hay hồ sơ approval riêng tư.

Đã thử lại cả 15 ứng viên cũ, mở được 14 trang chính thức (1 trang chỉ là công văn), 1 timeout. Bổ sung 8 hồ sơ, tổng 23. Ba PDF được đề xuất `eligible` theo bằng chứng CC BY-SA, nhưng **operator chưa phê duyệt rights review/terms/acquisition**. Vì vậy `status` vẫn `pending_review` và manifest import không có quyền hoạt động. Nguồn Huế có NC/ND là `restricted` cho workflow đề xuất.

Bằng chứng license là trang áp giấy phép cho bài cụ thể, không chỉ trang Creative Commons. Đọc lại [legal code](https://creativecommons.org/licenses/by-sa/4.0/legalcode.en), [chính sách gửi bài](https://thaibinhjmp.vn/index.php/ojstbump/about/submissions) và [quy định](https://thaibinhjmp.vn/index.php/ojstbump/quy_dinh_quy_trinh) trước khi duyệt. Hướng dẫn thể lệ nhúng Drive chưa review; chưa thấy rào cản trên đường dẫn PDF công khai đã đọc.

Các quyền trong bảng là **căn cứ giấy phép đề xuất**, không phải trusted grant. Unknown vẫn chờ review. Không suy NC/ND đồng nghĩa cấm mọi TDM nội bộ; không chọn khi chưa giải quyết điều kiện. Không suy rằng quyền phát hành lại có ghi nguồn của website là giấy phép cho mọi tài sản hoặc mục đích AI.

JSON máy đọc tương ứng: [vietnamese-medical-rights-review.v1.1.json](../config/vietnamese-medical-rights-review.v1.1.json). Batch vận hành chưa kích hoạt: [vietnamese-medical-batch.v1.1.json](../config/vietnamese-medical-batch.v1.1.json).

## Tổng quan

| ID | Đề xuất | Trạng thái vận hành | Định dạng/ngôn ngữ | Phạm vi |
|---|---|---|---|---|
| `vn-guideline-2023` | pending_review | pending_review | pdf / not_reverified_fulltext_vi | K07 |
| `vn-melanoma-targeted` | pending_review | pending_review | html / vi | K03, K07 |
| `vn-skin-cancer-updates` | pending_review | pending_review | html / vi | K05, K07, K08 |
| `vn-bcc-diagnosis` | pending_review | pending_review | html / vi | K03, K04, K05, K07 |
| `vn-self-skin-check` | pending_review | pending_review | html / not_reverified_fulltext_vi | K01, K08 |
| `vn-moles-reference` | pending_review | pending_review | html / vi | K01, K02, K03, K06 |
| `vn-moles-warning` | pending_review | pending_review | html / vi | K01, K03, K08 |
| `vn-bcc-quyhoa` | pending_review | pending_review | html / vi | K01, K02, K03, K04, K05, K07, K08 |
| `vn-melanoma-prognosis` | pending_review | pending_review | pdf / not_reverified_fulltext_vi | K01, K03, K05 |
| `vn-bcc-reconstruction` | pending_review | pending_review | pdf / vi | K07 |
| `vn-skin-cancer-signs` | pending_review | pending_review | html / vi | K01, K03, K08 |
| `vn-skin-cancer-early` | pending_review | pending_review | html / vi | K03, K08 |
| `vn-seborrheic-keratosis` | pending_review | pending_review | html / vi | K01, K02, K04, K06, K07 |
| `vn-melanoma-histology` | pending_review | pending_review | pdf / not_reverified_fulltext_vi | K03, K05 |
| `vn-acs-skin-check` | pending_review | pending_review | pdf / vi | K01, K03, K08 |
| `vn-tbjmp-atopic-488` | eligible | pending_review | pdf / vi | K01, K03, K04 |
| `vn-tbjmp-acne-490` | eligible | pending_review | pdf / vi | K01, K02, K03, K04 |
| `vn-tbjmp-psoriasis-640` | eligible | pending_review | pdf / vi | K01, K03, K07 |
| `vn-tbjmp-atopic-qol-425` | pending_review | pending_review | pdf / vi_abstract_verified_fulltext_not_reverified | K03 |
| `vn-tbjmp-psoriasis-qol-367` | pending_review | pending_review | pdf / vi_abstract_verified_fulltext_not_reverified | K03 |
| `vn-tbjmp-acne-tcm-507` | pending_review | pending_review | pdf / vi_abstract_verified_fulltext_not_reverified | K01, K02, K03 |
| `vn-hue-skin-spectrum-2271` | restricted | restricted | pdf / vi_abstract_verified_fulltext_not_reverified | unknown |
| `vn-vjdv-immunotherapy-154` | pending_review | pending_review | pdf / vi_abstract_verified_fulltext_not_reverified | K02, K04, K07 |

## vn-guideline-2023

**Tiêu đề:** Hướng dẫn Chẩn đoán và điều trị các bệnh Da liễu

**Đơn vị đăng/xuất bản:** Bộ Y tế. **Tác giả/đơn vị gốc:** Bộ Y tế; nguồn đăng công văn: Sở Y tế Đồng Nai.

**Nguồn:** [Trang chính thức](https://syt.dongnai.gov.vn/vi/van-ban/detail/V-v-trien-khai-thuc-hien-Quyet-dinh-so-4416-QD-BYT-ngay-06-thang-12-nam-2023-cua-Bo-truong-Bo-Y-te-9469/). **Định dạng:** pdf; **ngôn ngữ:** `not_reverified_fulltext_vi`; **truy cập:** `opened_notice_only`.

**Copyright/license:** unknown; không suy luận public domain/open license.

**Bằng chứng:** [Nguồn 1](https://syt.dongnai.gov.vn/vi/van-ban/detail/V-v-trien-khai-thuc-hien-Quyet-dinh-so-4416-QD-BYT-ngay-06-thang-12-nam-2023-cua-Bo-truong-Bo-Y-te-9469/).

| Thao tác | Quyền/căn cứ |
|---|---|
| Tải PDF/HTML | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| Lưu byte original | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| Trích xuất và lưu text | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| RAG/indexing nội bộ dự kiến | Chưa xác minh; không được phép vận hành từ hồ sơ này |

**Tài sản bên thứ ba và hạn chế:** Trang thực tế là công văn 7556/SYT-NV ngày 14/12/2023 của Sở Y tế, có dk-7556.pdf và 7556-nv.pdf; chưa xác minh byte phụ lục là toàn bộ hướng dẫn 4416. Không coi công văn là chính tài liệu hướng dẫn.

**Phạm vi:** K07. Nguồn: https://syt.dongnai.gov.vn/vi/van-ban/detail/V-v-trien-khai-thuc-hien-Quyet-dinh-so-4416-QD-BYT-ngay-06-thang-12-nam-2023-cua-Bo-truong-Bo-Y-te-9469/; chủ đề đã đối chiếu: K07. Xem review_notes về mức xác minh.

**Kết luận:** trạng thái `pending_review`; đề xuất `pending_review`. Trang thực tế là công văn 7556/SYT-NV ngày 14/12/2023 của Sở Y tế, có dk-7556.pdf và 7556-nv.pdf; chưa xác minh byte phụ lục là toàn bộ hướng dẫn 4416. Không coi công văn là chính tài liệu hướng dẫn.

**File original/SHA-256:** chưa có. **Human review chất lượng:** chưa bắt đầu; **RAG ready:** false.

## vn-melanoma-targeted

**Tiêu đề:** Điều trị đích trong Ung thư hắc tố ở người Việt Nam

**Đơn vị đăng/xuất bản:** Bệnh viện Da liễu Trung ương. **Tác giả/đơn vị gốc:** Bệnh viện Da liễu Trung ương.

**Nguồn:** [Trang chính thức](https://dalieu.vn/dieu-tri-dich-trong-ung-thu-hac-to-o-nguoi-viet-nam-6048.html). **Định dạng:** html; **ngôn ngữ:** `vi`; **truy cập:** `opened`.

**Copyright/license:** unknown; không suy luận public domain/open license.

**Bằng chứng:** [Nguồn 1](https://dalieu.vn/dieu-tri-dich-trong-ung-thu-hac-to-o-nguoi-viet-nam-6048.html).

| Thao tác | Quyền/căn cứ |
|---|---|
| Tải PDF/HTML | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| Lưu byte original | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| Trích xuất và lưu text | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| RAG/indexing nội bộ dự kiến | Chưa xác minh; không được phép vận hành từ hồ sơ này |

**Tài sản bên thứ ba và hạn chế:** Footer có yêu cầu ghi nguồn khi sử dụng lại thông tin, chưa chứng minh phạm vi lưu toàn bộ, extract và RAG/ảnh. Giữ pending; không suy luận rằng mọi hình/bảng là của bệnh viện.

**Phạm vi:** K03, K07. Nguồn: https://dalieu.vn/dieu-tri-dich-trong-ung-thu-hac-to-o-nguoi-viet-nam-6048.html; chủ đề đã đối chiếu: K03, K07. Xem review_notes về mức xác minh.

**Kết luận:** trạng thái `pending_review`; đề xuất `pending_review`. Footer có yêu cầu ghi nguồn khi sử dụng lại thông tin, chưa chứng minh phạm vi lưu toàn bộ, extract và RAG/ảnh. Giữ pending; không suy luận rằng mọi hình/bảng là của bệnh viện.

**File original/SHA-256:** chưa có. **Human review chất lượng:** chưa bắt đầu; **RAG ready:** false.

## vn-skin-cancer-updates

**Tiêu đề:** MỘT SỐ CẬP NHẬT VỀ TIẾN BỘ TRONG CHẨN ĐOÁN VÀ ĐIỀU TRỊ UNG THƯ DA

**Đơn vị đăng/xuất bản:** Bệnh viện Da Liễu TP.HCM. **Tác giả/đơn vị gốc:** Bệnh viện Da Liễu TP.HCM.

**Nguồn:** [Trang chính thức](https://bvdl.org.vn/d-9777.0.33/kien-thuc-y-khoa/mot-so-cap-nhat-ve-tien-bo--trong-chan-doan-va-dieu-tri-ung-thu-da.html). **Định dạng:** html; **ngôn ngữ:** `vi`; **truy cập:** `opened`.

**Copyright/license:** unknown; không suy luận public domain/open license.

**Bằng chứng:** [Nguồn 1](https://bvdl.org.vn/d-9777.0.33/kien-thuc-y-khoa/mot-so-cap-nhat-ve-tien-bo--trong-chan-doan-va-dieu-tri-ung-thu-da.html).

| Thao tác | Quyền/căn cứ |
|---|---|
| Tải PDF/HTML | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| Lưu byte original | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| Trích xuất và lưu text | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| RAG/indexing nội bộ dự kiến | Chưa xác minh; không được phép vận hành từ hồ sơ này |

**Tài sản bên thứ ba và hạn chế:** Đã mở bài ngày 23/06/2023; có PDF báo cáo tại admin.bvdl.org.vn, liên kết HTTP. Chưa kiểm tra giấy phép slide/hình; không tự đổi HTTP thành HTTPS.

**Phạm vi:** K05, K07, K08. Nguồn: https://bvdl.org.vn/d-9777.0.33/kien-thuc-y-khoa/mot-so-cap-nhat-ve-tien-bo--trong-chan-doan-va-dieu-tri-ung-thu-da.html; chủ đề đã đối chiếu: K05, K07, K08. Xem review_notes về mức xác minh.

**Kết luận:** trạng thái `pending_review`; đề xuất `pending_review`. Đã mở bài ngày 23/06/2023; có PDF báo cáo tại admin.bvdl.org.vn, liên kết HTTP. Chưa kiểm tra giấy phép slide/hình; không tự đổi HTTP thành HTTPS.

**File original/SHA-256:** chưa có. **Human review chất lượng:** chưa bắt đầu; **RAG ready:** false.

## vn-bcc-diagnosis

**Tiêu đề:** UNG THƯ BIỂU MÔ TẾ BÀO ĐÁY – CHẨN ĐOÁN VÀ ĐIỀU TRỊ

**Đơn vị đăng/xuất bản:** Bệnh viện Da Liễu TP.HCM. **Tác giả/đơn vị gốc:** Bệnh viện Da Liễu TP.HCM.

**Nguồn:** [Trang chính thức](https://bvdl.org.vn/cong-dong/d-11422.1768.33/kien-thuc-y-khoa/ung-thu-bieu-mo-te-bao-day--chan-doan-va-dieu-tri.html). **Định dạng:** html; **ngôn ngữ:** `vi`; **truy cập:** `opened_corrected_url`.

URL trong snapshot V1: [nguồn cũ](https://bvdl.org.vn/cong-dong/d-11422.0.33/tin-tuc-benh-vien/ung-thu-bieu-mo-te-bao-day--chan-doan-va-dieu-tri.html).

**Copyright/license:** unknown; không suy luận public domain/open license.

**Bằng chứng:** [Nguồn 1](https://bvdl.org.vn/cong-dong/d-11422.1768.33/kien-thuc-y-khoa/ung-thu-bieu-mo-te-bao-day--chan-doan-va-dieu-tri.html).

| Thao tác | Quyền/căn cứ |
|---|---|
| Tải PDF/HTML | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| Lưu byte original | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| Trích xuất và lưu text | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| RAG/indexing nội bộ dự kiến | Chưa xác minh; không được phép vận hành từ hồ sơ này |

**Tài sản bên thứ ba và hạn chế:** URL cũ timeout; URL chính thức thay thế đã mở, bài ngày 27/10/2025, tư vấn Đặng Hùng Anh. Có PDF chính thức, footer yêu cầu ghi nguồn khi phát hành lại; chưa xác minh mọi tài sản và dùng RAG.

**Phạm vi:** K03, K04, K05, K07. Nguồn: https://bvdl.org.vn/cong-dong/d-11422.0.33/tin-tuc-benh-vien/ung-thu-bieu-mo-te-bao-day--chan-doan-va-dieu-tri.html; chủ đề đã đối chiếu: K03, K04, K05, K07. Xem review_notes về mức xác minh.

**Kết luận:** trạng thái `pending_review`; đề xuất `pending_review`. URL cũ timeout; URL chính thức thay thế đã mở, bài ngày 27/10/2025, tư vấn Đặng Hùng Anh. Có PDF chính thức, footer yêu cầu ghi nguồn khi phát hành lại; chưa xác minh mọi tài sản và dùng RAG.

**File original/SHA-256:** chưa có. **Human review chất lượng:** chưa bắt đầu; **RAG ready:** false.

## vn-self-skin-check

**Tiêu đề:** LÀM THẾ NÀO ĐỂ TỰ KIỂM TRA UNG THƯ DA?

**Đơn vị đăng/xuất bản:** Bệnh viện Da Liễu TP.HCM. **Tác giả/đơn vị gốc:** Bệnh viện Da Liễu TP.HCM; quyền tài sản gốc chưa xác minh.

**Nguồn:** [Trang chính thức](https://bvdl.org.vn/d-7395.5.12/truyen-thong-giao-duc-suc-khoe/lam-the-nao-de-tu-kiem-tra-ung-thu-da.html). **Định dạng:** html; **ngôn ngữ:** `not_reverified_fulltext_vi`; **truy cập:** `timeout`.

**Copyright/license:** unknown; không suy luận public domain/open license.

**Bằng chứng:** [Nguồn 1](https://bvdl.org.vn/d-7395.5.12/truyen-thong-giao-duc-suc-khoe/lam-the-nao-de-tu-kiem-tra-ung-thu-da.html).

| Thao tác | Quyền/căn cứ |
|---|---|
| Tải PDF/HTML | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| Lưu byte original | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| Trích xuất và lưu text | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| RAG/indexing nội bộ dự kiến | Chưa xác minh; không được phép vận hành từ hồ sơ này |

**Tài sản bên thứ ba và hạn chế:** Mở lại timeout; kế thừa metadata từ Phase V1, chưa xác nhận live trong V1.1; không nâng mức xác minh.

**Phạm vi:** K01, K08. Nguồn: https://bvdl.org.vn/d-7395.5.12/truyen-thong-giao-duc-suc-khoe/lam-the-nao-de-tu-kiem-tra-ung-thu-da.html; chủ đề đã đối chiếu: K01, K08. Xem review_notes về mức xác minh.

**Kết luận:** trạng thái `pending_review`; đề xuất `pending_review`. Mở lại timeout; kế thừa metadata từ Phase V1, chưa xác nhận live trong V1.1; không nâng mức xác minh.

**File original/SHA-256:** chưa có. **Human review chất lượng:** chưa bắt đầu; **RAG ready:** false.

## vn-moles-reference

**Tiêu đề:** Nốt ruồi và những điều cần biết

**Đơn vị đăng/xuất bản:** Khoa Da Liễu – Thẩm Mỹ Da, Bệnh viện Đại học Y Dược TP.HCM. **Tác giả/đơn vị gốc:** Bệnh viện Đại học Y Dược TP.HCM; nguồn nội dung tham khảo/ảnh bên thứ ba.

**Nguồn:** [Trang chính thức](https://dalieudhyd.vn/not-ruoi-va-nhung-dieu-can-biet). **Định dạng:** html; **ngôn ngữ:** `vi`; **truy cập:** `opened`.

**Copyright/license:** unknown; không suy luận public domain/open license.

**Bằng chứng:** [Nguồn 1](https://dalieudhyd.vn/not-ruoi-va-nhung-dieu-can-biet).

| Thao tác | Quyền/căn cứ |
|---|---|
| Tải PDF/HTML | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| Lưu byte original | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| Trích xuất và lưu text | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| RAG/indexing nội bộ dự kiến | Chưa xác minh; không được phép vận hành từ hồ sơ này |

**Tài sản bên thứ ba và hạn chế:** Nội dung tiếng Việt đã đọc; dẫn DermNet/nguồn tham khảo. Thiếu giấy phép tái sử dụng bản dịch và ảnh.

**Phạm vi:** K01, K02, K03, K06. Nguồn: https://dalieudhyd.vn/not-ruoi-va-nhung-dieu-can-biet; chủ đề đã đối chiếu: K01, K02, K03, K06. Xem review_notes về mức xác minh.

**Kết luận:** trạng thái `pending_review`; đề xuất `pending_review`. Nội dung tiếng Việt đã đọc; dẫn DermNet/nguồn tham khảo. Thiếu giấy phép tái sử dụng bản dịch và ảnh.

**File original/SHA-256:** chưa có. **Human review chất lượng:** chưa bắt đầu; **RAG ready:** false.

## vn-moles-warning

**Tiêu đề:** Dấu hiệu nốt ruồi ung thư da

**Đơn vị đăng/xuất bản:** Khoa Da Liễu – Thẩm Mỹ Da, Bệnh viện Đại học Y Dược TP.HCM. **Tác giả/đơn vị gốc:** VnExpress; ảnh American Academy of Dermatology.

**Nguồn:** [Trang chính thức](https://dalieudhyd.vn/dau-hieu-not-ruoi-ung-thu-da). **Định dạng:** html; **ngôn ngữ:** `vi`; **truy cập:** `opened`.

**Copyright/license:** unknown; không suy luận public domain/open license.

**Bằng chứng:** [Nguồn 1](https://dalieudhyd.vn/dau-hieu-not-ruoi-ung-thu-da).

| Thao tác | Quyền/căn cứ |
|---|---|
| Tải PDF/HTML | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| Lưu byte original | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| Trích xuất và lưu text | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| RAG/indexing nội bộ dự kiến | Chưa xác minh; không được phép vận hành từ hồ sơ này |

**Tài sản bên thứ ba và hạn chế:** Trang đăng lại nội dung có nguồn VnExpress, ảnh American Academy of Dermatology. Cần quyền chủ sở hữu gốc/bản dịch/ảnh, không chỉ quyền đơn vị đăng lại.

**Phạm vi:** K01, K03, K08. Nguồn: https://dalieudhyd.vn/dau-hieu-not-ruoi-ung-thu-da; chủ đề đã đối chiếu: K01, K03, K08. Xem review_notes về mức xác minh.

**Kết luận:** trạng thái `pending_review`; đề xuất `pending_review`. Trang đăng lại nội dung có nguồn VnExpress, ảnh American Academy of Dermatology. Cần quyền chủ sở hữu gốc/bản dịch/ảnh, không chỉ quyền đơn vị đăng lại.

**File original/SHA-256:** chưa có. **Human review chất lượng:** chưa bắt đầu; **RAG ready:** false.

## vn-bcc-quyhoa

**Tiêu đề:** MỘT SỐ ĐIỀU CẦN BIẾT VỀ BỆNH UNG THƯ TẾ BÀO ĐÁY

**Đơn vị đăng/xuất bản:** Bệnh viện Da liễu Trung ương Quy Hòa. **Tác giả/đơn vị gốc:** Bệnh viện Da liễu Trung ương Quy Hòa.

**Nguồn:** [Trang chính thức](https://bvquyhoa.vn/mot-so-dieu-can-biet-ve-benh-ung-thu-te-bao-day/). **Định dạng:** html; **ngôn ngữ:** `vi`; **truy cập:** `opened`.

**Copyright/license:** unknown; không suy luận public domain/open license.

**Bằng chứng:** [Nguồn 1](https://bvquyhoa.vn/mot-so-dieu-can-biet-ve-benh-ung-thu-te-bao-day/).

| Thao tác | Quyền/căn cứ |
|---|---|
| Tải PDF/HTML | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| Lưu byte original | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| Trích xuất và lưu text | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| RAG/indexing nội bộ dự kiến | Chưa xác minh; không được phép vận hành từ hồ sơ này |

**Tài sản bên thứ ba và hạn chế:** Đã đối chiếu tiêu đề, BSCKI. Huỳnh Thanh Ban, ngày 15/11/2023; có ảnh lâm sàng. Chưa xác minh giấy phép cho original và ảnh.

**Phạm vi:** K01, K02, K03, K04, K05, K07, K08. Nguồn: https://bvquyhoa.vn/mot-so-dieu-can-biet-ve-benh-ung-thu-te-bao-day/; chủ đề đã đối chiếu: K01, K02, K03, K04, K05, K07, K08. Xem review_notes về mức xác minh.

**Kết luận:** trạng thái `pending_review`; đề xuất `pending_review`. Đã đối chiếu tiêu đề, BSCKI. Huỳnh Thanh Ban, ngày 15/11/2023; có ảnh lâm sàng. Chưa xác minh giấy phép cho original và ảnh.

**File original/SHA-256:** chưa có. **Human review chất lượng:** chưa bắt đầu; **RAG ready:** false.

## vn-melanoma-prognosis

**Tiêu đề:** NGHIÊN CỨU MỘT SỐ YẾU TỐ TIÊN LƯỢNG UNG THƯ HẮC TỐ DA TẠI BỆNH VIỆN K TỪ 2009 ĐẾN 2019

**Đơn vị đăng/xuất bản:** Tạp chí Y học Việt Nam. **Tác giả/đơn vị gốc:** Tạp chí Y học Việt Nam / tác giả bài nghiên cứu.

**Nguồn:** [Trang chính thức](https://tapchiyhocvietnam.vn/index.php/vmj/article/view/1394). **Định dạng:** pdf; **ngôn ngữ:** `not_reverified_fulltext_vi`; **truy cập:** `opened_english_metadata`.

**Copyright/license:** unknown; không suy luận public domain/open license.

**Bằng chứng:** [Nguồn 1](https://tapchiyhocvietnam.vn/index.php/vmj/article/view/1394).

| Thao tác | Quyền/căn cứ |
|---|---|
| Tải PDF/HTML | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| Lưu byte original | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| Trích xuất và lưu text | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| RAG/indexing nội bộ dự kiến | Chưa xác minh; không được phép vận hành từ hồ sơ này |

**Tài sản bên thứ ba và hạn chế:** DOI 10.51298/vmj.v507i2.1394; Vũ Thanh Phương, Nguyễn Văn Chủ, Nguyễn Đại Bình; ngày 28/10/2021. Trang hiện trả tiêu đề/abstract tiếng Anh; tiếng Việt toàn văn chưa xác minh trong phiên, chưa thấy license.

**Phạm vi:** K01, K03, K05. Nguồn: https://tapchiyhocvietnam.vn/index.php/vmj/article/view/1394; chủ đề đã đối chiếu: K01, K03, K05. Xem review_notes về mức xác minh.

**Kết luận:** trạng thái `pending_review`; đề xuất `pending_review`. DOI 10.51298/vmj.v507i2.1394; Vũ Thanh Phương, Nguyễn Văn Chủ, Nguyễn Đại Bình; ngày 28/10/2021. Trang hiện trả tiêu đề/abstract tiếng Anh; tiếng Việt toàn văn chưa xác minh trong phiên, chưa thấy license.

**File original/SHA-256:** chưa có. **Human review chất lượng:** chưa bắt đầu; **RAG ready:** false.

## vn-bcc-reconstruction

**Tiêu đề:** Tạo hình góc mắt trong sau cắt ung thư tế bào đáy bằng nhiều vạt tại chỗ: Loạt ca lâm sàng

**Đơn vị đăng/xuất bản:** Trường Đại học Y Hà Nội – Tạp chí Nghiên cứu Y học. **Tác giả/đơn vị gốc:** Trường Đại học Y Hà Nội – Tạp chí Nghiên cứu Y học / tác giả.

**Nguồn:** [Trang chính thức](https://tapchinghiencuuyhoc.vn/index.php/tcncyh/article/view/3670). **Định dạng:** pdf; **ngôn ngữ:** `vi`; **truy cập:** `opened`.

**Copyright/license:** unknown; không suy luận public domain/open license.

**Bằng chứng:** [Nguồn 1](https://tapchinghiencuuyhoc.vn/index.php/tcncyh/article/view/3670).

| Thao tác | Quyền/căn cứ |
|---|---|
| Tải PDF/HTML | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| Lưu byte original | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| Trích xuất và lưu text | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| RAG/indexing nội bộ dự kiến | Chưa xác minh; không được phép vận hành từ hồ sơ này |

**Tài sản bên thứ ba và hạn chế:** DOI 10.52852/tcncyh.v193i8.3670; Dương Mạnh Chiến, Lê Trung Thành; 29/08/2025. Có nút PDF; chưa có license reuse rõ, ảnh vùng mắt/ca bệnh cần review riêng.

**Phạm vi:** K07. Nguồn: https://tapchinghiencuuyhoc.vn/index.php/tcncyh/article/view/3670; chủ đề đã đối chiếu: K07. Xem review_notes về mức xác minh.

**Kết luận:** trạng thái `pending_review`; đề xuất `pending_review`. DOI 10.52852/tcncyh.v193i8.3670; Dương Mạnh Chiến, Lê Trung Thành; 29/08/2025. Có nút PDF; chưa có license reuse rõ, ảnh vùng mắt/ca bệnh cần review riêng.

**File original/SHA-256:** chưa có. **Human review chất lượng:** chưa bắt đầu; **RAG ready:** false.

## vn-skin-cancer-signs

**Tiêu đề:** Dấu hiệu của ung thư da

**Đơn vị đăng/xuất bản:** Bệnh viện Nguyễn Tri Phương. **Tác giả/đơn vị gốc:** Chưa xác định chủ sở hữu nội dung gốc.

**Nguồn:** [Trang chính thức](https://bvnguyentriphuong.com.vn/khoa-kham-benh/dau-hieu-cua-ung-thu-da). **Định dạng:** html; **ngôn ngữ:** `vi`; **truy cập:** `opened`.

**Copyright/license:** unknown; không suy luận public domain/open license.

**Bằng chứng:** [Nguồn 1](https://bvnguyentriphuong.com.vn/khoa-kham-benh/dau-hieu-cua-ung-thu-da).

| Thao tác | Quyền/căn cứ |
|---|---|
| Tải PDF/HTML | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| Lưu byte original | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| Trích xuất và lưu text | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| RAG/indexing nội bộ dự kiến | Chưa xác minh; không được phép vận hành từ hồ sơ này |

**Tài sản bên thứ ba và hạn chế:** Trang có nội dung tiếng Việt; tác giả gốc/ngày/license chưa xác định được. Không gán bản quyền cho bệnh viện chỉ vì đang lưu trang.

**Phạm vi:** K01, K03, K08. Nguồn: https://bvnguyentriphuong.com.vn/khoa-kham-benh/dau-hieu-cua-ung-thu-da; chủ đề đã đối chiếu: K01, K03, K08. Xem review_notes về mức xác minh.

**Kết luận:** trạng thái `pending_review`; đề xuất `pending_review`. Trang có nội dung tiếng Việt; tác giả gốc/ngày/license chưa xác định được. Không gán bản quyền cho bệnh viện chỉ vì đang lưu trang.

**File original/SHA-256:** chưa có. **Human review chất lượng:** chưa bắt đầu; **RAG ready:** false.

## vn-skin-cancer-early

**Tiêu đề:** Một số dấu hiệu giúp bạn nhận biết sớm bệnh ung thư da

**Đơn vị đăng/xuất bản:** Bệnh viện Nguyễn Tri Phương. **Tác giả/đơn vị gốc:** Chưa xác định chủ sở hữu nội dung gốc.

**Nguồn:** [Trang chính thức](https://bvnguyentriphuong.com.vn/benh-hoc-da/mot-so-dau-hieu-giup-ban-nhan-biet-som-benh-ung-thu-da). **Định dạng:** html; **ngôn ngữ:** `vi`; **truy cập:** `opened_after_retry`.

**Copyright/license:** unknown; không suy luận public domain/open license.

**Bằng chứng:** [Nguồn 1](https://bvnguyentriphuong.com.vn/benh-hoc-da/mot-so-dau-hieu-giup-ban-nhan-biet-som-benh-ung-thu-da).

| Thao tác | Quyền/căn cứ |
|---|---|
| Tải PDF/HTML | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| Lưu byte original | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| Trích xuất và lưu text | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| RAG/indexing nội bộ dự kiến | Chưa xác minh; không được phép vận hành từ hồ sơ này |

**Tài sản bên thứ ba và hạn chế:** Đã mở trang tiếng Việt sau lần timeout. Thiếu căn cứ chủ sở hữu gốc/bản dịch/hình và giấy phép lưu/extract/RAG.

**Phạm vi:** K03, K08. Nguồn: https://bvnguyentriphuong.com.vn/benh-hoc-da/mot-so-dau-hieu-giup-ban-nhan-biet-som-benh-ung-thu-da; chủ đề đã đối chiếu: K03, K08. Xem review_notes về mức xác minh.

**Kết luận:** trạng thái `pending_review`; đề xuất `pending_review`. Đã mở trang tiếng Việt sau lần timeout. Thiếu căn cứ chủ sở hữu gốc/bản dịch/hình và giấy phép lưu/extract/RAG.

**File original/SHA-256:** chưa có. **Human review chất lượng:** chưa bắt đầu; **RAG ready:** false.

## vn-seborrheic-keratosis

**Tiêu đề:** DÀY SỪNG DA DẦU HAY DÀY SỪNG TIẾT BÃ: LÀNH TÍNH, ẢNH HƯỞNG THẦM MỸ NHƯNG DỄ ĐIỀU TRỊ

**Đơn vị đăng/xuất bản:** Bệnh viện Da Liễu TP.Đà Nẵng. **Tác giả/đơn vị gốc:** Bệnh viện Da Liễu TP.Đà Nẵng.

**Nguồn:** [Trang chính thức](https://dalieudanang.com/news/cham-soc-da-tham-my/day-sung-da-dau-hay-day-sung-tiet-ba-lanh-tinh-anh-huong-tham-my-nhung-de-dieu-tri-640.html). **Định dạng:** html; **ngôn ngữ:** `vi`; **truy cập:** `opened`.

**Copyright/license:** unknown; không suy luận public domain/open license.

**Bằng chứng:** [Nguồn 1](https://dalieudanang.com/news/cham-soc-da-tham-my/day-sung-da-dau-hay-day-sung-tiet-ba-lanh-tinh-anh-huong-tham-my-nhung-de-dieu-tri-640.html).

| Thao tác | Quyền/căn cứ |
|---|---|
| Tải PDF/HTML | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| Lưu byte original | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| Trích xuất và lưu text | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| RAG/indexing nội bộ dự kiến | Chưa xác minh; không được phép vận hành từ hồ sơ này |

**Tài sản bên thứ ba và hạn chế:** Đã mở trang, ngày 04/09/2024, BSCKI. Nguyễn Thị Nam Phương; copyright bệnh viện. Chưa thấy giấy phép sao chép/chuyển thể cho corpus.

**Phạm vi:** K01, K02, K04, K06, K07. Nguồn: https://dalieudanang.com/news/cham-soc-da-tham-my/day-sung-da-dau-hay-day-sung-tiet-ba-lanh-tinh-anh-huong-tham-my-nhung-de-dieu-tri-640.html; chủ đề đã đối chiếu: K01, K02, K04, K06, K07. Xem review_notes về mức xác minh.

**Kết luận:** trạng thái `pending_review`; đề xuất `pending_review`. Đã mở trang, ngày 04/09/2024, BSCKI. Nguyễn Thị Nam Phương; copyright bệnh viện. Chưa thấy giấy phép sao chép/chuyển thể cho corpus.

**File original/SHA-256:** chưa có. **Human review chất lượng:** chưa bắt đầu; **RAG ready:** false.

## vn-melanoma-histology

**Tiêu đề:** ĐẶC ĐIỂM LÂM SÀNG VÀ MÔ BỆNH HỌC CỦA BỆNH UNG THƯ HẮC TỐ DA TẠI BỆNH VIỆN DA LIỄU TRUNG ƯƠNG GIAI ĐOẠN 2020-2026

**Đơn vị đăng/xuất bản:** Tạp chí Y học Cộng đồng. **Tác giả/đơn vị gốc:** Tạp chí Y học Cộng đồng / Đỗ Thị Như Hoa, Vũ Thái Hà, Nguyễn Hữu Quang.

**Nguồn:** [Trang chính thức](https://tapchiyhcd.vn/index.php/yhcd/en/article/view/6280). **Định dạng:** pdf; **ngôn ngữ:** `not_reverified_fulltext_vi`; **truy cập:** `opened_english_metadata`.

URL trong snapshot V1: [nguồn cũ](https://tapchiyhcd.vn/index.php/yhcd/vi/article/view/6280).

**Copyright/license:** unknown; không suy luận public domain/open license.

**Bằng chứng:** [Nguồn 1](https://tapchiyhcd.vn/index.php/yhcd/en/article/view/6280).

| Thao tác | Quyền/căn cứ |
|---|---|
| Tải PDF/HTML | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| Lưu byte original | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| Trích xuất và lưu text | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| RAG/indexing nội bộ dự kiến | Chưa xác minh; không được phép vận hành từ hồ sơ này |

**Tài sản bên thứ ba và hạn chế:** URL /vi/ redirect loop; endpoint không locale chuyển tới /en/ và mở được. DOI 10.52163/yhc.v67iCD12.6280, ngày 25/08/2026; chưa xác minh toàn văn tiếng Việt/giấy phép.

**Phạm vi:** K03, K05. Nguồn: https://tapchiyhcd.vn/index.php/yhcd/vi/article/view/6280; chủ đề đã đối chiếu: K03, K05. Xem review_notes về mức xác minh.

**Kết luận:** trạng thái `pending_review`; đề xuất `pending_review`. URL /vi/ redirect loop; endpoint không locale chuyển tới /en/ và mở được. DOI 10.52163/yhc.v67iCD12.6280, ngày 25/08/2026; chưa xác minh toàn văn tiếng Việt/giấy phép.

**File original/SHA-256:** chưa có. **Human review chất lượng:** chưa bắt đầu; **RAG ready:** false.

## vn-acs-skin-check

**Tiêu đề:** Kiểm tra da để tìm các dấu hiệu ung thư

**Đơn vị đăng/xuất bản:** American Cancer Society. **Tác giả/đơn vị gốc:** American Cancer Society, Inc..

**Nguồn:** [Trang chính thức](https://www.cancer.org/content/dam/cancer-org/cancer-control/vi/booklets-flyers/checking-your-skin.pdf). **Định dạng:** pdf; **ngôn ngữ:** `vi`; **truy cập:** `opened_pdf_in_browser`.

**Copyright/license:** unknown; không suy luận public domain/open license.

**Bằng chứng:** [Nguồn 1](https://www.cancer.org/content/dam/cancer-org/cancer-control/vi/booklets-flyers/checking-your-skin.pdf).

| Thao tác | Quyền/căn cứ |
|---|---|
| Tải PDF/HTML | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| Lưu byte original | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| Trích xuất và lưu text | Chưa xác minh; không được phép vận hành từ hồ sơ này |
| RAG/indexing nội bộ dự kiến | Chưa xác minh; không được phép vận hành từ hồ sơ này |

**Tài sản bên thứ ba và hạn chế:** PDF chính thức 2 trang có tiếng Việt, copyright American Cancer Society 2024, Rev.9/24. Đọc PDF qua công cụ web để nghiên cứu, không lưu vào corpus. Chưa xác minh giấy phép cho workflow RAG; trang terms thử mở không truy cập được.

**Phạm vi:** K01, K03, K08. Nguồn: https://www.cancer.org/content/dam/cancer-org/cancer-control/vi/booklets-flyers/checking-your-skin.pdf; chủ đề đã đối chiếu: K01, K03, K08. Xem review_notes về mức xác minh.

**Kết luận:** trạng thái `pending_review`; đề xuất `pending_review`. PDF chính thức 2 trang có tiếng Việt, copyright American Cancer Society 2024, Rev.9/24. Đọc PDF qua công cụ web để nghiên cứu, không lưu vào corpus. Chưa xác minh giấy phép cho workflow RAG; trang terms thử mở không truy cập được.

**File original/SHA-256:** chưa có. **Human review chất lượng:** chưa bắt đầu; **RAG ready:** false.

## vn-tbjmp-atopic-488

**Tiêu đề:** Đặc điểm lâm sàng và một số yếu tố liên quan đến bệnh viêm da cơ địa ở sinh viên Trường Đại học Y Dược Thái Bình năm 2024

**Đơn vị đăng/xuất bản:** Trường Đại học Y Dược Thái Bình – Tạp chí Y Dược Thái Bình. **Tác giả/đơn vị gốc:** Tạp chí Y Dược Thái Bình / Trương Mai Trâm, Dương Văn Dược, Lường Thị Hồng, Nguyễn Thị Kim Oanh, Vũ Hà Phương, Mirna Da Nora Mangue, Nguyễn Thị Tài Linh.

**Nguồn:** [Trang chính thức](https://thaibinhjmp.vn/index.php/ojstbump/article/view/488). **Định dạng:** pdf; **ngôn ngữ:** `vi`; **truy cập:** `opened_pdf_in_browser`.

PDF chính thức: [endpoint đã đối chiếu](https://thaibinhjmp.vn/index.php/ojstbump/article/download/488/449/1470). HEAD `373569` byte, chưa nhận body vào corpus. DOI: `10.62685/tbjmp.2025.18.08`; ngày xuất bản: 2025-09-30.

**Copyright/license:** CC BY-SA 4.0.

**Bằng chứng:** [Nguồn 1](https://thaibinhjmp.vn/index.php/ojstbump/article/view/488); [Nguồn 2](https://creativecommons.org/licenses/by-sa/4.0/); [Nguồn 3](https://creativecommons.org/licenses/by-sa/4.0/legalcode.en); [Nguồn 4](https://thaibinhjmp.vn/index.php/ojstbump/about/submissions); [Nguồn 5](https://thaibinhjmp.vn/index.php/ojstbump/quy_dinh_quy_trinh); [Nguồn 6](https://thaibinhjmp.vn/robots.txt).

| Thao tác | Quyền/căn cứ |
|---|---|
| Tải PDF/HTML | CC BY-SA cho sao chép/chuyển thể có điều kiện; chờ operator duyệt |
| Lưu byte original | CC BY-SA cho sao chép/chuyển thể có điều kiện; chờ operator duyệt |
| Trích xuất và lưu text | CC BY-SA cho sao chép/chuyển thể có điều kiện; chờ operator duyệt |
| RAG/indexing nội bộ dự kiến | Có căn cứ license cho indexing nội bộ khi giữ điều kiện; chờ operator review, grant và human QA |

**Tài sản bên thứ ba và hạn chế:** Không thấy credit loại trừ quyền trong lớp text đã kiểm tra; chưa xác minh toàn bộ bằng hình render. Không tải tài liệu tham khảo, bộ câu hỏi SCORAD/DLQI, ảnh hoặc tài sản liên kết riêng. Nếu phát hiện ngoại lệ ở byte nhận về thì giữ nguyên original, cô lập và ngừng cấp RAG.

**Phạm vi:** K01, K03, K04. Trang in 49-54 (6 trang); bảng triệu chứng mụn nước, khô da/bong vảy, ngứa và yếu tố liên quan. Metadata web chỉ liệt kê tác giả đầu; danh sách đồng tác giả lấy từ trang đầu PDF.

**Kết luận:** trạng thái `pending_review`; đề xuất `eligible`. License theo từng bài cho sao chép/chuyển thể; đề xuất đủ căn cứ để operator duyệt batch có giới hạn. Không phải approved rights review.

**File original/SHA-256:** chưa có. **Human review chất lượng:** chưa bắt đầu; **RAG ready:** false.

## vn-tbjmp-acne-490

**Tiêu đề:** Các yếu tố nguy cơ liên quan đến mức độ trứng cá thể thông thường ở sinh viên: Nghiên cứu cắt ngang tại Trường Đại học Y Dược Thái Bình

**Đơn vị đăng/xuất bản:** Trường Đại học Y Dược Thái Bình – Tạp chí Y Dược Thái Bình. **Tác giả/đơn vị gốc:** Tạp chí Y Dược Thái Bình / Nguyễn Thị Kim Dung, Nguyễn Thị Tài Linh.

**Nguồn:** [Trang chính thức](https://thaibinhjmp.vn/index.php/ojstbump/article/view/490). **Định dạng:** pdf; **ngôn ngữ:** `vi`; **truy cập:** `opened_pdf_in_browser`.

PDF chính thức: [endpoint đã đối chiếu](https://thaibinhjmp.vn/index.php/ojstbump/article/download/490/451/1474). HEAD `240159` byte, chưa nhận body vào corpus. DOI: `10.62685/tbjmp.2025.18.10`; ngày xuất bản: 2025-09-30.

**Copyright/license:** CC BY-SA 4.0.

**Bằng chứng:** [Nguồn 1](https://thaibinhjmp.vn/index.php/ojstbump/article/view/490); [Nguồn 2](https://creativecommons.org/licenses/by-sa/4.0/); [Nguồn 3](https://creativecommons.org/licenses/by-sa/4.0/legalcode.en); [Nguồn 4](https://thaibinhjmp.vn/index.php/ojstbump/about/submissions); [Nguồn 5](https://thaibinhjmp.vn/index.php/ojstbump/quy_dinh_quy_trinh); [Nguồn 6](https://thaibinhjmp.vn/robots.txt).

| Thao tác | Quyền/căn cứ |
|---|---|
| Tải PDF/HTML | CC BY-SA cho sao chép/chuyển thể có điều kiện; chờ operator duyệt |
| Lưu byte original | CC BY-SA cho sao chép/chuyển thể có điều kiện; chờ operator duyệt |
| Trích xuất và lưu text | CC BY-SA cho sao chép/chuyển thể có điều kiện; chờ operator duyệt |
| RAG/indexing nội bộ dự kiến | Có căn cứ license cho indexing nội bộ khi giữ điều kiện; chờ operator review, grant và human QA |

**Tài sản bên thứ ba và hạn chế:** Không thấy credit loại trừ quyền trong lớp text đã kiểm tra; chưa xác minh toàn bộ bằng hình render. Không tải tài liệu tham khảo, bộ câu hỏi SCORAD/DLQI, ảnh hoặc tài sản liên kết riêng. Nếu phát hiện ngoại lệ ở byte nhận về thì giữ nguyên original, cô lập và ngừng cấp RAG.

**Phạm vi:** K01, K02, K03, K04. Trang in 63-67 (5 trang); mục 2.2 mô tả comedones, sẩn, mủ, nốt/nang và mức độ; bảng yếu tố liên quan. Không biến liên quan thống kê thành căn nguyên đã chứng minh.

**Kết luận:** trạng thái `pending_review`; đề xuất `eligible`. License theo từng bài cho sao chép/chuyển thể; đề xuất đủ căn cứ để operator duyệt batch có giới hạn. Không phải approved rights review.

**File original/SHA-256:** chưa có. **Human review chất lượng:** chưa bắt đầu; **RAG ready:** false.

## vn-tbjmp-psoriasis-640

**Tiêu đề:** Kết quả điều trị và tính an toàn của Secukinumab trên bệnh nhân vảy nến thông thường mức độ vừa và nặng tại Bệnh viện Da liễu Thanh Hóa

**Đơn vị đăng/xuất bản:** Trường Đại học Y Dược Thái Bình – Tạp chí Y Dược Thái Bình. **Tác giả/đơn vị gốc:** Tạp chí Y Dược Thái Bình / Lương Đức Diễn, Lê Trí Bách, Nguyễn Thị Lệ, Lê Thu Hoài.

**Nguồn:** [Trang chính thức](https://thaibinhjmp.vn/index.php/ojstbump/article/view/640). **Định dạng:** pdf; **ngôn ngữ:** `vi`; **truy cập:** `opened_pdf_in_browser`.

PDF chính thức: [endpoint đã đối chiếu](https://thaibinhjmp.vn/index.php/ojstbump/article/download/640/598/1930). HEAD `308937` byte, chưa nhận body vào corpus. DOI: `10.62685/tbjmp.2026.24.20`; ngày xuất bản: 2026-08-28.

**Copyright/license:** CC BY-SA 4.0.

**Bằng chứng:** [Nguồn 1](https://thaibinhjmp.vn/index.php/ojstbump/article/view/640); [Nguồn 2](https://creativecommons.org/licenses/by-sa/4.0/); [Nguồn 3](https://creativecommons.org/licenses/by-sa/4.0/legalcode.en); [Nguồn 4](https://thaibinhjmp.vn/index.php/ojstbump/about/submissions); [Nguồn 5](https://thaibinhjmp.vn/index.php/ojstbump/quy_dinh_quy_trinh); [Nguồn 6](https://thaibinhjmp.vn/robots.txt).

| Thao tác | Quyền/căn cứ |
|---|---|
| Tải PDF/HTML | CC BY-SA cho sao chép/chuyển thể có điều kiện; chờ operator duyệt |
| Lưu byte original | CC BY-SA cho sao chép/chuyển thể có điều kiện; chờ operator duyệt |
| Trích xuất và lưu text | CC BY-SA cho sao chép/chuyển thể có điều kiện; chờ operator duyệt |
| RAG/indexing nội bộ dự kiến | Có căn cứ license cho indexing nội bộ khi giữ điều kiện; chờ operator review, grant và human QA |

**Tài sản bên thứ ba và hạn chế:** Không thấy credit loại trừ quyền trong lớp text đã kiểm tra; chưa xác minh toàn bộ bằng hình render. Không tải tài liệu tham khảo, bộ câu hỏi SCORAD/DLQI, ảnh hoặc tài sản liên kết riêng. Nếu phát hiện ngoại lệ ở byte nhận về thì giữ nguyên original, cô lập và ngừng cấp RAG.

**Phạm vi:** K01, K03, K07. Trang in 159-166 (8 trang); mục 2.2.2 mô tả đỏ da, dày da, bong vảy; bảng đáp ứng tổn thương PASI. DLQI chỉ mô tả chỉ số/kết quả, không thấy toàn bộ 10 câu hỏi trong lớp text đã đọc. Không nhập bộ câu hỏi riêng.

**Kết luận:** trạng thái `pending_review`; đề xuất `eligible`. License theo từng bài cho sao chép/chuyển thể; đề xuất đủ căn cứ để operator duyệt batch có giới hạn. Không phải approved rights review.

**File original/SHA-256:** chưa có. **Human review chất lượng:** chưa bắt đầu; **RAG ready:** false.

## vn-tbjmp-atopic-qol-425

**Tiêu đề:** Các yếu tố ảnh hưởng đến chất lượng cuộc sống của bệnh nhân viêm da cơ địa tại Thái Bình

**Đơn vị đăng/xuất bản:** Tạp chí Y Dược Thái Bình. **Tác giả/đơn vị gốc:** Tạp chí Y Dược Thái Bình / Nguyễn Thị Kim Dung.

**Nguồn:** [Trang chính thức](https://thaibinhjmp.vn/index.php/ojstbump/article/view/425). **Định dạng:** pdf; **ngôn ngữ:** `vi_abstract_verified_fulltext_not_reverified`; **truy cập:** `opened_article_page`.

**Copyright/license:** CC BY 4.0.

**Bằng chứng:** [Nguồn 1](https://thaibinhjmp.vn/index.php/ojstbump/article/view/425).

| Thao tác | Quyền/căn cứ |
|---|---|
| Tải PDF/HTML | Chưa review cho batch này; không chọn để tải |
| Lưu byte original | Chưa review cho batch này; không chọn để tải |
| Trích xuất và lưu text | Chưa review cho batch này; không chọn để tải |
| RAG/indexing nội bộ dự kiến | Chưa review cho batch này; không chọn để tải |

**Tài sản bên thứ ba và hạn chế:** Có license theo bài; thiên về chất lượng cuộc sống, cần xác nhận phạm vi tổn thương và review DLQI/ảnh trước chọn.

**Phạm vi:** K03. Có license theo bài; thiên về chất lượng cuộc sống, cần xác nhận phạm vi tổn thương và review DLQI/ảnh trước chọn.

**Kết luận:** trạng thái `pending_review`; đề xuất `pending_review`. Có license theo bài; thiên về chất lượng cuộc sống, cần xác nhận phạm vi tổn thương và review DLQI/ảnh trước chọn.

**File original/SHA-256:** chưa có. **Human review chất lượng:** chưa bắt đầu; **RAG ready:** false.

## vn-tbjmp-psoriasis-qol-367

**Tiêu đề:** Thực trạng chất lượng cuộc sống của người bệnh vảy nến đến khám, điều trị tại Bệnh viện Da Liễu Thái Bình năm 2024

**Đơn vị đăng/xuất bản:** Tạp chí Y Dược Thái Bình. **Tác giả/đơn vị gốc:** Tạp chí Y Dược Thái Bình / Lê Thị Hương.

**Nguồn:** [Trang chính thức](https://thaibinhjmp.vn/index.php/ojstbump/article/view/367). **Định dạng:** pdf; **ngôn ngữ:** `vi_abstract_verified_fulltext_not_reverified`; **truy cập:** `opened_article_page`.

**Copyright/license:** CC BY 4.0.

**Bằng chứng:** [Nguồn 1](https://thaibinhjmp.vn/index.php/ojstbump/article/view/367).

| Thao tác | Quyền/căn cứ |
|---|---|
| Tải PDF/HTML | Chưa review cho batch này; không chọn để tải |
| Lưu byte original | Chưa review cho batch này; không chọn để tải |
| Trích xuất và lưu text | Chưa review cho batch này; không chọn để tải |
| RAG/indexing nội bộ dự kiến | Chưa review cho batch này; không chọn để tải |

**Tài sản bên thứ ba và hạn chế:** Có license theo bài, chưa chọn; tránh trùng quần thể với bài 377, review phạm vi K và quyền bộ câu hỏi.

**Phạm vi:** K03. Có license theo bài, chưa chọn; tránh trùng quần thể với bài 377, review phạm vi K và quyền bộ câu hỏi.

**Kết luận:** trạng thái `pending_review`; đề xuất `pending_review`. Có license theo bài, chưa chọn; tránh trùng quần thể với bài 377, review phạm vi K và quyền bộ câu hỏi.

**File original/SHA-256:** chưa có. **Human review chất lượng:** chưa bắt đầu; **RAG ready:** false.

## vn-tbjmp-acne-tcm-507

**Tiêu đề:** Nghiên cứu các thể lâm sàng mụn trứng cá theo Y học cổ truyền tại Bệnh viện Trường Đại học Y Dược Huế

**Đơn vị đăng/xuất bản:** Tạp chí Y Dược Thái Bình. **Tác giả/đơn vị gốc:** Tạp chí Y Dược Thái Bình / Đoàn Thị Nhật Lệ.

**Nguồn:** [Trang chính thức](https://thaibinhjmp.vn/index.php/ojstbump/article/view/507). **Định dạng:** pdf; **ngôn ngữ:** `vi_abstract_verified_fulltext_not_reverified`; **truy cập:** `opened_article_page`.

**Copyright/license:** CC BY-SA 4.0.

**Bằng chứng:** [Nguồn 1](https://thaibinhjmp.vn/index.php/ojstbump/article/view/507).

| Thao tác | Quyền/căn cứ |
|---|---|
| Tải PDF/HTML | Chưa review cho batch này; không chọn để tải |
| Lưu byte original | Chưa review cho batch này; không chọn để tải |
| Trích xuất và lưu text | Chưa review cho batch này; không chọn để tải |
| RAG/indexing nội bộ dự kiến | Chưa review cho batch này; không chọn để tải |

**Tài sản bên thứ ba và hạn chế:** Bài có mô tả sẩn/mụn mủ/nang và license; chưa chọn vì cần review phạm vi phần YHCT, bằng chứng và tài sản trước toàn văn.

**Phạm vi:** K01, K02, K03. Bài có mô tả sẩn/mụn mủ/nang và license; chưa chọn vì cần review phạm vi phần YHCT, bằng chứng và tài sản trước toàn văn.

**Kết luận:** trạng thái `pending_review`; đề xuất `pending_review`. Bài có mô tả sẩn/mụn mủ/nang và license; chưa chọn vì cần review phạm vi phần YHCT, bằng chứng và tài sản trước toàn văn.

**File original/SHA-256:** chưa có. **Human review chất lượng:** chưa bắt đầu; **RAG ready:** false.

## vn-hue-skin-spectrum-2271

**Tiêu đề:** Phổ các bệnh da và một số yếu tố liên quan trên bệnh nhân cao tuổi khám chuyên khoa da liễu tại Bệnh viện Thống Nhất

**Đơn vị đăng/xuất bản:** Tạp chí Y học lâm sàng Bệnh viện Trung Ương Huế. **Tác giả/đơn vị gốc:** Tạp chí Y học lâm sàng Bệnh viện Trung Ương Huế / Tác giả trên trang bài; chưa chép danh sách đầy đủ.

**Nguồn:** [Trang chính thức](https://jcmhch.com.vn/index.php/home/article/view/2271). **Định dạng:** pdf; **ngôn ngữ:** `vi_abstract_verified_fulltext_not_reverified`; **truy cập:** `opened_article_page`.

**Copyright/license:** CC BY-NC-ND 4.0.

**Bằng chứng:** [Nguồn 1](https://jcmhch.com.vn/index.php/home/article/view/2271); [Nguồn 2](https://jcmhch.com.vn/index.php/home/License_and_copyright).

| Thao tác | Quyền/căn cứ |
|---|---|
| Tải PDF/HTML | Chưa review cho batch này; không chọn để tải |
| Lưu byte original | Chưa review cho batch này; không chọn để tải |
| Trích xuất và lưu text | Chưa review cho batch này; không chọn để tải |
| RAG/indexing nội bộ dự kiến | Chưa review cho batch này; không chọn để tải |

**Tài sản bên thứ ba và hạn chế:** Điều khoản NC/ND; không khẳng định cấm mọi xử lý nội bộ nhưng chưa đủ căn cứ cho workflow RAG dự kiến, cần review hoặc permission riêng.

**Phạm vi:** unknown. Điều khoản NC/ND; không khẳng định cấm mọi xử lý nội bộ nhưng chưa đủ căn cứ cho workflow RAG dự kiến, cần review hoặc permission riêng.

**Kết luận:** trạng thái `restricted`; đề xuất `restricted`. Điều khoản NC/ND; không khẳng định cấm mọi xử lý nội bộ nhưng chưa đủ căn cứ cho workflow RAG dự kiến, cần review hoặc permission riêng.

**File original/SHA-256:** chưa có. **Human review chất lượng:** chưa bắt đầu; **RAG ready:** false.

## vn-vjdv-immunotherapy-154

**Tiêu đề:** Liệu pháp miễn dịch trong ung thư da không hắc tố

**Đơn vị đăng/xuất bản:** Tạp chí Da liễu học Việt Nam. **Tác giả/đơn vị gốc:** Tạp chí Da liễu học Việt Nam / Nguyễn Hồng Sơn, Lê Thị Thanh Hiền, Nguyễn Hữu Quang, Nguyễn Đình Quân.

**Nguồn:** [Trang chính thức](https://vjdv.vn/index.php/vjdv/article/view/154). **Định dạng:** pdf; **ngôn ngữ:** `vi_abstract_verified_fulltext_not_reverified`; **truy cập:** `opened_article_page`.

**Copyright/license:** unknown.

**Bằng chứng:** [Nguồn 1](https://vjdv.vn/index.php/vjdv/article/view/154).

| Thao tác | Quyền/căn cứ |
|---|---|
| Tải PDF/HTML | Chưa review cho batch này; không chọn để tải |
| Lưu byte original | Chưa review cho batch này; không chọn để tải |
| Trích xuất và lưu text | Chưa review cho batch này; không chọn để tải |
| RAG/indexing nội bộ dự kiến | Chưa review cho batch này; không chọn để tải |

**Tài sản bên thứ ba và hạn chế:** Nguồn chuyên khoa phù hợp trực tiếp, DOI 10.56320/tcdlhvn.43.154; chưa thấy license rõ trên trang bài. Đưa vào diện xin phép, không chọn để tải.

**Phạm vi:** K02, K04, K07. Nguồn chuyên khoa phù hợp trực tiếp, DOI 10.56320/tcdlhvn.43.154; chưa thấy license rõ trên trang bài. Đưa vào diện xin phép, không chọn để tải.

**Kết luận:** trạng thái `pending_review`; đề xuất `pending_review`. Nguồn chuyên khoa phù hợp trực tiếp, DOI 10.56320/tcdlhvn.43.154; chưa thấy license rõ trên trang bài. Đưa vào diện xin phép, không chọn để tải.

**File original/SHA-256:** chưa có. **Human review chất lượng:** chưa bắt đầu; **RAG ready:** false.

## Quy tắc ghi công và chất lượng cho batch

Giữ toàn bộ tác giả trong PDF (metadata web chỉ có thể hiển thị tác giả đầu), tên bài, đơn vị xuất bản, DOI, URL nguồn và CC BY-SA 4.0. Ghi original giữ nguyên byte, text được trích tự động, các lỗi/thay đổi đã biết. ShareAlike khi chia sẻ phần phái sinh theo điều kiện áp dụng; chưa đánh giá việc phát hành corpus công khai. Không gắn quyền cho tài liệu tham khảo hoặc bộ câu hỏi chỉ được nhắc đến.

Các bài được chọn có text layer tiếng Việt; chưa chạy importer, so sánh fidelity hoặc kiểm tra toàn bộ hình render. Một số bảng cần đối chiếu số liệu/nhãn cột và các từ tiếng Anh ngắt dòng. Chưa thấy thông báo loại trừ quyền trong lớp text đã đọc; đó không phải bảo đảm pháp lý cho mọi tài sản nhúng. Dừng hoặc cô lập nếu bytes thực nhận có ngoại lệ quyền/nhận diện bệnh nhân.

[Báo cáo batch, giới hạn acquisition, trạng thái thực nhận và hướng dẫn tiếp theo](PHASE_V1_1_CORPUS_REPORT.md).
