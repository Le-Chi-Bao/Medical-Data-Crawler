# DEFINE_PROBLEM.md — Pipeline thu thập tài liệu y khoa

**Phiên bản:** 1.0  
**Trạng thái:** ĐÃ KHÓA — bộ yêu cầu nền tảng (đã thống nhất thiết kế, chưa xác nhận triển khai)  
**Ngày chốt:** 22/11/2026  
**Hệ thống sử dụng chính:** Medical RAG cho Skin Lesion Detection & Segmentation

## 1. Phát biểu bài toán

Kiến thức y khoa về tổn thương da (skin lesions) phân tán ở nhiều tài liệu và định dạng không đồng nhất. Thu thập thủ công gây khó khăn cho việc bảo toàn tài liệu gốc, duy trì cấu trúc nhất quán, xác định nguồn gốc và tái sử dụng nội dung đáng tin cậy. Dự án xác định một pipeline thu thập tài liệu có khả năng lưu giữ bản gốc và tạo ra dữ liệu thô có cấu trúc (Structured Raw), có thể truy vết và được kiểm tra tính hợp lệ về kỹ thuật, để cung cấp cho hệ thống Medical RAG ở giai đoạn sau.

Pipeline không phải hệ thống hỗ trợ quyết định lâm sàng; không chẩn đoán bệnh, không đánh giá phương án điều trị cho từng bệnh nhân và không tự xác nhận tính đúng đắn của các tuyên bố y khoa.

## 2. Các quyết định đã khóa

| ID | Quyết định | Nội dung đã thống nhất |
|---|---|---|
| PD-01 | Mục tiêu chính | Thu thập kiến thức cho Medical RAG, không xây dựng kho nghiên cứu tổng quát |
| PD-02 | Chiến lược phạm vi | Progressive Scope: bắt đầu từ tổn thương da; chỉ mở rộng khi có quyết định thay đổi phạm vi rõ ràng |
| PD-03 | Độ bao phủ MVP | Kiến thức toàn diện về Skin Lesions: hình thái tổn thương và bối cảnh lâm sàng |
| PD-04 | Đối tượng sử dụng | Người dùng phổ thông và người học/nghiên cứu y khoa |
| PD-05 | Mức độ hoàn thiện đầu ra | Structured Raw, chưa phải embedding hay dữ liệu đã xử lý hoàn chỉnh cho RAG |
| PD-06 | Bảo toàn dữ liệu | Giữ nguyên byte tài liệu đã tải và thông tin nguồn gốc có thể kiểm chứng |
| PD-07 | Giới hạn lâm sàng | Chỉ hỗ trợ truy xuất thông tin; không chẩn đoán hay tư vấn cá nhân hóa |

## 3. Mục tiêu dự án

- Thu thập tài liệu thuộc phạm vi từ các đầu vào đã cấu hình và được phép truy cập.
- Bảo toàn chính xác tài liệu gốc cùng checksum và thông tin truy vết quá trình thu thập.
- Trích xuất văn bản và khôi phục cấu trúc tài liệu trong khả năng kỹ thuật, không viết lại ý nghĩa y khoa.
- Tạo bản ghi Structured Raw có phiên bản và được kiểm tra theo schema.
- Cho phép theo dõi, chạy lại và xử lý lỗi riêng lẻ mà không ảnh hưởng toàn bộ pipeline.
- Hỗ trợ hệ thống phía sau lựa chọn theo phạm vi kiến thức và nhóm độc giả mà không bắt buộc suy đoán nhãn.

## 4. Phạm vi kiến thức MVP

Các nhóm sau là **những loại kiến thức được phép thu thập**, không yêu cầu mỗi tài liệu phải bao phủ tất cả. Một tài liệu có thể thuộc nhiều nhóm hoặc mang trạng thái `unknown`. Chưa khóa chỉ tiêu số lượng tài liệu theo nhóm trước khi có bộ dữ liệu đánh giá.

| ID | Nhóm kiến thức | Nội dung trong phạm vi | Ranh giới |
|---|---|---|---|
| K01 | Hình thái tổn thương (Lesion Morphology) | Hình dạng, kích thước, màu sắc, ranh giới, phân bố, bề mặt và thuật ngữ mô tả | Crawler không phân tích hình ảnh |
| K02 | Phân loại tổn thương (Lesion Classification) | Tổn thương nguyên phát/thứ phát, lành tính/ác tính, phân loại chưa xác định | Không suy luận chẩn đoán |
| K03 | Biểu hiện lâm sàng (Clinical Presentation) | Dấu hiệu, triệu chứng, diễn tiến và biểu hiện thường gặp | Không đánh giá bệnh nhân cụ thể |
| K04 | Yếu tố nguy cơ và căn nguyên (Risk Factors & Etiology) | Yếu tố nguy cơ, nguyên nhân, cơ chế được tài liệu mô tả | Giữ nguyên mức độ không chắc chắn của nguồn |
| K05 | Thông tin chẩn đoán (Diagnostic Information) | Khái niệm đánh giá lâm sàng, soi da, sinh thiết và xét nghiệm liên quan | Không đưa ra khuyến nghị chẩn đoán cá nhân |
| K06 | Chẩn đoán phân biệt (Differential Diagnosis) | Các tình trạng dễ nhầm lẫn và đặc điểm phân biệt được ghi nhận trong tài liệu | Không tự động chẩn đoán phân biệt |
| K07 | Quản lý và điều trị (Management & Treatment) | Nguyên tắc chung, theo dõi và thông tin điều trị trong tài liệu | Không kê đơn hoặc lập phác đồ cá nhân |
| K08 | Phòng ngừa và giáo dục người bệnh (Prevention & Patient Education) | Phòng ngừa, tự quan sát, dấu hiệu cần tìm hỗ trợ y tế | Không thay thế chăm sóc lâm sàng |

### Quy tắc mở rộng theo Progressive Scope

MVP tập trung vào kiến thức tổn thương da thuộc K01–K08. Các chủ đề da liễu rộng hơn, chuyên ngành hẹp và loại dữ liệu mới không tự động nằm trong phạm vi. Mọi đề xuất mở rộng cần có biên bản thay đổi ghi rõ lý do, ranh giới nhóm kiến thức mới, ảnh hưởng đến dữ liệu xuất/schema và kiểm thử nghiệm thu.

## 5. Chính sách đối tượng sử dụng

- `general`: tài liệu giáo dục dễ tiếp cận cho người dùng phổ thông.
- `medical`: tài liệu chuyên môn hoặc định hướng nghiên cứu.
- `mixed`: phù hợp với cả hai nhóm khi có căn cứ.
- `unknown`: chưa đủ căn cứ để xác định.

Pipeline không được tự đơn giản hóa văn bản chuyên môn, biến đổi phát biểu y khoa hoặc ép tài liệu vào một nhãn đối tượng. Việc gán nhãn có thể để cho bước xử lý phía sau; nếu crawler gán nhãn, phải lưu căn cứ xác định nhãn.

## 6. Ranh giới hệ thống

### Trong phạm vi

1. Thu thập tài liệu và ghi trạng thái cho từng tài liệu.
2. Bảo toàn byte gốc theo cách bất biến hoặc lưu trữ tương đương dựa trên hàm băm nội dung.
3. Trích xuất có cấu trúc: văn bản, tiêu đề, đoạn văn, danh sách và bảng khi hỗ trợ được.
4. Quản lý metadata, nguồn gốc, kiểm tra toàn vẹn và cảnh báo trích xuất.
5. Phát hiện bản gốc trùng hoàn toàn bằng checksum; phát hiện gần trùng là tùy chọn/tương lai.
6. Kiểm tra tính hợp lệ kỹ thuật, cô lập lỗi và xuất dữ liệu có thể tái lập.
7. Hợp đồng dữ liệu đầu ra và manifest có phiên bản.
8. Tuân thủ quyền truy cập, điều khoản sử dụng và quyền tái sử dụng tài liệu.

### Ngoài phạm vi

- Chunking, embedding, vector database, truy xuất RAG và sinh câu trả lời.
- Huấn luyện mô hình, phân đoạn ảnh và phân loại tổn thương từ hình ảnh.
- Kiểm chứng sự thật y khoa, suy luận chẩn đoán và tư vấn điều trị cá nhân.
- Tự động diễn giải lại hoặc dịch nội dung y khoa của nguồn.
- Mở rộng thành kho tài liệu nghiên cứu đa mục đích trong MVP.
- Cam kết trích xuất đầy đủ mọi hình, bản scan hoặc bảng PDF phức tạp.

## 7. Yêu cầu chức năng

| ID | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-01 | Thu thập tài liệu được phép và đã cấu hình, ghi trạng thái từng mục | Bắt buộc |
| FR-02 | Giữ nguyên byte gốc và checksum có thể kiểm chứng | Bắt buộc |
| FR-03 | Trích xuất các khối văn bản theo đúng thứ tự và cấu trúc có thể nhận diện | Bắt buộc |
| FR-04 | Ghi định danh tài liệu ổn định và thông tin nguồn gốc | Bắt buộc |
| FR-05 | Phát hiện bản gốc trùng hoàn toàn, tránh lưu bản sao không kiểm soát | Bắt buộc |
| FR-06 | Kiểm tra tính hợp lệ của file và bản ghi có cấu trúc | Bắt buộc |
| FR-07 | Cô lập lỗi, ghi nhật ký lỗi và hỗ trợ chạy lại | Bắt buộc |
| FR-08 | Xuất bản ghi và manifest theo phiên bản schema | Bắt buộc |
| FR-09 | Biểu diễn rõ trường thiếu, giới hạn trích xuất và thông tin chưa chắc chắn | Bắt buộc |
| FR-10 | Hỗ trợ mở rộng phạm vi kiến thức mà không làm mất hiệu lực dữ liệu cũ | Nên có |

## 8. Hợp đồng đầu ra ở mức logic (chưa khóa schema JSON vật lý)

Mỗi tài liệu được chấp nhận có các thành phần:

- `document_id`: định danh logic ổn định; cách tạo cụ thể sẽ quyết định ở giai đoạn kiến trúc.
- `schema_version`: phiên bản cấu trúc bản ghi xuất ra.
- `source`: định danh nguồn hoặc URI, thời điểm thu thập, ngữ cảnh truy xuất.
- `original`: tham chiếu tới file gốc bất biến, loại nội dung, kích thước byte, checksum SHA-256.
- `content`: các khối nội dung đã trích xuất theo thứ tự, loại khối, cấp cấu trúc và văn bản; đánh dấu rõ nếu chỉ trích xuất một phần.
- `metadata`: tiêu đề, ngôn ngữ, tác giả, ngày xuất bản khi có căn cứ; nếu không thì `null`/`unknown`.
- `scope`: không, một hoặc nhiều nhãn kiến thức được hỗ trợ, hoặc `unknown`.
- `audience`: `general`, `medical`, `mixed` hoặc `unknown`.
- `extraction`: trạng thái, phương pháp/phiên bản, cảnh báo và lỗi.
- `rights`: thông tin đã biết về quyền truy cập/tái sử dụng hoặc `unknown`; trạng thái chưa biết không có nghĩa là được phép phân phối lại.

Tài liệu có bản gốc hợp lệ nhưng trích xuất thất bại vẫn phải có bản ghi lỗi để truy vết; không được âm thầm xuất như tài liệu văn bản đã xử lý thành công.

## 9. Yêu cầu phi chức năng

- **Toàn vẹn dữ liệu:** Có thể kiểm tra bản gốc bằng checksum đã lưu.
- **Truy vết:** Mỗi khối nội dung trích xuất liên kết được với file gốc và bản ghi nguồn.
- **Độ tin cậy:** Lỗi của một tài liệu không làm hỏng kết quả khác.
- **Khả năng tái lập:** Lưu phiên bản công cụ và cấu hình trích xuất quan trọng; không mặc định các phiên bản công cụ khác nhau cho đầu ra giống hệt từng byte.
- **Khả năng mở rộng:** Nguồn đầu vào hoặc extractor mới không được âm thầm thay đổi ý nghĩa dữ liệu cũ.
- **Khả năng bảo trì:** Trách nhiệm module rõ ràng, có kiểm thử tự động.
- **Tuân thủ:** Tôn trọng kiểm soát truy cập, điều khoản và giấy phép; ghi trạng thái quyền sử dụng.
- **Bảo mật và quyền riêng tư:** Không chủ đích thu thập thông tin định danh bệnh nhân; dữ liệu nhạy cảm ngoài dự kiến phải được cách ly hoặc từ chối theo chính sách xác định.

## 10. Tiêu chí nghiệm thu MVP

Đây là điều kiện để nghiệm thu bản phát hành, **không phải tuyên bố rằng code hiện tại đã đạt**.

| ID | Điều kiện nghiệm thu | Cách kiểm chứng |
|---|---|---|
| AC-01 | 100% tài liệu được chấp nhận có ID ổn định và nguồn xác định được | Kiểm tra schema trên bộ mẫu được chấp nhận |
| AC-02 | 100% file gốc được chấp nhận có tham chiếu lưu trữ và SHA-256 khớp | Tính lại hash trên bộ test |
| AC-03 | Mỗi bản trích xuất thành công truy được đúng file gốc | Kiểm thử toàn vẹn tham chiếu |
| AC-04 | 100% bản ghi xuất thành công đạt schema đã khai báo | Kiểm tra schema tự động |
| AC-05 | Thu thập lại file gốc giống hệt không tạo bản sao ngoài kiểm soát | Kiểm thử tính idempotent |
| AC-06 | Một tài liệu lỗi/không hợp lệ không làm dừng xử lý các tài liệu khác | Kiểm thử batch gồm cả thành công và thất bại |
| AC-07 | Metadata thiếu/chưa chắc chắn và trích xuất một phần được biểu diễn rõ | Kiểm thử tình huống biên |
| AC-08 | Dữ liệu xuất không chứa chunk RAG, embedding hay vector index | Kiểm tra đầu ra và ranh giới pipeline |
| AC-09 | Quyền tái sử dụng bị hạn chế/chưa xác minh không bị mặc định là quyền phân phối lại | Kiểm thử chính sách quyền sử dụng |
| AC-10 | Schema biểu diễn được cả 8 nhóm kiến thức mà không ép nhãn thiếu căn cứ | Kiểm thử schema và bộ mẫu |

### Các chỉ số chất lượng cần xác lập trong giai đoạn pilot

- Tỷ lệ trích xuất thành công theo định dạng.
- Mức độ bảo toàn văn bản so với mẫu nguồn được kiểm tra thủ công.
- Mức độ bảo toàn cấu trúc tiêu đề, thứ tự, danh sách và bảng.
- Độ đầy đủ của thông tin truy vết và tỷ lệ tài liệu chưa xác minh quyền tái sử dụng.
- Hiệu quả cô lập lỗi và phục hồi.

Không đặt ngưỡng độ chính xác trích xuất tùy ý trước khi có bộ dữ liệu đánh giá đại diện và được gán nhãn.

## 11. Giả định và rủi ro

1. Chất lượng trích xuất kỹ thuật khác với tính đúng đắn hoặc tính cập nhật của kiến thức lâm sàng.
2. Một tài liệu có thể phục vụ nhiều nhóm độc giả và thuộc nhiều nhóm kiến thức.
3. Bản scan, hình ảnh, bảng và công thức phức tạp có thể không được trích xuất đầy đủ; phải thể hiện rõ giới hạn.
4. Tài liệu truy cập công khai không mặc nhiên được phép tái sử dụng không giới hạn.
5. Kho kiến thức bao phủ một bệnh không có nghĩa mô hình thị giác có thể nhận diện hay chẩn đoán bệnh đó.
6. Cần tránh thu thập dữ liệu định danh bệnh nhân và không làm rò rỉ nội dung nhạy cảm qua log hoặc file xuất.

## 12. Quản lý thay đổi và bàn giao

Tài liệu này khóa **MVP cần đạt điều gì**, không khóa **cách triển khai**. Việc lựa chọn nguồn dữ liệu, quyền crawl từng website, bộ công nghệ, schema vật lý, cấu trúc lưu trữ, thuật toán trích xuất, thông lượng và ngưỡng chất lượng vẫn để ngỏ cho các giai đoạn thiết kế sau. Mọi sửa đổi cần có biên bản quyết định ghi ngày, lý do, yêu cầu bị ảnh hưởng và thay đổi tương ứng trong kiểm thử nghiệm thu.

**Trạng thái:** Problem Definition v1.0 đã khóa. **Chưa bắt đầu giai đoạn tiếp theo.**
