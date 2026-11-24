# Kiểm tra sơ bộ HTML ngoại tuyến · Session 05B-3

Reviewer chạy inspector trên một bản gốc HTML đã có sẵn hợp pháp và được phép đọc. Đặt file trên ổ cục bộ do reviewer kiểm soát và giữ nguyên file trong khi kiểm tra. Kết quả dùng để điền [hồ sơ thẩm định](PILOT_APPROVAL_PACK.md).

## Cách chạy

Từ root của repo, cài package vào virtual environment theo [README](../README.md), kích hoạt môi trường rồi chạy với fixture tổng hợp.

```powershell
python -B scripts/inspect_html_preflight.py tests/fixtures/synthetic.html
```

Sau khi có bản gốc được phép đọc, truyền đường dẫn cục bộ của bản đó. `--max-bytes` đặt giới hạn đọc, mặc định 1 MiB (1.048.576 byte), tối đa 4 MiB (4.194.304 byte). Script in JSON ra stdout để reviewer có thể dùng trong hồ sơ. Mã thoát `0` đi với `REVIEW_REQUIRED`, `1` đi với `INSPECTION_INCOMPLETE` và `2` báo đối số CLI không hợp lệ.

Nếu đã có chứng cứ HTTP lưu riêng, có thể đánh dấu tên trường bằng `--http-evidence-field` lặp lại. Ví dụ dưới đây chỉ minh họa cú pháp báo một trường đã được cung cấp.

```powershell
python -B scripts/inspect_html_preflight.py tests/fixtures/synthetic.html --http-evidence-field status_code
```

Các lựa chọn gồm `content_type`, `status_code`, `redirect_chain`, `final_destination` và `response_headers`. `supplied` cho biết reviewer báo đã có chứng cứ, còn `missing_evidence` liệt kê trường chưa được cung cấp. Mọi trường vẫn mang `NOT VERIFIED`. Hậu tố `.html`, khai báo HTML và meta `Content-Type` chỉ là dấu hiệu cục bộ. Reviewer đối chiếu chứng cứ của đúng lần truy cập và đúng bản gốc để xác nhận kiểu nội dung HTTP thực tế, status, các lần redirect, đích cuối và header máy chủ. Chỉ truyền tên trường, giữ URL, header và chứng cứ gốc trong hồ sơ được phân quyền.

## Đọc kết quả

| Trường | Ý nghĩa |
| --- | --- |
| `inspector_version`, `inspected_at` | Phiên bản công cụ và thời điểm UTC. |
| `byte_size`, `sha256` | Kích thước và SHA-256 của byte đã đọc. File bị từ chối có `sha256` là `null` và chỉ có kích thước khi xác định được. |
| `parse_status`, `encoding` | `PARSED`, `PARTIAL`, `FAILED` hoặc `NOT_ATTEMPTED`. Encoding gồm nhãn đã chuẩn hóa trong danh sách hỗ trợ, BOM và codec đã dùng. Nhãn lạ được ghi thành `UNSUPPORTED`. |
| `counts`, `findings` | Các số đếm dương theo khóa cố định và mã phát hiện có ưu tiên `HIGH` hoặc `REVIEW`. Một cấu trúc có thể đóng góp vào nhiều số đếm. |
| `manual_review`, `review_readiness` | Các hạng mục luôn cần reviewer kiểm tra. `REVIEW_REQUIRED` báo đã hoàn thành lượt quét kỹ thuật. `INSPECTION_INCOMPLETE` báo lỗi đọc, lỗi giải mã hoặc giới hạn phân tích đã phát hiện. |

Lượt quét ghi nhận script nội tuyến, tham chiếu script, SVG nội tuyến, URL `data:` và dấu `;base64`, iframe và `srcdoc`, frame, object/embed, ảnh, CSS, media, `base href`, meta refresh, thuộc tính sự kiện, URL `javascript:`, template và form. Các số đếm tham chiếu ảnh, CSS, script và media có thể gồm cả tham chiếu tương đối và tài nguyên nhúng. Khóa `remote_*` chỉ đếm tham chiếu có dạng HTTP(S) hoặc bắt đầu bằng `//`. Inspector chỉ ghi nhận sự hiện diện của `base href` và không dùng nó để phân giải đường dẫn.

## Giới hạn

- Inspector đọc file thường ở chế độ chỉ đọc, từ chối symlink, reparse point, đường dẫn mạng rõ ràng và ổ mạng được gán ký tự trên Windows. Dùng filesystem cục bộ ổn định vì công cụ không xác minh được mọi mount từ xa hoặc mọi thay đổi đồng thời. Khi file vượt giới hạn, inspector dừng và để trống SHA-256.
- Inspector dùng `HTMLParser` để đếm token. Dấu hiệu lỗi gồm markup dang dở, thuộc tính trùng và lỗi parser. Trạng thái `PARSED` chỉ mô tả lượt quét, chưa xác nhận cấu trúc HTML5 hoặc hành vi trình duyệt. Nội dung `srcdoc`, base64, CSS/JavaScript động, tài nguyên tải từ xa và URL CSS viết bằng escape có thể chứa dữ liệu ngoài phần quét. Inspector không render, chạy mã, giải mã payload nhúng, mở URL hoặc gửi HTTP request.
- Inspector ưu tiên BOM, sau đó thử khai báo ASCII-compatible trong 1.024 byte đầu, với UTF-8 làm mặc định. Inspector hỗ trợ UTF-8, ASCII, Windows-1252, ISO-8859-1 và UTF-16/32 với BOM. Xung đột khai báo, codec ngoài danh sách, byte phải thay thế và ký tự điều khiển được báo theo mã. Hai encoding đôi khi cùng giải mã được một chuỗi byte, nên lượt quét có thể bỏ sót khai báo sai.
- Form, trường ẩn, nhãn như MRN, ngày sinh và chuỗi giống email là dấu hiệu để rà thủ công. Có thể có cả báo nhầm và bỏ sót, đặc biệt trong ảnh, payload, mã động và ngôn ngữ ngoài mẫu dò. Reviewer luôn phải rà privacy/PHI, kể cả khi số đếm không có dấu hiệu.
- Báo cáo chỉ có metadata, mã và số đếm. Inspector không ghi đường dẫn đầu vào, HTML, URL, header HTTP, giá trị thuộc tính, script, byte hình ảnh hoặc giá trị định danh vào báo cáo. Công cụ không lưu file báo cáo, đưa original vào ArtifactStore, ghi provenance, hoặc tạo export batch. Quyết định về quyền truy cập, quyền lưu, tài sản nhúng, bên thứ ba và privacy thuộc reviewer theo [chính sách pilot](INTERNAL_PILOT_POLICY.md).
