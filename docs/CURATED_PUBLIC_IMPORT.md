# Corpus y khoa tiếng Việt: tiếp nhận tài liệu công khai đã tuyển chọn

Luồng `CuratedPublicDocumentImporter` nhận file PDF/HTML/HTM cục bộ, hoàn toàn
ngoại tuyến. Không có downloader hoặc discovery tự động trong CLI này.
Đây là nguồn `curated-public`, không phải tài liệu bệnh viện nội bộ.
K01–K08, Structured Raw v0.1, gateway nội bộ, PubMed và PMC được giữ nguyên.

## Bắt đầu trên Windows

Chạy ở root repo trong môi trường đã cài `.[dev]`. Các lệnh dưới đây có thật.
Lệnh `create`, `approval-template` và report có `--output` không ghi đè file có sẵn.
Phiên triển khai đã tạo `data/vietnamese-medical-corpus/sources.json`; chỉ chạy
`create` nếu chưa có file. Không cần sửa code Python.

```powershell
python -m medical_data_crawler.curated_cli --help
python -m medical_data_crawler.curated_cli candidates
if (!(Test-Path data/vietnamese-medical-corpus/sources.json)) {
    python -m medical_data_crawler.curated_cli create
}
python -m medical_data_crawler.curated_cli validate
python -m medical_data_crawler.curated_cli check-files
python -m medical_data_crawler.curated_cli report
python scripts/demo_curated_import.py
```

Demo tạo dữ liệu **tổng hợp**, với `data_origin=synthetic`, dưới
`data/curated-synthetic-demo/<uuid>/`. Chạy hai lần cùng đầu vào để chứng minh
chỉ một original và hai event khác nhau. Demo không truy cập mạng, không cấp
quyền cho bất kỳ tài liệu công khai nào, không cộng vào corpus thật.

## Manifest tuyển chọn v0.1

Validator có thẩm quyền là `curated_manifest.validate_manifest()`. Envelope:
`{"curated_manifest_version":"0.1","documents":[...]}`. Tối đa 1.000 mục,
file JSON CLI tối đa 1 MiB UTF-8; từ chối khóa JSON trùng. Mỗi mục phải có đúng
các trường trong [manifest ứng viên](../config/vietnamese-medical-candidates.v0.1.json).
Khóa ngoài hợp đồng bị từ chối. Lỗi cấu trúc/metadata khiến validation manifest
thất bại trước import; lỗi file và quyền từng mục được cô lập trong batch.

| Trường | Cách dùng |
|---|---|
| `document_id` | Slug bền vững; không đổi ID khi chạy lại/cập nhật byte cùng tài liệu. |
| `title`, `publisher`, `original_publisher` | Tiêu đề có căn cứ; đơn vị xuất bản trang và đơn vị xuất bản gốc. `null` nếu không biết. |
| `source_url`, `download_url` | HTTPS nguồn chuẩn và endpoint tải đã xác minh nếu có. Không tự tải URL. |
| `language`, `published_on` | Ngôn ngữ có căn cứ; ngày `YYYY`, `YYYY-MM` hoặc `YYYY-MM-DD`; thiếu dùng `null`. |
| `format`, `category` | `pdf`/`html`/`htm`; taxonomy category hiện có trong catalog. |
| `scope`, `scope_evidence` | K01–K08 kèm căn cứ; `[]` và `null` khi chưa có căn cứ, xuất thành `unknown`. |
| `local_path` | File tuyệt đối hoặc tương đối với `--base-dir` (mặc định root đang chạy). Không tương đối theo vị trí manifest. |
| `expected_sha256` | SHA-256 hex thường; có thể chưa biết khi research, grant import luôn cần checksum thực tế. |
| `submitted_at` | Thời điểm bàn giao file có timezone; không lấy thời điểm research thay thế. |
| `data_origin` | `real` hoặc `synthetic`; người vận hành chịu trách nhiệm xác nhận. |
| `source_status`, `verified_at` | `candidate` hoặc `verified`; verified cần thời điểm và metadata nguồn. Đây là xác minh thư mục, chưa phải xác minh byte. |
| `access_status` | `public_read`, `download_link`, `unverified`, `restricted`; không cấp quyền xử lý. |
| `rights` | Quyền theo từng thao tác, căn cứ và trạng thái review. |
| `review_notes` | Mức kiểm tra nguồn, giới hạn, nguồn gốc bên thứ ba và phần phải xác minh tiếp. |

`rights.status` nhận `pending_review`, `reviewed`, `restricted`, `rejected`.
`license_uri`, `evidence_url`, `evidence_note` để `null` nếu không biết.
`allowed_operations` nhận từng quyền độc lập:

- `read`: đọc file để kiểm tra/trích xuất.
- `download`: quyền tải về; khác việc website có nút tải.
- `manual_acquisition`, `automated_acquisition`: phương thức được phép.
- `store`: lưu toàn bộ original, bao gồm tài sản nhúng, cùng kết quả xử lý nội bộ.
- `extract`: trích xuất và lưu văn bản.
- `reuse` và `rag`: cần cả hai cho đúng mục đích Medical RAG dự kiến.

`allowed_operations=[]` là chưa cấp quyền. Có quyền thì `status=reviewed` và
phải có URL hoặc mã hồ sơ bằng chứng. `license_uri` đơn lẻ không cấp quyền;
có thể không có giấy phép công khai nếu có văn bản cho phép riêng có căn cứ.
Review cần bao phủ ảnh, nội dung đăng lại/dịch, tài sản bên thứ ba và điều kiện
ghi công. Phần mềm không tự xác minh thẩm quyền hoặc diễn giải pháp lý của hồ sơ.

Tám nhóm K01–K08 không phải nhãn chẩn đoán tự suy luận. Importer không dịch,
viết lại văn bản, chunk, embedding, chatbot hoặc nhận định bệnh nhân.

## Quy trình từ ứng viên đến batch được duyệt

1. Review nguồn và quyền cho từng mục. Giữ pending nếu chưa đủ bằng chứng.
2. Khi được phép tiếp nhận thủ công, đặt file vào `data/vietnamese-medical-corpus/intake/`.
   Không sửa original; ghi URL, người xuất bản gốc và thời điểm bàn giao thật.
3. Tạo manifest nhỏ 3–5 mục bằng cách sao chép các mục đã review vào JSON riêng.
   Điền `local_path`, checksum, nguồn đã xác minh, quyền và căn cứ đúng thực tế.
4. Người vận hành có thẩm quyền tạo và duyệt hồ sơ riêng, chỉ định qua
   `--trusted-approvals`. Không để người bàn giao tự chọn hoặc sửa hồ sơ này.
5. Validate, dry-run, preview, review fidelity tiếng Việt, import và verify.

Ví dụ PowerShell tạo manifest con từ mục đã chọn, **không cấp quyền hoặc tải file**:

```powershell
$corpus = 'data/vietnamese-medical-corpus'
$sourceManifest = Get-Content "$corpus/sources.json" -Raw -Encoding UTF8 | ConvertFrom-Json
$selectedIds = @('vn-melanoma-targeted', 'vn-bcc-quyhoa', 'vn-seborrheic-keratosis')
$pilotManifest = [ordered]@{
    curated_manifest_version = '0.1'
    documents = @($sourceManifest.documents | Where-Object { $_.document_id -in $selectedIds })
}
$pilotManifest | ConvertTo-Json -Depth 12 | Set-Content "$corpus/pilot.json" -Encoding UTF8
code "$corpus/pilot.json"
```

`pilot.json` vẫn pending và chưa có file. Sau khi có quyền và file thật,
dùng `Get-FileHash` trên file đã bàn giao để lấy
hash rồi điền chữ thường vào JSON. Ví dụ với tên file đã chọn cho mục đầu:

```powershell
(Get-FileHash -Algorithm SHA256 -LiteralPath 'data/vietnamese-medical-corpus/intake/vn-melanoma-targeted.html').Hash.ToLowerInvariant()
```

Lệnh sau tạo grant **bị tắt, đã hết hạn,
không có thao tác được phép**. Chỉ chạy khi mọi mục pilot đã có checksum.

```powershell
python -m medical_data_crawler.curated_cli validate --manifest data/vietnamese-medical-corpus/pilot.json
python -m medical_data_crawler.curated_cli fingerprints --manifest data/vietnamese-medical-corpus/pilot.json
python -m medical_data_crawler.curated_cli approval-template --manifest data/vietnamese-medical-corpus/pilot.json --output data/operator/curated-approvals.json
```

Mỗi grant có `document_id`, `manifest_entry_sha256`, `expected_sha256`,
`allowed_operations`, `reviewer`, `evidence`, `expires_at`, `active`.
Người duyệt thay `UNASSIGNED`, `PENDING_REVIEW_NO_PERMISSION`, thời hạn và quyền
bằng thông tin có thật; chỉ bật `active` khi đã review. JSON không phải chứng
thực danh tính. Bảo vệ filesystem và hồ sơ operator như gateway nội bộ hiện có.
Sửa metadata/đường dẫn/quyền trong manifest sẽ đổi fingerprint, cần review grant
mới; không tự cập nhật grant sau khi manifest thay đổi.

Các lệnh dưới đây chạy khi đã có pilot và hồ sơ đã duyệt thật:

```powershell
$pilotArgs = @('--manifest', 'data/vietnamese-medical-corpus/pilot.json',
    '--trusted-approvals', 'data/operator/curated-approvals.json')
python -m medical_data_crawler.curated_cli import @pilotArgs --dry-run
python -m medical_data_crawler.curated_cli preview @pilotArgs
$runOutput = python -m medical_data_crawler.curated_cli import @pilotArgs
if ($LASTEXITCODE -ne 0) { throw 'Import có lỗi; xem JSON report trước khi sử dụng kết quả.' }
$run = $runOutput | ConvertFrom-Json
$reportPath = "data/vietnamese-medical-corpus/reports/$($run.run_id)/report.json"
python -m medical_data_crawler.curated_cli verify --report $reportPath
python -m medical_data_crawler.curated_cli inspect-text --report $reportPath --document-id vn-melanoma-targeted --trusted-approvals data/operator/curated-approvals.json
Get-Content "data/vietnamese-medical-corpus/reports/$($run.run_id)/report.md" -Encoding UTF8
# Import đã export Structured Raw và verify batch; lấy đường dẫn thực, không export thêm bản sao:
$exportPath = "data/vietnamese-medical-corpus/$($run.export_manifest)"
Get-Content $exportPath -Encoding UTF8
```

## Đầu ra và xác minh

Original dùng `originals/<sha256>`, không nhân bản khi byte trùng. File intake do
người vận hành giữ nguyên để đối chiếu; có một bản original trong ArtifactStore.
`document_id` v0.1 được suy bằng thuật toán hiện có từ
`("curated-public", document_id-trong-manifest)`. Report giữ ánh xạ hai ID.
Mỗi lần nhập có provenance event mới, kể cả trùng byte. Event có extension
`curated_public.version=0.1` liên kết hash manifest entry và grant, không có
nhãn `internal`. Publisher, local path và metadata bổ sung ở snapshot manifest
trong report, không thêm khóa vào Structured Raw v0.1.

```text
data/vietnamese-medical-corpus/
  sources.json / pilot.json        # metadata vận hành; không commit
  intake/                         # file do người vận hành cung cấp
  originals/<sha256>              # byte nguyên vẹn trong ArtifactStore
  provenance/<event_id>.json
  extracted/<run_id>/<id>.txt      # UTF-8, thứ tự block nguyên văn
  extracted/<run_id>/<id>.quality.json
  exports/<batch_id>/manifest.json
  exports/<batch_id>/records/<index>.json
  reports/<run_id>/report.json
  reports/<run_id>/report.md
```

Quality sidecar v0.1 giữ biên trang/block PDF, số trang, encoding HTML khi có,
cảnh báo, checksum text và quyền RAG lúc chạy. Hash sidecar gắn vào warning
`curated_quality_sha256:<hash>` trong record v0.1. Verifier đối chiếu original,
event, grant/manifest snapshots, record/schema, text và sidecar; không trích xuất
lại khi verify. `verify` xác minh lịch sử kỹ thuật; `inspect-text` còn kiểm tra
grant hiện hành do operator chỉ định. Không coi snapshot lịch sử là cấp phép
RAG còn hiệu lực. Downstream phải kiểm tra lại quyền, mục đích, thời hạn và ghi công.

Dry-run chỉ snapshot trong RAM, kiểm tra checksum/định dạng/quyền, không chạy
extractor và không tạo state. Preview cần quyền đọc/lưu/trích xuất, chỉ trả text
ra stdout, không lưu state và không tạo batch. `check-files` chỉ kiểm tra đường
dẫn/file hiện diện, chưa xác minh hash hoặc quyền. Không tự resolve symlink;
snapshot từ chối traversal, UNC, network drive, symlink/junction và reparse point.
File tối đa 32 MiB, có thể hạ bằng `--max-bytes`. Parser có giới hạn byte;
chưa có process sandbox/quota CPU cho tài liệu thù địch.

Chỉ đủ quyền đọc/lưu sẽ `stored_only`. PDF không có text layer hoặc có trang
không trích được text sẽ báo `OCR_REQUIRED`; không tự nhận đã OCR. Empty text,
Unicode đáng ngờ, `partial` và `failed` không đủ điều kiện RAG tự động. PDF giữ
`pdf_layout_unverified`; vẫn cần review fidelity/thứ tự/ảnh bằng người trước pilot.
RAG eligibility yêu cầu thêm quyền `reuse` + `rag`, chất lượng text đủ theo gate
kỹ thuật và nguồn thật. `reuse` trong record v0.1 giữ `unknown` vì quyền RAG
cụ thể không chứng minh quyền phân phối/tái sử dụng chung.

Mã thoát: `0` khi thao tác hoàn tất (kể cả stored-only), `1` khi batch có mục
bị chặn/trích xuất thất bại hoặc export lỗi, `2` khi cấu hình/đối số/I/O lỗi.
Nếu lỗi sau lưu original nhưng trước event/export, original có thể còn lại;
không xóa tự động. Cần đối soát orphan rồi chạy lại, dùng lại hash. Store/event,
sidecar/report và export chưa có giao dịch chung, chữ ký hoặc trust anchor độc lập;
verifier không chống được sửa đồng bộ toàn bộ bằng chứng trên filesystem tin cậy.

## Kiểm tra trước commit

```powershell
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
git diff --check
git diff --cached --check
```

Nếu pytest default gặp ACL thư mục temp trên Windows, chạy lại với thư mục mới:
`python -m pytest -q --basetemp=data/pytest-curated-final`.
Không commit original, text đã tải, report dữ liệu, cache, venv hoặc approval thật.
Chỉ commit code, fixture tổng hợp và metadata thư mục ứng viên đã kiểm tra.
