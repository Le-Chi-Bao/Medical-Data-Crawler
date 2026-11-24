# Hồ sơ thẩm định nguồn pilot nội bộ · Session 05B-1

Tám ứng viên ưu tiên đều ở trạng thái `needs_review` và bị gate chặn. `UNKNOWN` chỉ quyết định hoặc giá trị chưa có căn cứ. `NOT VERIFIED` chỉ bước đối chiếu chưa thực hiện. Đầu mối chính sách giúp reviewer tìm căn cứ theo từng tài liệu. Hai URL CDC được chọn từ chỉ mục của nhà xuất bản để đề xuất mẫu K06. Định dạng thực tế và redirect sẽ được reviewer xác minh. [Registry ứng viên](../config/source_candidates.v0.1.json) · [Chính sách pilot nội bộ](INTERNAL_PILOT_POLICY.md)

## NCI Skin Cancer Treatment — Patient

| Trường | Giá trị |
| --- | --- |
| source_id | `nci-skin-treatment-patient` |
| candidate_url | <https://www.cancer.gov/types/skin/patient/skin-treatment-pdq> |
| publisher | NCI |
| Expected document type | HTML |
| Actual document type | NOT VERIFIED |
| Final URL / redirect status | NOT VERIFIED |
| Terms evidence URL | UNKNOWN |
| Copyright/license evidence URL | UNKNOWN |
| Đầu mối chính sách truy cập | UNKNOWN |
| Đầu mối chính sách quyền tác giả | <https://www.cancer.gov/policies/copyright-reuse> |
| Manual access decision | UNKNOWN |
| Original bytes read permission | UNKNOWN |
| Original bytes internal storage permission | UNKNOWN |
| Extracted text read permission | UNKNOWN |
| Extracted text internal storage permission | UNKNOWN |
| Embedded assets review | NOT VERIFIED |
| Third-party images/media review | NOT VERIFIED |
| Privacy / PHI review | NOT VERIFIED |
| Candidate K01–K08 | K07 |
| reviewer_id | UNKNOWN |
| reviewed_at | UNKNOWN |
| review_again_at | UNKNOWN |
| Unresolved risks | Xác định điều khoản truy cập và căn cứ cho đúng bản PDQ Patient. Kiểm tra credit và quyền lưu hình/minh họa nếu có. |
| Proposed decision | `needs_review` |
| Final approval decision | UNKNOWN |

## NCI Skin Cancer Prevention

| Trường | Giá trị |
| --- | --- |
| source_id | `nci-skin-prevention` |
| candidate_url | <https://www.cancer.gov/types/skin/patient/skin-prevention-pdq> |
| publisher | NCI |
| Expected document type | HTML |
| Actual document type | NOT VERIFIED |
| Final URL / redirect status | NOT VERIFIED |
| Terms evidence URL | UNKNOWN |
| Copyright/license evidence URL | UNKNOWN |
| Đầu mối chính sách truy cập | UNKNOWN |
| Đầu mối chính sách quyền tác giả | <https://www.cancer.gov/policies/copyright-reuse> |
| Manual access decision | UNKNOWN |
| Original bytes read permission | UNKNOWN |
| Original bytes internal storage permission | UNKNOWN |
| Extracted text read permission | UNKNOWN |
| Extracted text internal storage permission | UNKNOWN |
| Embedded assets review | NOT VERIFIED |
| Third-party images/media review | NOT VERIFIED |
| Privacy / PHI review | NOT VERIFIED |
| Candidate K01–K08 | K04, K08 |
| reviewer_id | UNKNOWN |
| reviewed_at | UNKNOWN |
| review_again_at | UNKNOWN |
| Unresolved risks | Xác định điều khoản truy cập và phạm vi giấy phép cho đúng bản PDQ Patient. Kiểm tra credit và ngoại lệ tài sản nếu có. |
| Proposed decision | `needs_review` |
| Final approval decision | UNKNOWN |

## NIAMS Acne

| Trường | Giá trị |
| --- | --- |
| source_id | `niams-acne` |
| candidate_url | <https://www.niams.nih.gov/health-topics/acne> |
| publisher | NIAMS |
| Expected document type | HTML |
| Actual document type | NOT VERIFIED |
| Final URL / redirect status | NOT VERIFIED |
| HTTP Content-Type, status và response headers | NOT VERIFIED |
| HTML preflight trên original | NOT VERIFIED. Chưa có lượt quét trên bản gốc NIAMS Acne. |
| Terms evidence URL | UNKNOWN |
| Copyright/license evidence URL | UNKNOWN |
| Đầu mối chính sách truy cập | UNKNOWN |
| Đầu mối chính sách quyền tác giả | <https://www.niams.nih.gov/disclaimer> |
| Manual access decision | UNKNOWN |
| Original bytes read permission | UNKNOWN |
| Original bytes internal storage permission | UNKNOWN |
| Extracted text read permission | UNKNOWN |
| Extracted text internal storage permission | UNKNOWN |
| Embedded assets review | NOT VERIFIED |
| Third-party images/media review | NOT VERIFIED |
| Privacy / PHI review | NOT VERIFIED |
| Candidate K01–K08 | K03, K04, K07 |
| reviewer_id | UNKNOWN |
| reviewed_at | UNKNOWN |
| review_again_at | UNKNOWN |
| Unresolved risks | Đối chiếu disclaimer với quyền đọc và lưu trang cụ thể. Kiểm tra nguồn và quyền của hình ảnh nếu có. |
| Proposed decision | `needs_review` |
| Final approval decision | UNKNOWN |

Khi reviewer đã có bản HTML hợp pháp và được phép đọc, dùng [HTML preflight](HTML_PREFLIGHT.md) để ghi SHA-256, kích thước, trạng thái phân tích và mã phát hiện vào hồ sơ. Đối chiếu chứng cứ HTTP riêng cho đúng bản gốc. Hoàn tất rà soát tài sản nhúng, media bên thứ ba, privacy/PHI và căn cứ quyền trước khi ghi quyết định. `niams-acne` đang ở `needs_review`.

## NIAMS Atopic Dermatitis

| Trường | Giá trị |
| --- | --- |
| source_id | `niams-atopic-dermatitis` |
| candidate_url | <https://www.niams.nih.gov/health-topics/atopic-dermatitis> |
| publisher | NIAMS |
| Expected document type | HTML |
| Actual document type | NOT VERIFIED |
| Final URL / redirect status | NOT VERIFIED |
| Terms evidence URL | UNKNOWN |
| Copyright/license evidence URL | UNKNOWN |
| Đầu mối chính sách truy cập | UNKNOWN |
| Đầu mối chính sách quyền tác giả | <https://www.niams.nih.gov/disclaimer> |
| Manual access decision | UNKNOWN |
| Original bytes read permission | UNKNOWN |
| Original bytes internal storage permission | UNKNOWN |
| Extracted text read permission | UNKNOWN |
| Extracted text internal storage permission | UNKNOWN |
| Embedded assets review | NOT VERIFIED |
| Third-party images/media review | NOT VERIFIED |
| Privacy / PHI review | NOT VERIFIED |
| Candidate K01–K08 | K03, K04 |
| reviewer_id | UNKNOWN |
| reviewed_at | UNKNOWN |
| review_again_at | UNKNOWN |
| Unresolved risks | Đối chiếu điều khoản và quyền cho trang tổng quan. Rà hình ảnh, credit và dấu hiệu nhận dạng cá nhân nếu có. |
| Proposed decision | `needs_review` |
| Final approval decision | UNKNOWN |

## NIAMS Psoriasis Diagnosis & Treatment

| Trường | Giá trị |
| --- | --- |
| source_id | `niams-psoriasis-care` |
| candidate_url | <https://www.niams.nih.gov/health-topics/psoriasis/diagnosis-treatment-and-steps-to-take> |
| publisher | NIAMS |
| Expected document type | HTML |
| Actual document type | NOT VERIFIED |
| Final URL / redirect status | NOT VERIFIED |
| Terms evidence URL | UNKNOWN |
| Copyright/license evidence URL | UNKNOWN |
| Đầu mối chính sách truy cập | UNKNOWN |
| Đầu mối chính sách quyền tác giả | <https://www.niams.nih.gov/disclaimer> |
| Manual access decision | UNKNOWN |
| Original bytes read permission | UNKNOWN |
| Original bytes internal storage permission | UNKNOWN |
| Extracted text read permission | UNKNOWN |
| Extracted text internal storage permission | UNKNOWN |
| Embedded assets review | NOT VERIFIED |
| Third-party images/media review | NOT VERIFIED |
| Privacy / PHI review | NOT VERIFIED |
| Candidate K01–K08 | K05, K07 |
| reviewer_id | UNKNOWN |
| reviewed_at | UNKNOWN |
| review_again_at | UNKNOWN |
| Unresolved risks | Xác minh quyền cho đúng tiểu trang chẩn đoán và điều trị. Kiểm tra credit và ngoại lệ tài sản nếu có. |
| Proposed decision | `needs_review` |
| Final approval decision | UNKNOWN |

## NHS Moles

| Trường | Giá trị |
| --- | --- |
| source_id | `nhs-moles` |
| candidate_url | <https://www.nhs.uk/conditions/moles/> |
| publisher | NHS |
| Expected document type | HTML |
| Actual document type | NOT VERIFIED |
| Final URL / redirect status | NOT VERIFIED |
| Terms evidence URL | UNKNOWN |
| Copyright/license evidence URL | UNKNOWN |
| Đầu mối chính sách truy cập | <https://www.nhs.uk/our-policies/terms-and-conditions/> |
| Đầu mối chính sách quyền tác giả | <https://www.nhs.uk/our-policies/terms-and-conditions/> · <https://www.nhs.uk/our-policies/terms-and-conditions/content-not-licensed-for-re-use/> |
| Manual access decision | UNKNOWN |
| Original bytes read permission | UNKNOWN |
| Original bytes internal storage permission | UNKNOWN |
| Extracted text read permission | UNKNOWN |
| Extracted text internal storage permission | UNKNOWN |
| Embedded assets review | NOT VERIFIED |
| Third-party images/media review | NOT VERIFIED |
| Privacy / PHI review | NOT VERIFIED |
| Candidate K01–K08 | K01, K02, K08 |
| reviewer_id | UNKNOWN |
| reviewed_at | UNKNOWN |
| review_again_at | UNKNOWN |
| Unresolved risks | Đối chiếu điều khoản với danh mục nội dung loại trừ. Kiểm tra quyền ảnh, nguồn bên thứ ba và dấu hiệu nhận dạng cá nhân nếu có. |
| Proposed decision | `needs_review` |
| Final approval decision | UNKNOWN |

## CDC TMVII Clinical Overview

| Trường | Giá trị |
| --- | --- |
| source_id | `cdc-tmvii-clinical-overview` |
| candidate_url | <https://www.cdc.gov/ringworm/hcp/clinical-overview/tmvii.html> |
| publisher | CDC |
| Expected document type | HTML |
| Actual document type | NOT VERIFIED |
| Final URL / redirect status | NOT VERIFIED |
| Terms evidence URL | UNKNOWN |
| Copyright/license evidence URL | UNKNOWN |
| Đầu mối chính sách truy cập | UNKNOWN |
| Đầu mối chính sách quyền tác giả | <https://www.cdc.gov/other/agencymaterials.html> |
| Manual access decision | UNKNOWN |
| Original bytes read permission | UNKNOWN |
| Original bytes internal storage permission | UNKNOWN |
| Extracted text read permission | UNKNOWN |
| Extracted text internal storage permission | UNKNOWN |
| Embedded assets review | NOT VERIFIED |
| Third-party images/media review | NOT VERIFIED |
| Privacy / PHI review | NOT VERIFIED |
| Candidate K01–K08 | K06 |
| reviewer_id | UNKNOWN |
| reviewed_at | UNKNOWN |
| review_again_at | UNKNOWN |
| Unresolved risks | Xác minh locator từ chỉ mục, điều khoản truy cập và ngoại lệ của CDC theo tài liệu. Kiểm tra credit, ảnh lâm sàng, privacy và căn cứ gắn K06. |
| Proposed decision | `needs_review` |
| Final approval decision | UNKNOWN |

## CDC Monkeypox Clinical Considerations

| Trường | Giá trị |
| --- | --- |
| source_id | `cdc-monkeypox-clinical-considerations` |
| candidate_url | <https://www.cdc.gov/monkeypox/hcp/clinical-overview/> |
| publisher | CDC |
| Expected document type | HTML |
| Actual document type | NOT VERIFIED |
| Final URL / redirect status | NOT VERIFIED |
| Terms evidence URL | UNKNOWN |
| Copyright/license evidence URL | UNKNOWN |
| Đầu mối chính sách truy cập | UNKNOWN |
| Đầu mối chính sách quyền tác giả | <https://www.cdc.gov/other/agencymaterials.html> |
| Manual access decision | UNKNOWN |
| Original bytes read permission | UNKNOWN |
| Original bytes internal storage permission | UNKNOWN |
| Extracted text read permission | UNKNOWN |
| Extracted text internal storage permission | UNKNOWN |
| Embedded assets review | NOT VERIFIED |
| Third-party images/media review | NOT VERIFIED |
| Privacy / PHI review | NOT VERIFIED |
| Candidate K01–K08 | K06 |
| reviewer_id | UNKNOWN |
| reviewed_at | UNKNOWN |
| review_again_at | UNKNOWN |
| Unresolved risks | Xác nhận trang Clinical Overview of Clade I and Clade II Monkeypox là tài liệu phù hợp để đánh giá K06. Kiểm tra locator, điều khoản, credit, ngoại lệ tài sản và privacy. |
| Proposed decision | `needs_review` |
| Final approval decision | UNKNOWN |

## Ngoại lệ NCI PDF chờ xác minh

`nci-skin-cancer-booklet` có báo cáo chuyển hướng từ `anyone-can-get-skin-cancer.pdf` sang HTML. Final URL, redirect và định dạng thực tế đều `NOT VERIFIED`. Giữ `needs_review` và chặn import từ URL hiện tại. Nếu reviewer xác nhận và đề xuất URL hoặc định dạng thay thế, đăng ký ứng viên mới với `source_id` riêng theo chính sách nguồn. [Registry ứng viên](../config/source_candidates.v0.1.json) · [Quy tắc định danh](SOURCE_POLICY.md)

## Mẫu quyết định dành cho reviewer

Sao chép bảng của ứng viên để ghi kết quả. Giữ `UNKNOWN` hoặc `NOT VERIFIED` ở các mục chưa có căn cứ. Ghi URL căn cứ và điều kiện áp dụng riêng cho từng quyền, cùng tham chiếu chính sách hoặc phiên bản đã đối chiếu. Chỉ lưu mã reviewer và locator công khai trong hồ sơ.

| Trường bổ sung | Giá trị điền khi review |
| --- | --- |
| Snapshot registry được review | `UNKNOWN` |
| Locator và định dạng được duyệt | `NOT VERIFIED` |
| Căn cứ cho từng quyền đọc/lưu và điều kiện áp dụng | `UNKNOWN` |
| Căn cứ xử lý tài sản nhúng, ảnh/media bên thứ ba và privacy | `UNKNOWN` |
| Phạm vi hoạt động nội bộ và điều kiện lưu giữ | `UNKNOWN` |
| Quyết định cuối cùng, lý do và mục cần tái duyệt | `UNKNOWN` |

Người review có thẩm quyền điền `reviewer_id`, `reviewed_at` và `review_again_at` UTC trong phiếu của ứng viên. Khi quyết định được duyệt, ghi các quyền riêng vào registry, đóng các mục chờ tương ứng và kiểm tra bản cập nhật trước khi dùng gate. [Quy trình phê duyệt](INTERNAL_PILOT_POLICY.md#quy-trình-phê-duyệt-và-import)
