# Tiếp nhận tài liệu nội bộ ngoại tuyến

`InternalIntakeGateway` là entrypoint cho các lệnh import HTML, HTM và PDF nội bộ.
Gateway xử lý từng mục theo thứ tự trong đặc tả, dùng quyền đã xác minh để đọc,
lưu bản gốc và trích xuất. Session 06B dùng tài liệu tổng hợp. Gọi trực tiếp
`LocalDocumentAdapter` bỏ qua chính sách quyền và file của gateway. Luồng batch
cấp ứng dụng luôn gọi gateway.

## Ranh giới phê duyệt

Người vận hành có thẩm quyền cung cấp hồ sơ phê duyệt qua kênh riêng, giữ quyền ghi
file phê duyệt, cấu hình ứng dụng và thư mục trạng thái trong tài khoản được tin
cậy. Người bàn giao cung cấp đặc tả đầu vào và file đã khai báo. Quyền sửa đặc tả
đầu vào và quyền phê duyệt cần được tách ở cấp tài khoản hoặc quy trình vận hành.
CLI tin vào hồ sơ mà người vận hành chỉ định qua `--trusted-approvals`. Nếu mở
CLI cho người bàn giao tự chọn hồ sơ phê duyệt thì người đó có thể tự cấp quyền.
Các trường provider và authorization trong JSON là tham chiếu nghiệp vụ. Việc xác
minh danh tính thực tế và bảo vệ hồ sơ hiện do tổ chức và quyền filesystem đảm
nhiệm. Xác thực tập trung và phân quyền ứng dụng thuộc giai đoạn tích hợp sau.

Trước khi mở file, gateway kiểm tra định danh nguồn nội bộ, phê duyệt còn hiệu
lực, tác vụ `internal_import`, liên kết chính xác giữa định danh và đường dẫn,
quyền đọc và quyền lưu original. Gateway đối chiếu hồ sơ phê duyệt riêng với
đặc tả người bàn giao. Registry web dùng cho luồng HTTPS. HTML preflight chỉ hỗ
trợ người review xem xét metadata.

## Đặc tả đầu vào

Đặc tả là một JSON UTF-8 có `intake_version` bằng `"0.1"` và một mảng
`documents` liệt kê từng tài liệu. CLI giới hạn mỗi file JSON ở 1 MiB.
Đặc tả và hồ sơ phê duyệt chứa tối đa 1.000 mục mỗi file. Mỗi tài liệu chấp
nhận các trường sau.

| Trường | Ý nghĩa |
| --- | --- |
| `source_id` | Mã nguồn nội bộ có tiền tố `internal-`. |
| `logical_key` | Khóa ổn định của tài liệu trong nguồn. Giữ cùng khóa khi cập nhật byte của cùng tài liệu. |
| `locator` | Tham chiếu nội bộ an toàn dạng `internal:<slug>`. |
| `local_path` | Đường dẫn tuyệt đối riêng tư đến một file trong intake root đã chỉ định. |
| `format` | `html`, `htm` hoặc `pdf`. |
| `provider_ref` | Mã tham chiếu đã loại thông tin nhạy cảm của bên bàn giao. |
| `authorization_ref` | Mã hồ sơ tra cứu trong tập phê duyệt đáng tin cậy. |
| `allow_store` | Boolean khai báo quyền lưu original. |
| `allow_extract` | Boolean khai báo quyền trích xuất và lưu text nội bộ. |
| `access_basis` | Mã căn cứ truy cập do người vận hành kiểm soát. |
| `expected_sha256` | Tùy chọn. SHA-256 gồm 64 chữ số hex thường. |
| `reuse` | Tùy chọn. `unknown` mặc định, `restricted` hoặc `permitted` khi có phê duyệt tương ứng. |

Mã định danh dùng chữ ASCII thường, số và dấu phân cách `.`, `_`, `-`. Mỗi
slug tối đa 64 ký tự và bắt đầu bằng chữ. `source_id` dài tối đa 64 ký tự
tính cả tiền tố. Dùng mã nghiệp vụ trung tính vì các
trường nguồn, locator và tham chiếu phê duyệt xuất hiện trong hồ sơ liên quan.
Giữ đường dẫn, tên bệnh nhân, token và mô tả mật trong kênh bàn giao được bảo
vệ. Định danh tài liệu trong output được suy từ cặp `source_id` và `logical_key`.

Ví dụ đặc tả cho một fixture tại Windows.

```json
{
  "intake_version": "0.1",
  "documents": [
    {
      "source_id": "internal-fixture",
      "logical_key": "fixture-a",
      "locator": "internal:fixture-a",
      "local_path": "C:/intake/fixture-a.html",
      "format": "html",
      "provider_ref": "provider-fixture",
      "authorization_ref": "approval-fixture-a",
      "allow_store": true,
      "allow_extract": true,
      "access_basis": "internal_authorization"
    }
  ]
}
```

Hồ sơ phê duyệt dùng envelope `{"authorization_version":"0.1","authorizations":[...]}`.
Mỗi phê duyệt mang các trường như mục trong đặc tả và thêm `active`, `expires_at`,
`operation` và `allow_read`. `expires_at` dùng timestamp ISO 8601 có chỉ báo
`Z` hoặc offset múi giờ. Mỗi `authorization_ref` trong hồ sơ là duy nhất.
Ví dụ hồ sơ cho fixture trên, do người vận hành cung cấp riêng.

```json
{
  "authorization_version": "0.1",
  "authorizations": [
    {
      "source_id": "internal-fixture",
      "logical_key": "fixture-a",
      "locator": "internal:fixture-a",
      "local_path": "C:/intake/fixture-a.html",
      "format": "html",
      "provider_ref": "provider-fixture",
      "authorization_ref": "approval-fixture-a",
      "allow_store": true,
      "allow_extract": true,
      "access_basis": "internal_authorization",
      "active": true,
      "expires_at": "2030-01-02T08:00:00+07:00",
      "operation": "internal_import",
      "allow_read": true
    }
  ]
}
```

Quyền lưu và quyền trích xuất áp dụng khi cả đặc tả và hồ sơ phê duyệt cấp quyền
tương ứng. Mục đủ quyền đọc/lưu nhưng thiếu quyền trích xuất chỉ lưu original
và provenance, báo `extraction_not_authorized`. Quyền tái sử dụng đã biết phải
khớp hồ sơ cấp quyền, còn `unknown` giữ nguyên trong bản ghi. Mọi đầu ra được
giữ nội bộ. Phân phối công khai, chia sẻ bên ngoài, RAG và huấn luyện cần quyết
định quyền riêng cho từng mục đích.

## Chạy batch và xác minh

Chạy từ virtual environment đã cài package. Chọn intake root và state root cục
bộ thuộc quyền quản lý của người vận hành. Có thể lặp `--intake-root` để khai
báo nhiều vùng được duyệt.

```powershell
python -m medical_data_crawler.internal_import_cli --spec .\request.json --trusted-approvals .\operator\approvals.json --intake-root C:/intake --state-root .\data\internal-intake --dry-run
python -m medical_data_crawler.internal_import_cli --spec .\request.json --trusted-approvals .\operator\approvals.json --intake-root C:/intake --state-root .\data\internal-intake
```

Dry-run kiểm tra phê duyệt, file, định dạng và SHA-256 bằng snapshot trong RAM.
Báo cáo dùng trạng thái validation, state root không nhận original hay event,
và workflow bỏ qua extractor cùng bước export. Khi import thật, gateway kiểm
tra lại từ đầu. Mặc định mỗi file tối đa 32 MiB. Có thể hạ giới hạn theo byte
qua `--max-bytes`. Gateway chặn đầu vào rỗng, sai định dạng, hỏng cấu trúc, quá
giới hạn hoặc hash sai. Khi hồ sơ phê duyệt ghi checksum, gateway áp dụng
checksum đó kể cả khi đặc tả bỏ trống trường này. File cần là file thường
trên vùng cục bộ được duyệt.
Kiểm tra đường dẫn loại symlink, junction/reparse point, UNC, ổ mạng được ánh
xạ trên Windows và traversal. Snapshot giới hạn kích thước và kiểm tra dấu
hiệu file thay đổi hoặc thiếu byte trong lúc đọc. Store đối chiếu SHA-256 ngay
trước khi công bố original. Trên POSIX, người vận hành cấp thư mục intake,
state và temp trên filesystem cục bộ được tin cậy. Đường dẫn mount cục bộ có
thể che giấu backend từ xa.

Khi được phép lưu, byte gốc nằm ở `originals/<sha256>` dưới state root.
ArtifactStore dùng lại byte trùng đã xác minh. Mỗi lần tiếp nhận được chấp nhận
có một event riêng tại `provenance/<event_id>.json`, kể cả khi tài liệu và
original trùng. Event liên kết document ID, locator, thời điểm, hash và chứng
cứ phê duyệt an toàn. Filesystem của state root cần hỗ trợ hard link.

Gateway xuất các record đủ điều kiện qua `export_batch()`, sau đó đọc lại
manifest bằng `verify_batch()`. Nếu có batch xuất, lấy `batch_id` từ trường
`export` trong báo cáo để tìm `exports/<batch_id>/manifest.json`. Manifest
giữ hợp đồng v0.1. Báo cáo tiếp nhận giữ đủ số lượng đầu vào, kể cả mục từ
chối và lưu original đơn thuần. `input_index` bắt đầu từ 0 theo đặc tả.
`export_input_index` liên kết mục đã gửi tới exporter với index trong manifest.
Kết quả extraction hỏng vẫn có thể có record Structured Raw hợp lệ mang
trạng thái `failed`. Kiểm tra trạng thái của mục và `summary` cùng kết quả
xác minh để phân biệt tính toàn vẹn batch với chất lượng trích xuất.

CLI in JSON ra stdout với tổng hợp và kết quả từng mục. Mã thoát `0` biểu thị
batch hợp lệ theo quyền đã cấp, kể cả mục chỉ lưu original. Mã `1` biểu thị
có mục lỗi hoặc lỗi xuất/xác minh batch. Mã `2` biểu thị lỗi đối số hoặc cấu
hình, kèm mã cố định trên stderr.

## Xử lý lỗi và bảo vệ dữ liệu

- Với `authorization_missing`, `authorization_expired` hoặc
  `authorization_binding_mismatch`, tra cứu hồ sơ qua kênh người vận hành và
  xác minh lại tài liệu trước khi cấp lại quyền. Với `storage_not_authorized`,
  kiểm tra quyền lưu riêng. Những mục bị từ chối trước khi đọc không tạo
  original hoặc accepted event.
- Với `file_changed` hoặc `checksum_mismatch`, xác nhận lại byte nguồn và
  đợi hoàn tất bàn giao trước khi gửi lại. Với lỗi định dạng, dùng bản gốc
  đúng định dạng từ bên bàn giao. Giữ nguyên original đã lưu.
- Nếu export hoặc ghi provenance thất bại, xử lý nguyên nhân filesystem rồi
  gửi lại các mục cần xử lý. Lần thử mới có event mới khi được chấp nhận và
  dùng lại artifact nếu byte trùng. File original hợp lệ đã công bố có thể
  còn lại khi ghi event không thành công. Store và provenance không dùng chung
  transaction.

CLI và báo cáo dùng mã cố định. Đường dẫn vận hành và tên file chỉ cần trong
config được bảo vệ. Byte gốc, nội dung trích xuất và metadata có thể chứa dữ
liệu nhạy cảm. Bảo vệ state root, cache/temp của tài khoản vận hành, file phê
duyệt và mọi bản sao theo cùng chính sách nội bộ. Bộ kiểm tra định dạng nhận
diện markup HTML và kiểm tra cấu trúc PDF. PDF mã hóa có thể qua kiểm tra cấu
trúc và báo lỗi khi trích xuất. Nội dung phức tạp vẫn có thể phát sinh lỗi khi
extractor đọc sâu hơn. RAM và CPU của parser phụ thuộc vào cấu trúc tài liệu,
kể cả khi byte nguồn đã qua giới hạn kích thước. HTML/PDF được đọc cục bộ
qua parser, bỏ qua mã nhúng và tài nguyên bên ngoài. Việc đánh giá PHI, quyền
truy cập và phân loại nhạy cảm cần có người phụ trách.

Khi tổ chức cho phép bàn giao tài liệu thật, người phụ trách chọn từng mục
thuộc phạm vi MVP, cấp mã trung tính, xác nhận quyền đọc/lưu/trích xuất và
đặt thời hạn cho phê duyệt riêng. Nên ghi checksum tin cậy ngay khi bàn giao
để ràng buộc cả phiên bản byte. Người vận hành đưa các file đã review vào
intake root được bảo vệ, chạy dry-run, xử lý kết quả từ chối rồi mới chạy
import. Chạy thử quy trình với fixture tổng hợp bằng
`python scripts/demo_internal_import.py`.
