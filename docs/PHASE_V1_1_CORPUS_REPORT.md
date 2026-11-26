# Phase V1.1 — báo cáo trước phê duyệt acquisition

> **Cập nhật thực thi 26/11/2026:** operator đã duyệt tải đúng batch ba PDF.
> Đã tải 3/3 original, tổng 922.665 byte, SHA-256 thực đã tính lại và khớp;
> 6 + 5 + 8 = 19 trang. Ba GET, không retry, redirect hoặc tải domain khác.
> Trang bài/CC BY-SA 4.0 được kiểm tra lại qua HTTPS trực tiếp (HTTP 200);
> công cụ web timeout được ghi riêng. Phần dưới là snapshot trước thực thi.
>
> CLI validate đạt; dry-run và preview trả exit 1 với
> `approval_missing_or_inactive` cho cả ba mục. Chưa có định danh người duyệt
> và thời hạn trusted grant; không tự nhận operator hay bật template.
> **0 tài liệu trích xuất bằng curated importer, 0 Structured Raw được verify,
> 0 tài liệu ready RAG.** Không tính việc đọc text để kiểm tra PDF là import.
>
> Agent đã xem render đủ 19 trang: mọi trang có text, chưa thấy dấu thay thế
> Unicode hoặc file đính kèm. Bài 488 có ba biểu đồ raster; text không bao phủ
> mọi nhãn trong hình. Layout hai cột/bảng ghép ô cần đối chiếu đầu ra sau
> preview. Bảng 4 nguồn bài 488 ghi n=93 nhưng tổng 82; giữ nguyên, không sửa
> số liệu. Human checklist vẫn `not_started`, mọi kết quả human đều pending.
>
> Original tại `data/vietnamese-medical-corpus/intake/`. Báo cáo thực thi,
> inventory SHA-256, source evidence, local manifest, render và checklist tại
> `data/vietnamese-medical-corpus/pilot-execution-20261126T045433Z/`, lần lượt
> `execution-report.md`, `execution-inventory.json`, `source-review.json`,
> `pilot.json`, `pdf-inspection/`, `human-review-checklist.json`.
> Grant request `operator-grant-request.UNSIGNED.json` chưa ký, inactive;
> operator cần cung cấp reviewer ID và expires_at thật trước import.
> Không commit corpus/approval. Regression: **895 passed, 2 skipped** trong
> 55,11 giây; Ruff lint/format PASS (96 file). Không thay code, không push.

Ngày: **26/11/2026**. Baseline: `1116fb0f57c782eea72efe1791cb9e800a4a7d5d`.
Đã đọc toàn bộ đặc tả v1.0, AGENTS và các tài liệu Phase V1 được yêu cầu.
Giữ nguyên đặc tả khóa, importer, PubMed, PMC và schema Structured Raw v0.1.
Không có thay đổi code: chưa có lỗi ngăn import thật được chứng minh.

## Kết quả thực tế

| Giai đoạn | Kết quả của phiên V1.1 |
|---|---|
| Nghiên cứu 15 ứng viên ban đầu | 15/15 đã thử đối chiếu lại; 14 trang chính thức mở được, trong đó 1 chỉ là công văn dẫn tới hướng dẫn; 1 timeout |
| Đối chiếu chính tài liệu/bài thay vì công văn | 13/15 có trang bài/PDF đọc được; toàn văn tiếng Việt của 2 bài trả metadata tiếng Anh chưa xác minh |
| Nguồn bổ sung có hồ sơ chi tiết | 8, gồm 3 PDF đề xuất batch và 5 mục dự phòng/xin phép |
| Bằng chứng giấy phép của batch | **3/3 có CC BY-SA 4.0 theo từng bài**, không suy từ open access |
| Rights review / source terms được operator phê duyệt | **0**; manifest vẫn `pending_review`, mọi `allowed_operations=[]` |
| File original thật đã lưu vào corpus | **0** |
| SHA-256 original / tài liệu trích xuất / Structured Raw mới | **0 / 0 / 0** |
| Human quality review đã hoàn tất / RAG sẵn sàng | **0 / 0** |
| Dữ liệu tổng hợp mới đưa vào corpus | **0**; fixture trong tests tách riêng |

Đã tìm được một batch có căn cứ giấy phép để trình operator; chưa hoàn thành
mục tiêu corpus thật. Không gộp URL, PDF đã đọc qua trình duyệt nghiên cứu,
HEAD response hoặc metadata thành file đã thu thập. Không có phép tải được
suy ra từ câu lệnh “START PHASE V1.1”: mục 6 của yêu cầu đòi hỏi duyệt đề xuất
acquisition cụ thể trước khi lấy original vào workspace.

## A–B. Danh sách, quyết định quyền và provenance nguồn

- [Bảng review đầy đủ từng mục](PHASE_V1_1_RIGHTS_REVIEW.md).
- [Hồ sơ metadata 23 mục](../config/vietnamese-medical-rights-review.v1.1.json).
- [Manifest 3 PDF tương thích importer](../config/vietnamese-medical-batch.v1.1.json).

`recommended_status=eligible` trong hồ sơ nghiên cứu là đề xuất cho 3 PDF,
không phải phê duyệt quyền. `status=pending_review` vẫn giữ cổng vận hành đóng.
Không tạo trusted grant, không tự nhận danh tính người duyệt, không đánh dấu
operator đã chấp thuận giấy phép. Người vận hành phải review riêng bằng chứng,
điều kiện ghi công/ShareAlike và tài sản bên thứ ba.

Phát hiện đáng chú ý: URL BCC TP.HCM cũ timeout, nhưng đã tìm và mở đúng
[URL chính thức thay thế](https://bvdl.org.vn/cong-dong/d-11422.1768.33/kien-thuc-y-khoa/ung-thu-bieu-mo-te-bao-day--chan-doan-va-dieu-tri.html).
Trang có PDF và thông báo bản quyền/ghi nguồn; chưa đủ để cấp toàn bộ thao tác
RAG. Bài hắc tố Y học Cộng đồng mở được qua endpoint không locale rồi chuyển
tới `/en/`, chưa chứng minh PDF tiếng Việt. Nguồn Đồng Nai là công văn triển
khai, chưa đối chiếu byte phụ lục với tài liệu hướng dẫn 4416. Không sửa hoặc
ghi đè manifest nghiên cứu v0.1; hồ sơ V1.1 giữ cả URL cũ và quan sát mới.

## Bản duyệt duy nhất cho batch đề xuất

Ba tài liệu đều do **Tạp chí Y Dược Thái Bình, Trường Đại học Y Dược Thái Bình**
xuất bản. Bằng chứng license nằm trên chính trang bài trong cột cuối:

| File đích trong `intake/` | PDF chính thức | Nội dung và bằng chứng license |
|---|---|---|
| `vn-tbjmp-atopic-488.pdf` | [488/449/1470](https://thaibinhjmp.vn/index.php/ojstbump/article/download/488/449/1470) | [Viêm da cơ địa ở sinh viên, 2025](https://thaibinhjmp.vn/index.php/ojstbump/article/view/488), 6 trang, K01/K03/K04 |
| `vn-tbjmp-acne-490.pdf` | [490/451/1474](https://thaibinhjmp.vn/index.php/ojstbump/article/download/490/451/1474) | [Mức độ trứng cá và yếu tố liên quan, 2025](https://thaibinhjmp.vn/index.php/ojstbump/article/view/490), 5 trang, K01/K02/K03/K04 |
| `vn-tbjmp-psoriasis-640.pdf` | [640/598/1930](https://thaibinhjmp.vn/index.php/ojstbump/article/download/640/598/1930) | [Đáp ứng tổn thương vảy nến với Secukinumab, 2026](https://thaibinhjmp.vn/index.php/ojstbump/article/view/640), 8 trang, K01/K03/K07 |

**Đề xuất thao tác:** lấy đúng 3 PDF qua HTTPS chính thức, lưu byte nguyên vẹn,
tính SHA-256; sau khi operator duyệt manifest và trusted grant theo checksum,
dry-run → preview → review chất lượng tiếng Việt bằng người → import/export
Structured Raw → verify. Chuẩn bị cho indexing RAG nội bộ trong tương lai;
phiên này không chunk, embedding, vector database hay triển khai RAG.

**Giới hạn:** tối đa 3 original, **8 MiB/file và 24 MiB tổng**, từng yêu cầu
tuần tự, tối đa 1 GET/file, dừng nếu vượt hạn mức, khác host, đòi đăng nhập,
paywall hoặc kiểm soát truy cập. Không tự retry tải, không tải ảnh/tham khảo
hay cả số tạp chí. Trạng thái hiện tại: **chờ operator duyệt**.

**Đích:** `data/vietnamese-medical-corpus/intake/`; ArtifactStore, text,
provenance, export và report tiếp tục nằm dưới `data/vietnamese-medical-corpus/`.
Không ghi đè file đã tồn tại, không commit các file corpus/approval.

**Điều kiện cần operator review:** [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
và [legal code, §2–4](https://creativecommons.org/licenses/by-sa/4.0/legalcode.en)
cho sao chép/chuyển thể với điều kiện áp dụng. Giữ tác giả, tên bài, tạp chí,
DOI, URL nguồn, copyright và link license; ghi rõ bản text là trích xuất tự
động, ghi giới hạn/thay đổi. Nếu chia sẻ tài liệu phái sinh, áp điều kiện
ShareAlike tương ứng; không suy rằng toàn bộ phần mềm phải đổi license.
Không nhận quyền đối với bộ câu hỏi/ảnh/tài liệu tham khảo chỉ vì được dẫn tên.

Đã đọc [submissions](https://thaibinhjmp.vn/index.php/ojstbump/about/submissions),
[quy định](https://thaibinhjmp.vn/index.php/ojstbump/quy_dinh_quy_trinh),
hướng dẫn thể lệ (nội dung nhúng Drive chưa review) và giấy phép từng bài.
`robots.txt` đọc trực tiếp bằng HTTP 200: chỉ `Disallow: /cache/`; endpoint PDF
không thuộc đường dẫn này. Robots là quy tắc truy cập, không phải license.
HEAD cho cả ba endpoint trả 200, `application/pdf`, không đổi URL. Content-Length
lần lượt **373569, 240159, 308937 byte**, tổng **922665 byte**; đây chỉ là header
tại thời điểm review, không phải byte đã nhận hoặc checksum.

## C–D. File thực nhận và kiểm kê checksum

Danh sách file mới thực nhận: **rỗng**. Không tạo checksum giả hoặc hash URL
thay cho hash original. Inventory vận hành:
`data/vietnamese-medical-corpus/phase-v1.1/acquisition-inventory.json` có
`real_documents=[]`, `original_checksums=[]`, `extractions=[]`, `exports=[]`.
Không kiểm kê gộp các corpus/demo lịch sử ngoài scope phiên này.

Manifest vận hành đã tạo tại
`data/vietnamese-medical-corpus/phase-v1.1/pilot.json`; mỗi `local_path`,
`expected_sha256`, `submitted_at` còn `null`. Không sửa `sources.json` cũ.

## E–F. Chất lượng tiếng Việt và điều kiện RAG

Đã đọc lớp text PDF trực tuyến để đối chiếu ngôn ngữ, tác giả, số trang,
phạm vi và thông báo quyền. Mẫu tiếng Việt có dấu đọc được. Một số từ tiếng
Anh bị ngắt có control character trong kết quả trình duyệt; chưa biết parser
hiện tại có tạo lỗi tương tự hay không. Không coi kết quả web là đầu ra importer.
Chưa hoàn tất kiểm tra hình render toàn bộ trang. Không khẳng định không có
ảnh/ngoại lệ quyền bằng việc chỉ tìm trong lớp text.

| ID | Human review | Extraction cục bộ | OCR / trùng hash | RAG |
|---|---|---|---|---|
| `vn-tbjmp-atopic-488` | `not_started` | Chưa chạy | Chưa đánh giá | false |
| `vn-tbjmp-acne-490` | `not_started` | Chưa chạy | Chưa đánh giá | false |
| `vn-tbjmp-psoriasis-640` | `not_started` | Chưa chạy | Chưa đánh giá | false |

Human quality review độc lập phải ràng buộc **SHA-256 original và text**, lưu
người duyệt/thời điểm/trang đã so sánh và kết quả từng tiêu chí: dấu Unicode,
thứ tự hai cột/đoạn/mục, bảng và số liệu, trang rỗng/garbled, OCR, metadata,
citation, trùng original, nội dung nhận diện bệnh nhân và tài sản bên thứ ba.
Trạng thái dùng `not_started`, `changes_required`, `passed` hoặc `rejected`;
chỉ người review có thẩm quyền mới điền `passed`. Bằng chứng mẫu nằm trong
hồ sơ V1.1; hồ sơ review thật chỉ lưu dưới `data/`.

Cờ `rag_eligible` hiện có của importer chỉ là gate kỹ thuật/quyền lúc chạy,
**chưa bao gồm phê duyệt fidelity bằng người**. Báo cáo V1.1 chỉ công nhận
`rag_ready` khi cả grant hiện hành, integrity, chất lượng kỹ thuật và human
review đều đạt. Không đổi schema/cờ production trước khi có lỗi import thật;
không dùng extraction success để tuyên bố độ chính xác y khoa.

Ba bài tập trung mô tả tổn thương viêm da cơ địa/trứng cá và quản lý tổn thương
vảy nến, có căn cứ K01–K08 đã nêu; không nhập dữ liệu bệnh án cá nhân hay mở
phạm vi thành toàn bộ da liễu. Các phần QoL hoặc YHCT ở nguồn dự phòng cần
review scope riêng. Batch này **chưa phủ melanoma, BCC, nốt ruồi hay soi da**.

## G–H. Xin phép và mở rộng 10–20 tài liệu

15 ứng viên cũ tiếp tục cần căn cứ quyền/review đầy đủ. Đặc biệt bài đăng lại
VnExpress/AAD và bản tham khảo DermNet cần giải quyết quyền nội dung gốc/bản
dịch/ảnh; không xin bệnh viện một cách chung chung rồi coi là đủ. Nguồn Huế
được khảo sát dùng CC BY-NC-ND: xếp `restricted` cho workflow đề xuất, không
kết luận rằng mọi cách xử lý nội bộ đều bị cấm. VJDV bài miễn dịch ung thư da
phù hợp chuyên khoa nhưng chưa có license rõ trên trang, ưu tiên xin phép.
Không gửi email hay liên hệ tác giả trong phiên này.

Lộ trình từ 3 lên 10: hoàn thành batch và đánh giá fidelity; review riêng các
bài Thái Bình 425, 367, 507 cùng bài liên quan 377 (chưa thêm như hồ sơ đã
xác minh), kiểm tra trùng quần thể/copyright bộ câu hỏi, chỉ giữ nội dung đúng
scope; song song xin quyền cho 3 bài trọng tâm melanoma/BCC/dày sừng trong
danh sách ban đầu. Đây là **mục tiêu 10**, không phải cam kết có 10 tài liệu đủ
quyền. Ưu tiên thay các bài QoL/YHCT nếu đóng góp tổn thương quá ít.

Từ 10 lên 20: duyệt từng lô 3–5 bài chuyên khoa qua license theo bài hoặc
permission chủ sở hữu, thêm nhãn bệnh/chủ đề đã có căn cứ, kiểm tra duplicate
bằng hash/DOI và quan hệ bản dịch. Không chia một tài liệu thành nhiều mục để
đạt chỉ tiêu, không tải cả issue, không bổ sung framework crawling. Mỗi lô
phải có bản duyệt acquisition mới và hồ sơ người duyệt, không kế thừa phép
của batch 3 sang URL khác.

## Kiểm thử và Git

| Kiểm tra | Kết quả |
|---|---|
| `python -m pytest -q` | 424 passed, **473 errors**, 80,24 giây; PermissionError temp Windows, không báo PASS |
| `python -m pytest -q -rs --basetemp=data/pytest-v11-release` | **895 passed, 2 skipped**, 44,86 giây |
| `python -m ruff check .` | PASS |
| `python -m ruff format --check .` | PASS, 96 file |
| CLI validate manifest batch | PASS, 3 documents; giữ pending |
| CLI create/check-files/report | PASS; 0 file, `local_file_not_declared` cho cả 3, không phải lỗi acquisition |
| Đối chiếu JSON, quyền đóng, Unicode và đặc tả khóa | PASS; 23 ID duy nhất, 3 mục được đề xuất, 0 quyền/grant kích hoạt, đặc tả khớp byte với HEAD |
| Dry-run/preview/import/export/verify trên file thật | **Chưa chạy**: thiếu acquisition được duyệt, file và trusted grant |

Hai skip do Windows thiếu quyền tạo symlink. Log kiểm thử thành công:
`data/phase-v11-pytest.log`. Automated tests dùng fixture cục bộ, bị chặn mạng.
Kiểm tra metadata, diff và staged diff trước commit. Commit bàn giao tài liệu:
`docs(corpus): document licensed Vietnamese pilot and acquisition gate`;
xem hash thực tế bằng `git log -1 --oneline`. Không push/merge.

## Thao tác tiếp theo sau khi operator duyệt

1. Duyệt bản batch phía trên: license/source terms, các thao tác, quota, đích
   lưu; ghi riêng danh tính người duyệt và phạm vi. Đồng ý vận hành không thay
   thế license của chủ sở hữu. Nếu chọn tải thủ công, mở từng PDF chính thức,
   Save As đúng tên trong bảng vào `intake/`, không in lại thành PDF.
2. Ghi thời điểm nhận, byte thực và hash bằng `Get-FileHash -Algorithm SHA256`;
   cập nhật **bản local** `phase-v1.1/pilot.json`, không điền vào manifest công
   khai. Operator review và điền `rights.status=reviewed` cùng từng thao tác
   thực sự cho phép, bằng chứng và điều kiện. Nếu có ngoại lệ quyền, giữ pending.
3. Chạy fingerprints/approval-template; người duyệt tạo trusted grant riêng
   gắn đúng fingerprint + checksum, quyền, tên, bằng chứng, thời hạn. Template
   do CLI tạo bị tắt/hết hạn; không tự kích hoạt hoặc sao chép quyền vào grant.
4. Chạy luồng sẵn có trong [CURATED_PUBLIC_IMPORT](CURATED_PUBLIC_IMPORT.md),
   dùng `--manifest data/vietnamese-medical-corpus/phase-v1.1/pilot.json`,
   `--max-bytes 8388608`, trusted-approvals do operator quản lý. Bắt đầu dry-run,
   preview và human review rồi import/verify. Export do import tạo; lấy đúng
   đường dẫn report/export trả về, không bịa run ID hoặc tạo export thứ hai.
5. Cập nhật inventory, SHA-256, extraction/human review, RAG assessment và báo
   cáo này từ kết quả thật; không đánh dấu hoàn tất khi chỉ có metadata.
