# Verified legacy backfill · Session 06C.2

`BackfillService` nối Structured Raw v0.1 vào catalog SQLite hiện có bằng mapping
tường minh. Công cụ chỉ ghi `legacy_reference`; không tạo source/document/revision,
không sửa metadata, nhãn hay policy, không cấp quyền lưu, extract, phân phối hoặc AI.
Các quyết định `unknown`/pending giữ nguyên. Không thay đổi schema SQLite v1.

## Đầu vào được kiểm soát

Người vận hành chọn domain và store đáng tin cậy. Tạo trước document, source item,
revision và rendition theo căn cứ đã review bằng API catalog. Mapping không suy ra
từ title, URL, tên file hay hash. `legacy_source_id` ràng buộc nguồn v0.1 với mapping
do reviewer chọn; source trong catalog có thể đại diện một provider khác cấp.
Không khôi phục `logical_key` từ `document_id` đã băm.

CLI đọc JSONL, mỗi dòng là một envelope phiên bản `0.1`:

```json
{"backfill_version":"0.1","domain_id":"public-fixtures","manifest_path":"batches/BATCH/manifest.json","manifest_sha256":"SHA256_OF_EXACT_MANIFEST_BYTES","mappings":[{"input_index":0,"legacy_source_id":"legacy-source","source_item_id":"reviewed-item","rendition_id":"reviewed-html"}]}
```

Đường dẫn manifest tương đối tính từ file JSONL; cũng có thể dùng đường dẫn tuyệt
đối cục bộ. Pin SHA-256 phải đủ 64 ký tự hex thường, lấy từ inventory đã review.
Giữ JSONL cùng bằng chứng review trong vùng được cấp quyền; báo cáo dùng
`batch_index` và `input_index` để đối chiếu mà không lặp lại ID, path, locator hay hash.
Không commit file đầu vào thật, originals, events hoặc database.

```powershell
python -m medical_data_crawler.backfill_cli --catalog data/catalog --domain public-fixtures --events data/events --originals data/originals --inputs data/reviewed-inputs.jsonl
# Sau khi kiểm tra báo cáo, thực thi cùng đầu vào:
python -m medical_data_crawler.backfill_cli --catalog data/catalog --domain public-fixtures --events data/events --originals data/originals --inputs data/reviewed-inputs.jsonl --execute
```

Mặc định là dry-run. CLI dùng SQLite URI `mode=ro`, không tạo catalog/domain và
không có giao dịch ghi. API Python nhận `DomainCatalog` đã được caller chọn:

```python
from medical_data_crawler.catalog.backfill import BackfillService
from medical_data_crawler.backfill_cli import read_inputs

for report in BackfillService(scope, provenance).run(read_inputs(input_path), dry_run=True):
    consume_report(report)  # xử lý từng báo cáo, không gom toàn corpus vào list
```

## Xác minh, kế hoạch và phục hồi

Mỗi envelope kiểm tra pin, schema, quota rồi gọi `verify_batch()` hiện có trước
bất kỳ publication nào. Verifier đối chiếu records, events, originals và omissions.
Record/event được đọc với giới hạn byte; original được hash theo stream. Catalog
và export legacy vẫn dùng API cũ; `verify_batch(..., max_file_bytes=...)` là tùy chọn
mới, không đổi mặc định cũ.

Trong một batch, lập kế hoạch theo `input_index`, kiểm tra nguồn, locator, domain,
document, rendition, format, byte size và SHA-256. Mapping trùng index luôn là
conflict, kể cả khai báo giống nhau. Các mapping đưa cùng legacy document sang
nhiều document trong batch đều chờ review trước khi ghi. Mapping khác chủ sở hữu
đã có trong catalog bị từ chối. Không dùng equality của URL/hash để ghép identity.

Thực thi đọc lại manifest pin, record/event và xác minh original ngay trước khi
ghi. Mỗi item dùng một `BEGIN IMMEDIATE`: kiểm tra lại binding/chủ sở hữu và ghi
reference trong cùng giao dịch. Lỗi trước commit rollback item đó; item đã commit
được giữ. Mất ACK sau commit có thể báo failed; rerun trả `already_linked`.
Không cần checkpoint ngoài database: chạy lại inventory từ đầu là an toàn.

Reference giữ legacy document ID, batch ID, event ID, record SHA-256, original
SHA-256, source ID, locator và thời điểm. Manifest gốc tiếp tục giữ `record_path`,
`input_index`, original reference và quyền v0.1; pin đầu vào giữ đúng inventory.
Không sửa originals, records, events hoặc manifests. Nối provenance cho record
extraction `failed` không biến nó thành nội dung extraction thành công.

## Báo cáo và giới hạn

Mỗi dòng stdout là báo cáo JSON `backfill_report_version=0.1`, có counts, reasons,
reconciliation, verification và kết quả từng input:

| Status | Ý nghĩa |
| --- | --- |
| `linked` | Đã commit reference mới |
| `already_linked` | Reference giống hệt đã tồn tại; không sửa |
| `needs_review` | Thiếu/trùng mapping, reference không có, sai binding hoặc conflict |
| `skipped` | `would_link` trong dry-run hoặc `legacy_omission` |
| `failed` | Integrity, I/O hoặc publication thất bại |

`verification=pass` xác nhận kiểm tra batch ban đầu. Lỗi khi đọc lại/publication
thể hiện ở từng item. Batch hỏng toàn vẹn chặn mọi item của batch. Manifest không
đọc được/pin sai chỉ báo các input đã biết từ mapping, không đoán inventory.
`extraction` giữ counts success/partial/failed từ manifest, và `legacy_gaps` nêu
thiếu logical key/locator block. Omissions được báo, không dựng record thay thế.
Exit code 0 khi không có lỗi/review; code 1 khi có lỗi hoặc cần review. Một lỗi
envelope hợp lệ không ngăn xử lý envelope sau; JSONL lỗi cú pháp dừng đọc file.

Giới hạn cố định: 128 inputs và 128 mapping declarations mỗi envelope, manifest
và mỗi dòng JSONL tối đa 256 KiB, mỗi record/event tối đa 8 MiB. Batch vượt giới
hạn bị từ chối để review/re-export có kiểm soát; không tách hay sửa manifest cũ.
API đọc từng batch và trả từng báo cáo nên bộ nhớ không tăng theo tổng corpus.

Dry-run đánh giá từng batch trên catalog hiện tại, không giả lập commit giữa các
batch. Vì vậy conflict chỉ xuất hiện sau một batch trước được commit có thể được
phát hiện lúc execute; không có reference hợp lệ nào bị đổi chủ. Không có giao
dịch xuyên filesystem/catalog hoặc toàn corpus. Root filesystem phải do operator
kiểm soát và không bị writer khác sửa đồng thời; hash không phải chữ ký chống sửa
đồng bộ. Công cụ không cấp quyền vận hành, không thay RBAC/ACL/thu hồi quyền và
không chuyển reader production sang catalog. Miền nội bộ vẫn cần store/ACL riêng.

## Demo và kiểm thử ngoại tuyến

```powershell
python scripts/demo_backfill.py
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

Demo tự tạo HTML/PDF và hai batch dưới `data/backfill-demo/`, gồm hai document,
nhiều version/rendition, hai nguồn có original HTML giống byte, PDF trống có giới
hạn extraction và omission thiếu access basis. Lần đầu: dry-run có 6 `would_link`,
execute có 6 `linked`, rerun có 6 `already_linked`; mỗi lượt có 2 omissions.
Chạy script lại tái sử dụng inventory đã tạo. Không tải dữ liệu hay crawl mạng.

Tests có network guard socket/DNS, fixture integrity hỏng, domain nội bộ/công khai,
mapping conflict, immutability, SQLite chỉ đọc, fault trước insert/sau insert/sau
commit, lazy corpus 2.000 batch và batch 128 mục với peak Python allocations dưới
24 MiB. Đây là kiểm chứng synthetic, chưa xác nhận hiệu năng corpus thật, mất điện
phần cứng hay chất lượng extraction y khoa.

Phiên tiếp theo đề xuất: 06C.3, discovery PubMed bằng payload tổng hợp/transport giả
và gate metadata theo trường; cần phê duyệt phạm vi phiên riêng, chưa mở crawl thật.
