# Đánh giá trích xuất pilot offline

**Kết quả trên corpus y khoa thật · NOT MEASURED.** Chưa có original được duyệt hoặc golden annotations cho pilot. Dùng các phiếu dưới đây với tài liệu đã được duyệt, trên máy có quyền truy cập original. Fixture tổng hợp kiểm tra hành vi kỹ thuật của pipeline.

## Chuẩn bị hai lần chạy có thể đối chiếu

1. Chốt danh sách đầu vào theo thứ tự, ghi `source_id`, `document_id` và SHA-256 original hoặc mã lý do khi tài liệu không có original. Với phép so sánh extractor, baseline và lần đối chiếu cùng xử lý chính xác các byte đã lưu. Đánh giá bản nội dung cập nhật thành nhóm khác và ghi cả hai checksum.
2. Ghi cho mỗi lần chạy Git commit, Python và phiên bản dependency, phiên bản registry/commit đã phê duyệt, phương pháp, phiên bản và profile của extractor, phiên bản schema, ID batch và tham chiếu manifest. Ghi phiên bản bộ annotation, tiêu chí chọn mẫu, vùng bỏ qua và quy tắc chuẩn hóa dùng chung.
3. Mở original với tài nguyên từ xa bị tắt. Xác định phần nội dung chính, thứ tự đọc và metadata theo nguồn. Reviewer chuẩn bị golden annotation hoặc phiếu thủ công có tham chiếu trang/vùng PDF hay selector/vị trí HTML, cùng phiên bản, ngày và mã reviewer. Ghi các đánh giá bất đồng cần phân xử. Chỉ lưu đoạn tham chiếu hoặc bản chép golden khi quyền sử dụng cho phép, trong khu vực đã duyệt.
4. Chạy `verify_batch(manifest_path, provenance)` cho từng batch. Đối với record được xuất, verifier phân biệt manifest sai, record sai và tham chiếu original/provenance hỏng. Kiểm tra omission riêng và dùng `ArtifactStore.verify(sha256)` cho original được giữ mà thiếu record xuất. Ghi lỗi chưa xử lý vào phiếu và giữ bản gốc để điều tra.
5. Ghép bản ghi theo `(document_id, original.sha256)` và dùng danh sách đầu vào để đối chiếu số lần xuất hiện, mục thiếu hoặc omission. Event ID, thời điểm acquisition và hash JSON record có thể khác khi chạy lại. So sánh thông tin trích xuất, số liệu và lỗi theo cùng fixture/golden, giữ cả hai batch để tái lập.

Phiếu cho mỗi lần chạy dùng các cột `case_id`, `input_index`, `document_id`, `original_sha256`, `format/layout`, `batch_id`, `annotation_version`, `criterion`, `expected_ref`, `observed_ref`, `status`, `issue_code` và `reviewer_id`. `expected_ref` trỏ tới locator golden hoặc mục kiểm tra thủ công, `observed_ref` trỏ tới block index hoặc mục manifest. Dùng `PASS`, `FAIL`, `NOT APPLICABLE` hoặc `NOT MEASURED`. Thiếu annotation hoặc chưa thực hiện kiểm tra được ghi `NOT MEASURED` và giữ số lượng mục chưa đo riêng trong tổng hợp.

## Bảng kiểm tra

| Tiêu chí | Kiểm tra và đầu ra cho mỗi lần chạy | Trạng thái pilot |
| --- | --- | --- |
| Text fidelity | Đối chiếu cùng đoạn nguồn đã chọn. Ghi nguyên văn bị thiếu, thêm hoặc sai và vị trí. Nếu có golden đầy đủ, có thể báo edit distance theo ký tự chia cho số ký tự tham chiếu khác 0. Công bố chuẩn hóa xuống dòng và mọi quy tắc trước khi so sánh. | NOT MEASURED |
| Reading order | Đối chiếu thứ tự của các đoạn, hàng hoặc cột được đánh dấu, kể cả đoạn lặp. Ghi cặp đảo thứ tự và đoạn thiếu. | NOT MEASURED |
| Heading preservation | Đối chiếu nội dung, cấp và thứ tự heading. Ghi heading bị bỏ hoặc chuyển thành paragraph. | NOT MEASURED |
| List preservation | Đối chiếu nội dung, vị trí mục và cấp lồng nhau. Ghi mục tách, gộp hoặc lệch cấp. | NOT MEASURED |
| Table preservation | Đối chiếu thứ tự hàng/cột, nội dung ô và quan hệ tiêu đề. Ghi cấu trúc mất khi bảng được xuất dạng text. | NOT MEASURED |
| Metadata completeness | Kiểm tra riêng title, language, authors và published_on. Đếm giá trị đúng, thiếu dù có căn cứ, `null` đúng khi nguồn thiếu và giá trị không có căn cứ. | NOT MEASURED |
| Provenance completeness | Đối chiếu source ID, locator công khai, thời điểm, event ID và original bằng manifest, store và registry snapshot. Ghi số tham chiếu hiện diện và khớp trên số được kiểm tra. | NOT MEASURED |
| Extraction success/partial/failed | Đếm các trạng thái trên số record xuất theo định dạng và layout. Báo thêm số input, record xuất và omission failed/skipped từ manifest. Kiểm tra thủ công các trường hợp status không tương xứng với phần mất quan sát được. | NOT MEASURED |
| Warnings/errors | Đếm theo mã, định dạng và layout. Báo số tài liệu có mã đó trên số tài liệu được đánh giá, cùng số lần xuất hiện nếu mã lặp. Tách mã omission và mã extractor. | NOT MEASURED |
| Original checksum integrity | So lại SHA-256, kích thước byte và tham chiếu. Ghi số original khớp, thiếu hoặc sai trên tổng số original cần kiểm tra. | NOT MEASURED |
| Coverage K01–K08 | Đếm tài liệu riêng biệt theo từng nhãn có căn cứ đoạn/trang do reviewer xác nhận. Ghi `unknown` và khoảng trống. `scope_candidates` chỉ hỗ trợ chọn mẫu. | NOT MEASURED |
| Rights status completeness | Đối chiếu `RecordRights.access_basis`, trạng thái reuse và evidence với quyết định còn hiệu lực. Tổng hợp quyền theo từng tài sản/hành động, tách `unknown`, `restricted`, `denied`, `allowed` và mục có căn cứ thiếu. | NOT MEASURED |

## Phiếu so sánh baseline

| Tiêu chí / định dạng | Baseline (kết quả, đã đo/tổng) | Lần đối chiếu (kết quả, đã đo/tổng) | Sai khác và tham chiếu |
| --- | --- | --- | --- |
| Mỗi hàng theo bảng kiểm tra | NOT MEASURED | NOT MEASURED | Điền khi có cùng tập original và reference phù hợp. |

Chỉ tính chênh lệch trên mẫu ghép cặp có bằng chứng cho cả hai lần chạy. Báo riêng `NOT APPLICABLE`, `NOT MEASURED`, tài liệu thiếu và khác biệt giữa các phiên bản nội dung. Review ca sai khác trước khi đề xuất tiêu chí nghiệm thu kỹ thuật. Việc đánh giá này đo fidelity và khả năng truy vết của pipeline. Ngưỡng nghiệm thu sẽ được xem xét khi có tập đại diện đã gán nhãn.
