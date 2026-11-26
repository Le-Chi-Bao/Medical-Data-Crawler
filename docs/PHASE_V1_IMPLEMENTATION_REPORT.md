# Báo cáo Phase V1 — 26/11/2026

Đã hoàn tất engineering ngoại tuyến và nghiên cứu thư mục. Corpus thật chưa
được tiếp nhận vì chưa có file cục bộ đủ quyền và hồ sơ phê duyệt tương ứng.
Không chạy bulk crawling, không tải original thật và không tự mở quyền RAG.

## Audit và phạm vi

Baseline thực tế: `0b32f9c8ca81ea35b7444e8ce798ee0d9e52365d`; working tree sạch
khi bắt đầu. Đã đọc AGENTS, toàn bộ DEFINE_PROBLEM v1.0, INTERNAL_IMPORT,
SOURCE_POLICY, DATA_CONTRACT, MULTISOURCE_ARCHITECTURE và báo cáo M0/M1; đối chiếu
extractor HTML/PDF, ArtifactStore, ProvenanceStore, exporter/verifier, catalog,
CLI và tests. Baseline kiểm thử: 846 passed, 2 skipped với basetemp cục bộ.

Giữ nguyên đặc tả khóa, K01–K08, Structured Raw v0.1, gateway nội bộ và các
connector PubMed/PMC. Dùng category của catalog hiện có; không tạo catalog mới
hoặc sửa schema catalog. Manifest/report sidecar giữ metadata tuyển chọn và
ánh xạ đến ID v0.1; chưa đồng bộ tự động intake này vào SQLite catalog.

## Đã triển khai

- `CuratedPublicDocumentImporter`: PDF/HTML/HTM cục bộ, snapshot có giới hạn,
  SHA-256, original bất biến và khử trùng qua ArtifactStore hiện có.
- Manifest, grant và report v0.1 độc lập. Tách tài liệu công khai khỏi nội bộ;
  provenance extension `curated_public` liên kết hash metadata và grant.
- Quyền đọc, tải, thủ công/tự động, lưu, extract, reuse, RAG riêng. Grant đáng
  tin cậy ràng buộc đúng entry manifest, checksum, reviewer, evidence và expiry.
  Không tự đổi pending thành reviewed; template grant luôn inactive/hết hạn.
- Dùng HTMLExtractor/PDFExtractor/OfflinePipeline, export_batch/verify_batch.
  Text UTF-8; giữ dấu tiếng Việt, heading, thứ tự block và biên trang khi có.
- Báo blank/suspicious Unicode, OCR_REQUIRED, partial/failed, trùng original và
  metadata thiếu. Quality sidecar có hash gắn vào record v0.1; verifier kiểm
  original/event/record/text/sidecar và quyền lịch sử. Inspect áp grant hiện hành.
- CLI: candidates, create, validate, check-files, fingerprints,
  approval-template, preview, import/dry-run, verify, inspect-text, report.
  Structured Raw được export và verify ngay trong import. Không có downloader.
- Demo tổng hợp và 49 test mới; toàn bộ automated tests bị chặn socket/DNS.

Commit engineering: `c75bc2410bd0b1575b9d516a98b728fa50b0c2ca`
(`feat(curated): add offline public document intake and rights verification`).
Metadata nghiên cứu, README và tài liệu bàn giao nằm ở commit riêng sau commit
trên; lấy hash bằng `git log -2 --oneline`. Không push hoặc merge.

## Corpus thật và dữ liệu tổng hợp

| Chỉ số | Kết quả |
|---|---:|
| Ứng viên tiếng Việt thật đã nhận diện | 15 |
| Mục mở được trang nguồn/metadata chính thức | 11 |
| Mục chỉ xác nhận qua chỉ mục; chờ xác minh live/byte | 4 |
| Ứng viên đủ bằng chứng quyền cho lưu + extract + RAG dự kiến | 0 |
| Pending rights review | 15 |
| Original thật mới đã import | 0 |
| Text tài liệu thật trích xuất thành công | 0 |
| OCR trên file thật | Chưa đánh giá; chưa có file |
| RAG eligible thật | 0 |

Không thấy bằng chứng đủ để mở các gate trong đợt research này; không kết luận
rằng các nguồn cấm mọi cách tái sử dụng. Nút download, đọc miễn phí và việc có
tài liệu trên trang cơ quan nhà nước không tự cấp quyền xử lý toàn văn/ảnh/AI.

Demo tại `data/curated-synthetic-demo/bf129379f2de4c1ebe1d8f5b25511bb2/` đã chạy
hai lần: 1 tài liệu tổng hợp, 1 original duy nhất, 2 event, 2 batch text/record,
duplicate ở lần hai, integrity verified, 0 yêu cầu mạng của importer. Không
cộng demo hoặc fixture test vào corpus thật. Chưa kiểm kê lại corpus lịch sử.

## Kiểm thử và xác minh

| Kiểm tra | Kết quả |
|---|---|
| `python -m pytest -q` | 424 passed, 472 errors do PermissionError tại temp Windows mặc định; không phải PASS |
| `python -m pytest -q -rs --basetemp=data/pytest-curated-release` | **895 passed, 2 skipped**, 48,58 giây |
| `python -m pytest -q tests/integration/test_curated.py --basetemp=data/pytest-curated-final-targeted` | **49 passed** |
| `python -m ruff check .` | **PASS** |
| `python -m ruff format --check .` | **PASS**, 96 file |
| Validate manifest 15 ứng viên / create / inventory report | **PASS**, không cấp quyền |
| Demo tổng hợp hai lượt, hash/text/provenance/batch verifier | **PASS**, không dùng mạng |
| Parse 6 code block PowerShell trong hướng dẫn | **PASS** về cú pháp; chưa chạy import với file thật |
| `git diff --check`, `git diff --cached --check` | **PASS**, đã review staged diff trước commit |

Hai skip là test symlink legacy: Windows thiếu quyền tạo symlink tại
`test_internal_import.py` và `test_html_preflight.py`. Không làm yếu permission
gate, bỏ qua test lỗi hoặc thay đổi thuật toán production để đạt kết quả.

49 test mới bao phủ Unicode HTML và PDF có ToUnicode CMap tự tạo, PDF text,
scan cần OCR, file thiếu/hỏng, hash sai, giới hạn byte, trùng tài liệu, manifest
sai, quyền/grant thiếu/hết hạn/bị tắt/sai binding, license không thay grant,
store-only, chặn downstream RAG, provenance, schema/export, tamper original,
text/record/event/page/quality/RAG flag, CLI và record text lớn hơn 1 MiB.

Log cục bộ: `data/curated-pytest-default.log`,
`data/curated-pytest-release.log`. Các log Ruff đầu tiên ghi lỗi style đã được
sửa trước kết quả PASS cuối; không dùng log đó làm bằng chứng code còn lỗi.

## Tệp bàn giao và lệnh Windows

- [Manifest ứng viên versioned](../config/vietnamese-medical-candidates.v0.1.json).
- [Bằng chứng từng nguồn và kế hoạch pilot](VIETNAMESE_CORPUS_CANDIDATES.md).
- [Hướng dẫn PowerShell đầy đủ](CURATED_PUBLIC_IMPORT.md), gồm grant/dry-run/
  preview/import/inspect/export/verify đúng interface đã triển khai.
- Manifest vận hành đã tạo: `data/vietnamese-medical-corpus/sources.json`.
- Inventory: `data/vietnamese-medical-corpus/reports/candidate-inventory.md`.
- Implementation: `src/medical_data_crawler/curated.py`, `curated_manifest.py`,
  `curated_cli.py`; tests: `tests/integration/test_curated.py`.

```powershell
python -m medical_data_crawler.curated_cli candidates
python -m medical_data_crawler.curated_cli validate
python -m medical_data_crawler.curated_cli check-files
python -m medical_data_crawler.curated_cli report
python scripts/demo_curated_import.py
python -m pytest -q --basetemp=data/pytest-curated-next
python -m ruff check .
python -m ruff format --check .
git log -2 --oneline
```

## Bước còn thiếu trước RAG

Review quyền cho pilot 3 mục ưu tiên trong báo cáo nghiên cứu; giải quyết tài
sản bên thứ ba, điều kiện ghi công và mục đích AI. Sau đó mới trình bản duyệt
acquisition một lần với URL/file/số lượng/thao tác/evidence/thư mục/giới hạn cụ
thể. Chưa có phê duyệt acquisition nên phiên này không tự tải tài liệu.

Khi có 3–5 file thật đã được phép và operator grant, chạy dry-run/preview,
người đọc tiếng Việt review fidelity, import/verify, xử lý OCR/partial nếu có,
rồi mở rộng các mục còn đủ quyền. RAG consumer vẫn cần kiểm tra quyền hiện
hành, citation và điều kiện dùng; repo không xây chunking/embeddings/RAG.

Các giới hạn: chưa đo fidelity trên corpus thật; OCR chưa triển khai; không có
giao dịch chung filesystem/catalog, chữ ký hoặc trust anchor chống sửa đồng
bộ; parser chưa có quota CPU/process sandbox. Không commit dữ liệu tải về,
approval thật, cache, venv hoặc secrets.
