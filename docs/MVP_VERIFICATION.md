# Xác minh MVP — Session 04

Phạm vi xác minh là pipeline offline với fixture HTML/PDF tổng hợp. Quality
gate trên Windows và Python 3.12.5 đạt 206 test. Ruff lint, Ruff format và kiểm
tra cả hai JSON Schema đều đạt. Demo xử lý 5 đầu vào, xuất 3 record (mỗi trạng
thái extraction có 1 record), ghi nhận 1 mục failed và 1 mục skipped.
`verify_batch()` trả kết quả hợp lệ cho batch demo.

| AC | Trạng thái | Bằng chứng đã chạy | Giới hạn còn lại và bước hoàn thiện |
| --- | --- | --- | --- |
| AC-01 | PASS | `test_reruns_and_content_versions_preserve_published_batches` kiểm tra ID qua lần chạy lại, nguồn khác và bản nội dung mới. `test_mismatched_event_does_not_attribute_record_to_another_source` kiểm tra sai nguồn. [Tests export](../tests/integration/test_export.py) | Phụ thuộc khóa logic ổn định do caller cấp. Review quy tắc khóa và truy vết cho từng nguồn pilot. |
| AC-02 | PASS | `test_mixed_html_pdf_batch_preserves_records_and_checksums` tính lại hash/kích thước original. `test_verify_detects_tampering_and_missing_files` phát hiện file gốc thiếu/hỏng. [Tests export](../tests/integration/test_export.py) | Đã kiểm chứng với ArtifactStore cục bộ. Tính lại checksum khi nghiệm thu corpus pilot trên storage dự kiến. |
| AC-03 | PASS | `test_end_to_end_original_and_provenance_are_verifiable` và bài kiểm tra batch hỗn hợp đối chiếu record và provenance với original. [Tests pipeline](../tests/integration/test_pipeline.py), [tests export](../tests/integration/test_export.py) | Kiểm tra liên kết với original bao phủ fixture HTML/PDF. Lấy mẫu đối chiếu thứ tự đọc và văn bản với bản gốc trong pilot. |
| AC-04 | PASS | `test_packaged_schema_is_valid` kiểm tra hai schema. Bài kiểm tra batch hỗn hợp gọi `validate_record()` trên toàn bộ record xuất và xác minh manifest. [Tests schema](../tests/contract/test_manifest.py), [tests export](../tests/integration/test_export.py) | Áp dụng cho v0.1. Chạy lại kiểm tra hợp đồng khi thêm producer hoặc phiên bản. |
| AC-05 | PASS | `test_reruns_and_content_versions_preserve_published_batches` xác nhận hai nguồn có nội dung trùng chỉ lưu một original, batch cũ giữ nguyên và bản nội dung mới có hash riêng. `test_concurrent_publish` thử lưu đồng thời. [Tests export](../tests/integration/test_export.py), [tests storage](../tests/unit/test_storage.py) | Đã kiểm chứng trên filesystem cục bộ hỗ trợ hard link. Kiểm tra lại nếu đổi môi trường lưu trữ. |
| AC-06 | PASS | Batch có acquisition lỗi, record sai schema và thiếu rights; test fault injection cô lập lỗi ghi và kiểm tra cleanup sau ngắt. [Tests export](../tests/integration/test_export.py) | Kill hoặc mất điện có thể để lại batch chưa công bố. Review cách phát hiện và dọn batch mồ côi trước khi chạy dài. |
| AC-07 | PASS | `test_record_with_unknown_fields`, `test_partial_requires_warning` và test batch hỗn hợp xác nhận trường chưa biết, warning và trạng thái extraction được giữ. [Tests record](../tests/contract/test_record.py), [tests export](../tests/integration/test_export.py) | PDF chưa có OCR, page-boundary chi tiết ở extraction nội bộ, bảng phức tạp có thể mất cấu trúc. Đánh giá fidelity bằng corpus pilot. |
| AC-08 | PASS | Schema từ chối trường ngoài hợp đồng. Test batch hỗn hợp so sánh record xuất với record pipeline và chỉ thấy manifest cùng các record JSON trong batch. [Tests record](../tests/contract/test_record.py), [tests export](../tests/integration/test_export.py) | Giữ kiểm tra hợp đồng khi tích hợp consumer ở giai đoạn sau. |
| AC-09 | PASS | `test_unknown_rights_do_not_allow_distribution_and_restricted_requires_evidence` kiểm tra chính sách gán quyền. Tests export giữ `unknown` và `restricted`, bỏ qua mục thiếu quyền và từ chối record sai rights. [Tests pipeline](../tests/integration/test_pipeline.py), [tests export](../tests/integration/test_export.py) | Đã kiểm chứng hành vi kỹ thuật khi export nội bộ. Review căn cứ truy cập, giấy phép, điều khoản và xử lý PHI theo từng nguồn trước pilot. |
| AC-10 | PARTIAL | `test_supported_labels` kiểm tra v0.1 biểu diễn đủ K01–K08 với căn cứ tổng hợp. Test pipeline giữ `unknown` khi thiếu căn cứ. [Tests record](../tests/contract/test_record.py), [tests pipeline](../tests/integration/test_pipeline.py) | Chưa có bộ mẫu được duyệt kèm căn cứ nhãn đại diện cho cả tám nhóm. Chuẩn bị corpus pilot để đối chiếu nhãn và phạm vi bao phủ. |

**Tổng hợp** — 9 PASS, 1 PARTIAL, 0 NOT IMPLEMENTED, 0 NOT VERIFIED.
Luồng MVP offline đã hoàn thành. HTTP crawling nguồn y khoa thật chưa triển khai.
Trước pilot cần duyệt chính sách truy cập, tái sử dụng và cách ly PHI, chốt khóa
logic theo nguồn, rồi đánh giá chất lượng trích xuất và độ bao phủ trên corpus
đại diện. Quality gate hiện tại dùng dữ liệu tổng hợp.
