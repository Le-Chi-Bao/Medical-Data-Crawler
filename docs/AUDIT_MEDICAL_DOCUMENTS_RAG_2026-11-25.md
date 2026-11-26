# Audit Medical Documents Output for Future RAG Integration

Repository: `Le-Chi-Bao/Medical-Data-Crawler`

Ngày audit: **25/11/2026**

Checkout đã audit: `1bcfb69ef8dc6991e206c5874b02779b6297204f`

Bản xuất Markdown của báo cáo trong hội thoại. Các kết quả kiểm thử và xác minh dưới đây là kết quả của lần audit đã báo cáo, không phải một lần crawl hoặc audit mới. Liên kết được đổi sang đường dẫn tương đối để đọc trong repository. Các đường dẫn `data/` trong nội dung ghi nhận vị trí tại thời điểm audit. Khi xuất báo cáo, output local đã nằm dưới `docs/data/`; các liên kết tới output và lệnh verify bên dưới được điều chỉnh theo vị trí hiện có. Không có dữ liệu nào được di chuyển bởi thao tác xuất báo cáo. Các output local không mặc định có trong một checkout khác.

## A. Current Crawler Status

**Crawler đã có pipeline Structured Raw và cơ chế xác minh bàn giao, nhưng chưa có bằng chứng về corpus y khoa thật đủ điều kiện đưa vào RAG trong workspace này.** Output kiểm tra được là dữ liệu **SYNTHETIC**. PubMed hiện cung cấp metadata, không cung cấp abstract hoặc toàn văn.

Audit ngày **25/11/2026**, tại checkout `1bcfb69ef8dc6991e206c5874b02779b6297204f`. Tôi đã đọc toàn bộ [DEFINE_PROBLEM_v1.0.md](DEFINE_PROBLEM_v1.0.md).

| Thành phần | Trạng thái được đối chiếu |
|---|---|
| Lưu original bất biến theo SHA-256, phát hiện trùng byte | Đã triển khai |
| Acquisition file local; gateway tiếp nhận nội bộ; HTTP có gate | Đã triển khai |
| Extraction HTML và PDF có text layer | Đã triển khai |
| Record Structured Raw v0.1, export manifest v0.1, verifier | Đã triển khai |
| Catalog SQLite: document, revision, rendition, identifier, observation, relation | Đã triển khai, tùy chọn |
| Discovery PubMed ESearch/ESummary | Đã triển khai; metadata-only |
| PubMed abstract/full text, JATS | **NOT SUPPORTED** trong connector hiện tại |
| OCR, chunking, embedding, vector index, RAG | **NOT SUPPORTED** |
| Fidelity trên corpus y khoa thật | **NOT VERIFIED** |

Bằng chứng: [pipeline.py](../src/medical_data_crawler/pipeline.py), [export.py](../src/medical_data_crawler/export.py), [Catalog implementation](CATALOG_IMPLEMENTATION.md), [PubMed live pilot](PUBMED_LIVE_PILOT.md).

**Xác minh đã chạy:**

- Tests offline: **755 passed, 2 skipped**.
- Ruff lint: **PASS**.
- Ruff format: **103 files already formatted**.
- Hai batch hiện có được chọn để kiểm tra: **`verify_batch()` PASS**.
- Staged diff rỗng.

Trong lần audit: không sửa code, không chạy demo sinh batch mới, không crawl, không commit/push. Thay đổi có sẵn trong working tree — xóa file đặc tả ở root và thêm file tại `docs/` — được giữ nguyên. File báo cáo Markdown này được tạo sau audit theo yêu cầu xuất file riêng của người dùng.

## B. Actual Medical Documents Structure

Hợp đồng có hiệu lực kỹ thuật nằm trong [DATA_CONTRACT.md](DATA_CONTRACT.md) và [structured-raw-0.1.json](../src/medical_data_crawler/schemas/structured-raw-0.1.json). Tài liệu contract còn gọi đây là đề xuất review liên repo, nhưng **validator và producer đã sử dụng schema này trong code**.

| Trường | Cấu trúc và hành vi thực tế |
|---|---|
| `schema_version` | Bắt buộc bằng `"0.1"` |
| `document_id` | Schema record chấp nhận chuỗi không trắng; pipeline/export thực tế dùng `doc:<64 hex>` |
| `source` | `source_id`, `locator`, `acquired_at` có múi giờ, `context` |
| `original` | `reference`, `media_type`, `byte_length > 0`, SHA-256 chữ thường |
| `content` | Mảng block; thứ tự mảng là thứ tự nội dung |
| Mỗi block | Chỉ có `kind`, `level`, `text` |
| `metadata` | Luôn có `title`, `language`, `authors`, `published_on`; thiếu căn cứ dùng `null` |
| `scope` | `"unknown"` hoặc mảng nhãn K01–K08; mảng rỗng biểu thị đã xác định không có nhãn phù hợp |
| `audience` | `general`, `medical`, `mixed`, `unknown` |
| Căn cứ nhãn | `scope_evidence`, `audience_evidence`; nhãn xác định phải có căn cứ |
| `extraction` | `status`, `method`, `version`, `configuration.profile`, `warnings`, `errors` |
| `rights` | `access_basis`, `reuse`, `evidence` |

Các loại block được phép:

```json
["heading", "paragraph", "list_item", "table", "text"]
```

HTML dùng `level` cho cấp heading và độ sâu list. Bảng được lưu **trong một chuỗi text**, không có model hàng/ô riêng. PDF hiện xuất các block `paragraph`, không phục hồi heading/list/table thành những loại tương ứng.

Quy tắc trạng thái:

| `extraction.status` | Yêu cầu |
|---|---|
| `success` | Có ít nhất một block; `errors` rỗng |
| `partial` | Có block dùng được; có warning |
| `failed` | `content: []`; có error |

Pipeline hiện tự đặt `scope` và `audience` là `"unknown"`; schema hỗ trợ nhãn có căn cứ nhưng **chưa có bộ phân loại tự động trong pipeline này**.

`original.reference` trong output hiện là khóa SHA-256 của ArtifactStore, không phải URL tải file. `source.context` được producer điền dạng `provenance_event:<event_id>`. Original và provenance nằm ngoài thư mục batch.

**NOT SUPPORTED trong record v0.1:** block ID, section ID, số trang PDF, bounding box, HTML selector, character offset, DOI/PMID chuyên biệt, và trường phân loại `full-text`/`abstract-only`/`metadata-only`. Schema từ chối thuộc tính ngoài danh sách.

## C. Real/Synthetic JSON Examples

**Cả năm ví dụ dưới đây đều là SYNTHETIC, không phải kiến thức y khoa để indexing production.** Các đoạn JSON là trích chọn field thực tế, không phải record đầy đủ để đưa trực tiếp vào validator.

### 1. SYNTHETIC HTML — heading, danh sách lồng nhau và bảng

Nguồn: fixture do dự án tạo, `fixture:synthetic.html`.

- Original dễ đọc: [tests/fixtures/synthetic.html](../tests/fixtures/synthetic.html).
- Record đã xuất: [records/0.json](data/offline-export-demo/exports/e76006d95a07433babc504563464f6ff/records/0.json).

```json
{
  "schema_version": "0.1",
  "document_id": "doc:05fdedc9b65bd244dc473447b737fad901d0d30a13acdf76cbc8712f998b00c8",
  "source": {
    "source_id": "synthetic-demo",
    "locator": "fixture:synthetic.html",
    "acquired_at": "2026-11-22T18:04:27.030370+00:00",
    "context": "provenance_event:d2941ecd269b4b38851879ea2258bdc9"
  },
  "original": {
    "reference": "22f636bc45f4e312b1eb8d5ef104c9cc86c0a5b831920b32a5203dbc78718f97",
    "media_type": "text/html",
    "byte_length": 936,
    "sha256": "22f636bc45f4e312b1eb8d5ef104c9cc86c0a5b831920b32a5203dbc78718f97"
  },
  "content": [
    {"kind": "heading", "level": 1, "text": "Tổn thương da — văn bản tổng hợp"},
    {"kind": "paragraph", "level": null, "text": "Đây là dữ liệu kiểm thử & không phải tài liệu y khoa."},
    {"kind": "heading", "level": 2, "text": "Danh sách"},
    {"kind": "list_item", "level": 1, "text": "Mục một"},
    {"kind": "list_item", "level": 2, "text": "Mục lồng nhau"},
    {"kind": "list_item", "level": 1, "text": "Phần sau mục con"},
    {"kind": "list_item", "level": 1, "text": "Mục hai"},
    {"kind": "table", "level": null, "text": "Bảng tổng hợp\nCột A\tCột B\nGiá trị 1\tGiá trị 2"},
    {"kind": "paragraph", "level": null, "text": "Kết thúc."}
  ],
  "metadata": {
    "title": "Tài liệu tổng hợp cho kiểm thử",
    "language": "vi",
    "authors": ["Synthetic Fixture Author"],
    "published_on": "2026-01"
  },
  "rights": {
    "access_basis": "Self-authored synthetic fixtures",
    "reuse": "unknown",
    "evidence": null
  }
}
```

`content` trên thể hiện toàn bộ text đã trích xuất theo thứ tự. Trạng thái `success`, warning `html_table_text_only`; `scope`/`audience` đều `unknown`.

Phân loại: **nội dung tổng hợp có text body**, không phải tài liệu y khoa full-text.

### 2. SYNTHETIC PDF — text layer trích xuất thành công

Nguồn giả lập: `https://publisher.example/sample.pdf`. Transport của demo trả bytes trong bộ nhớ, không tải từ publisher thật.

Record: [HTTP demo records/1.json](data/http-acquisition-demo/exports/7cb7804ecfb148e1a6d8cffeb75f218a/records/1.json).

```json
{
  "document_id": "doc:27a2236d98fdee672ed1bcd5052263d713ffca75a673a4a764839cedc418bbf2",
  "original": {
    "reference": "387841e1f7ca7c97abc1275dbf1aaed058bb61c494ea97765de094bacc119fcb",
    "media_type": "application/pdf",
    "byte_length": 641,
    "sha256": "387841e1f7ca7c97abc1275dbf1aaed058bb61c494ea97765de094bacc119fcb"
  },
  "content": [
    {"kind": "paragraph", "level": null, "text": "Synthetic PDF fixture."}
  ],
  "extraction": {
    "status": "success",
    "method": "pypdf/plain",
    "version": "1.1/pypdf-7.0.0",
    "configuration": {"profile": "pdf-plain-v2"},
    "warnings": [
      "pdf_layout_unverified",
      "v0.1_page_boundaries_internal_only"
    ],
    "errors": []
  }
}
```

Text sau extraction:

```text
Synthetic PDF fixture.
```

Bốn trường metadata đều `null`. Quyền: `access_basis = "Self-authored synthetic HTTP fixtures"`, `reuse = "unknown"`, `evidence = null`.

Đọc lại original bằng extractor hiện tại xác nhận một trang, block range `[0,1)`. **Thông tin trang này không có trong JSON export.**

Phân loại: **PDF tổng hợp có text body**, không phải PDF y khoa thật. Bằng chứng nguồn tổng hợp: [demo_http_acquisition.py](../scripts/demo_http_acquisition.py).

### 3. SYNTHETIC HTML — extraction một phần

Nguồn: `fixture:partial.html`.

Record: [records/1.json](data/offline-export-demo/exports/e76006d95a07433babc504563464f6ff/records/1.json).

```json
{
  "source": {
    "source_id": "synthetic-demo",
    "locator": "fixture:partial.html",
    "acquired_at": "2026-11-22T18:04:27.110822+00:00",
    "context": "provenance_event:c0c7c3f4587b4813a58c7299d6b215f7"
  },
  "content": [
    {"kind": "paragraph", "level": null, "text": "Mẫu tổng hợp"}
  ],
  "extraction": {
    "status": "partial",
    "method": "beautifulsoup4/html.parser",
    "version": "1.0/beautifulsoup4-4.13.3/html.parser",
    "configuration": {"profile": "html-dom-v1"},
    "warnings": ["html_nontext_content_omitted"],
    "errors": []
  }
}
```

Text sau extraction: **`Mẫu tổng hợp`**.

Original có `<img>`; phần nontext bị bỏ nên trạng thái `partial`. Metadata đều `null`; quyền tự khai là fixture tổng hợp, `reuse: unknown`, không có evidence. Phân loại: **nội dung tổng hợp trích xuất một phần**, không phải abstract.

### 4. SYNTHETIC PDF — không có text trích xuất được

Nguồn: `fixture:blank.pdf`.

Record: [records/2.json](data/offline-export-demo/exports/e76006d95a07433babc504563464f6ff/records/2.json).

```json
{
  "content": [],
  "extraction": {
    "status": "failed",
    "method": "pypdf/plain",
    "version": "1.1/pypdf-7.0.0",
    "configuration": {"profile": "pdf-plain-v2"},
    "warnings": [
      "pdf_layout_unverified",
      "pdf_page_1_no_text",
      "v0.1_page_boundaries_internal_only"
    ],
    "errors": ["no_extractable_text"]
  }
}
```

Text sau extraction: **không có**. Original PDF 431 bytes vẫn có hash và provenance hợp lệ. Metadata đều `null`, `reuse: unknown`.

Phân loại: **extraction thất bại trên PDF tổng hợp**; không coi là metadata-only publication hay tài liệu đã xử lý thành công.

### 5. SYNTHETIC PubMed — metadata-only

Nguồn dữ liệu giả lập ESearch/ESummary. Output thực tế nằm tại:

[data/pubmed-discovery-demo/catalog.sqlite3](data/pubmed-discovery-demo/catalog.sqlite3).

Đây là projection để đọc từ các hàng SQLite đã kiểm tra; `observation.value` được giải mã khỏi chuỗi JSON:

```json
{
  "source_item": {
    "domain_id": "pubmed-fixtures",
    "source_id": "pubmed",
    "native_key": "990000002",
    "document_id": "document-d9cce9008f61a47d2a3315b300a0805ff529632f376228ba363166e6af900bab",
    "locator": "https://pubmed.ncbi.nlm.nih.gov/990000002/"
  },
  "observation": {
    "field": "title",
    "value": "Retraction notice for an invented skin study",
    "verification": "reported",
    "observed_at": "2026-11-24T08:00:00+00:00",
    "connector_version": "pubmed-esummary-2.0-v1"
  }
}
```

Observation còn lưu evidence chứa PMID, fingerprint snapshot/permit, mapping version và field path.

**Text sau extraction: không có bước extraction bài báo.** Database demo có metadata như title, authors, journal, identifiers và publication type; **không có abstract hoặc full text**. Permit chỉ thuộc miền fixture, không xác nhận quyền AI của bài báo thật. PMID và URL trên là dữ liệu tổng hợp, không dùng làm citation y khoa.

Bằng chứng: [report.json](data/pubmed-discovery-demo/report.json), [pubmed.py](../src/medical_data_crawler/pubmed.py).

## D. Data Quality and Completeness

### Khả năng bảo toàn và truy vết

| Câu hỏi | Kết quả audit |
|---|---|
| Giữ thứ tự heading/paragraph/list/table? | **HTML: có theo DOM**, gồm cấp heading và độ sâu list. Không bảo đảm thứ tự hiển thị CSS/JS. PDF chỉ giữ thứ tự trang và text do pypdf trả về |
| Giữ cấu trúc list? | Giữ text và depth; không có parent ID hay thông tin loại/đánh số list đầy đủ. Mẫu nested list tách phần tiếp nối thành một block cùng level |
| Giữ cấu trúc table? | HTML lưu text với tab/newline; bảng phức tạp có warning mất cấu trúc. PDF table reconstruction: **NOT SUPPORTED** |
| Giữ số trang PDF? | Có `PageBoundary` nội bộ; **NOT SUPPORTED trong export v0.1** |
| Giữ tọa độ từng đoạn? | **NOT SUPPORTED**. Tọa độ fragment chỉ phục vụ heuristic layout, không xuất locator đoạn |
| Truy ngược chunk về original? | Có thể nếu Main System giữ record/hash/block range. Crawler chưa tạo chunk; citation đến trang/vùng chính xác **NOT SUPPORTED** |
| Ngôn ngữ chủ yếu? | Corpus thật: **NOT VERIFIED**. Fixture HTML là tiếng Việt; PDF mẫu là tiếng Anh nhưng metadata language `null` |
| Encoding lỗi? | Hai original mẫu đọc lại không có U+FFFD. Chưa đủ để kết luận chất lượng corpus thật |
| Đoạn ngắt sai? | PDF tách paragraph theo dòng trắng; độ đúng ngữ nghĩa **NOT VERIFIED** |
| OCR? | **NOT SUPPORTED** |

Bằng chứng: [html_extraction.py](../src/medical_data_crawler/html_extraction.py), [pdf_extraction.py](../src/medical_data_crawler/pdf_extraction.py), [extraction.py](../src/medical_data_crawler/extraction.py).

HTML không giữ nguyên mọi khoảng trắng: extractor chuẩn hóa whitespace và loại một số phần giao diện/nontext. **Bảo toàn byte áp dụng cho original**, không phải bản text extraction giống từng byte nguồn.

### Danh tính, trùng lặp và phiên bản

- ID pipeline được tính từ SHA-256 của biểu diễn JSON UTF-8 `[source_id, logical_key]`, có tiền tố `doc:`. Cùng hai giá trị này tạo cùng ID; không phụ thuộc extractor, timestamp hay nội dung file.
- Vì vậy ID ổn định **có điều kiện caller giữ khóa logic**. Thay URL không tự được nhận biết là cùng tài liệu.
- ArtifactStore dùng SHA-256 để tránh lưu lại original giống hệt trong cùng store. Document ID khác nhau vẫn có thể trỏ cùng original.
- Gần trùng hoặc cùng bài ở PDF/HTML khác bytes: **NOT SUPPORTED bằng checksum**.
- Catalog đã hỗ trợ revision, rendition, identifiers và quan hệ `supersedes` có căn cứ; đây là khả năng lưu model. Tự phát hiện/diễn giải mọi cập nhật nội dung: **NOT SUPPORTED**.
- PubMed giữ cùng document theo domain/PMID, thêm observations khi có evidence mới; không gộp bài chỉ vì trùng title hoặc DOI hint.

Bằng chứng: [provenance.py](../src/medical_data_crawler/provenance.py), [storage.py](../src/medical_data_crawler/storage.py), [catalog/discovery.py](../src/medical_data_crawler/catalog/discovery.py).

### Thống kê local

Các thư mục output được nhận diện gồm `offline-demo`, `offline-export-demo`, `http-acquisition-demo`, `internal-import-demo`, `catalog-demo`, `backfill-demo`, `pubmed-discovery-demo`, `secure-api-demo` và nhiều thư mục test. **Không cộng các batch lặp và database test thành số tài liệu y khoa thật.**

| Chỉ số corpus y khoa thật | Kết quả |
|---|---|
| Tổng tài liệu thực tế | **NOT VERIFIED** — chưa nhận diện được corpus thật |
| Full-text / abstract-only / metadata-only | **NOT VERIFIED** |
| PDF/HTML và ngôn ngữ | **NOT VERIFIED** |
| Success/partial/failed | **NOT VERIFIED** |
| Độ dài trung bình và phân bố | **NOT VERIFIED** |
| Bản ghi y khoa thật xác nhận đủ quyền RAG | **0 được xác nhận trong audit** |
| Tổng bản ghi thật chưa xác minh quyền | **NOT VERIFIED** |

Số liệu **SYNTHETIC**, đo trực tiếp trên hai batch đã xác minh:

| Chỉ số | Offline batch `e760…` | HTTP fixture batch `7cb7…` |
|---|---:|---:|
| Input | 5 | 2 |
| Record xuất | 3 | 2 |
| Omission failed / skipped | 1 / 1 | 0 / 0 |
| Extraction success / partial / failed | 1 / 1 / 1 | 2 / 0 / 0 |
| HTML / PDF trong record | 2 / 1 | 1 / 1 |
| Language metadata `vi` / `null` | 1 / 2 | 1 / 1 |
| Độ dài text từng record | 191, 12, 0 | 191, 22 |
| Trung bình; min–max | 67,67; 0–191 | 106,5; 22–191 |
| `reuse: unknown` | 3/3 | 2/2 |

Độ dài tính bằng tổng số ký tự `block.text`, không thêm separator. Trung bình offline bao gồm record failed có độ dài 0. Hai batch dùng chung original HTML nên **không cộng thành năm tài liệu độc lập**.

SQLite PubMed demo kiểm tra trực tiếp có **6 document, 52 observations, 0 revisions, 0 renditions**. Secure API demo có **2 document, 16 observations, 0 renditions**. Đây là metadata tổng hợp; không cộng hai database vì có thể dùng lại mẫu.

## E. Rights and RAG Eligibility

**Output v0.1 chưa tự chứa đủ thông tin để xác nhận quyền embedding, indexing và sử dụng với LLM.**

`rights.reuse = permitted` yêu cầu một chuỗi evidence, nhưng validator không xác minh nội dung pháp lý của evidence hoặc mục đích AI. Record không có các field riêng cho `ai_use`, phân phối, thời hạn, reviewer hay phạm vi nhà cung cấp LLM.

Ngược lại, registry/chính sách nguồn đã hỗ trợ quyền riêng theo tài sản và hành động:

- Tài sản: text HTML/PDF, original bytes, images, external media, third-party assets.
- Hành động: `read`, `internal_storage`, `reuse`, `distribute`, `ai_use`.
- `allows_asset_use(..., action="ai_use")` yêu cầu cả quyền `ai_use` và `reuse`, review còn hiệu lực và không còn pending AI decision.

Bằng chứng: [SOURCE_POLICY.md](SOURCE_POLICY.md), [source_policy.py](../src/medical_data_crawler/source_policy.py).

Registry thực tế có **18 nguồn, toàn bộ `needs_review`, không có nguồn approved**. README còn ghi 16, nên số README không phản ánh file registry hiện tại. Bằng chứng: [source_candidates.v0.1.json](../config/source_candidates.v0.1.json).

Trước khi dùng dữ liệu thật cho RAG cần căn cứ bao phủ:

1. Lưu text, tạo và lưu embedding/index.
2. Đưa text/context đến LLM, gồm provider hoặc môi trường triển khai cụ thể.
3. Hiển thị snippet, trích dẫn và phân phối original nếu cần.
4. Tài sản bên thứ ba, điều kiện giấy phép, attribution.
5. Thời hạn, thu hồi, retention và miền người dùng được phép.

Đây là các quyền cần reviewer có thẩm quyền xác minh; audit này không cấp quyền nguồn.

## F. Export Contract and Verification

### Cấu trúc export thực tế

Ví dụ batch HTTP fixture:

```text
data/http-acquisition-demo/
├── originals/
│   └── <original_sha256>
├── events/
│   └── <event_id>.json
└── exports/
    └── 7cb7804ecfb148e1a6d8cffeb75f218a/
        ├── manifest.json
        └── records/
            ├── 0.json
            └── 1.json
```

Batch không tự chứa originals/events. Root của hai store do cấu hình ngoài contract quyết định. Nội bộ import dùng tên thư mục provenance khác, nên consumer không nên hard-code `events/`.

Manifest thực tế: [manifest.json](data/http-acquisition-demo/exports/7cb7804ecfb148e1a6d8cffeb75f218a/manifest.json).

Đây là header và entry tương ứng PDF ở ví dụ 2; các entry khác được lược khỏi trích đoạn:

```json
{
  "manifest_version": "0.1",
  "structured_raw_version": "0.1",
  "batch_id": "7cb7804ecfb148e1a6d8cffeb75f218a",
  "created_at": "2026-11-24T12:30:46.432958+00:00",
  "records": [
    {
      "input_index": 1,
      "document_id": "doc:27a2236d98fdee672ed1bcd5052263d713ffca75a673a4a764839cedc418bbf2",
      "event_id": "2f516d3906d943f78f31a82dc949c523",
      "record_path": "records/1.json",
      "record_sha256": "c7e521a5cff901ae38ffe5b2d2be666f6cd6adc11eab6b95f0742b83fe9a125a",
      "record_byte_size": 1355,
      "original_reference": "387841e1f7ca7c97abc1275dbf1aaed058bb61c494ea97765de094bacc119fcb",
      "original_sha256": "387841e1f7ca7c97abc1275dbf1aaed058bb61c494ea97765de094bacc119fcb",
      "extraction_status": "success",
      "reuse": "unknown"
    }
  ]
}
```

Manifest đầy đủ có summary `total=2`, `exported=2`, extraction success=2 và omissions rỗng. Schema: [export-manifest-0.1.json](../src/medical_data_crawler/schemas/export-manifest-0.1.json).

**Record extraction failed vẫn có thể được export hợp lệ.** `summary.failed` là omission failed, còn `summary.extraction.failed` đếm record đã xuất nhưng extraction failed.

### API xác minh đã có

| API | Phạm vi |
|---|---|
| `validate_record(record)` | Schema record |
| `validate_manifest(manifest)` | Schema, tổng đếm, index đầu vào, record paths |
| `verify_batch(manifest_path, provenance)` | File record, hash/size, schema, manifest consistency, original và provenance |
| `ArtifactStore.verify(sha256)` | Tính lại hash original, kiểm tra không rỗng |
| `ArtifactStore.copy_to(sha256, stream)` | Đọc original có kiểm chứng |
| `catalog.verify()` | SQLite integrity và foreign keys |
| `link_verified_record(...)` | Liên kết catalog với record legacy đã đối chiếu |

Không thấy CLI chuyên dụng chỉ để verify batch. Có thể gọi API hiện tại bằng PowerShell mà không acquisition, chạy từ root repository:

```powershell
@'
from pathlib import Path
from medical_data_crawler.storage import ArtifactStore
from medical_data_crawler.provenance import ProvenanceStore
from medical_data_crawler.export import verify_batch

root = Path("docs/data/http-acquisition-demo")
assert (root / "originals").is_dir()
assert (root / "events").is_dir()

store = ArtifactStore(root / "originals")
provenance = ProvenanceStore(root / "events", store)
manifest = root / "exports/7cb7804ecfb148e1a6d8cffeb75f218a/manifest.json"

result = verify_batch(manifest, provenance)
print(result.valid, result.error_code, result.input_index)
'@ | .\.venv\Scripts\python -B -
```

Verifier đối chiếu:

- SHA-256 và kích thước **bytes JSON thực tế**, không phải JSON đã parse rồi serialize lại.
- Entry manifest với record.
- `source`, timestamp, document ID, event và original.
- Hash/size original.
- Record ngoài danh sách trong `records/`.
- Omissions có event theo phạm vi được mô tả trong contract.

**Giới hạn:** manifest/provenance chưa có chữ ký hoặc neo inventory tin cậy. Sửa đồng bộ các file, hoặc xóa entry cùng record rồi sửa summary, có thể vượt kiểm tra nhất quán. Omission không có event chỉ được kiểm tra cấu trúc/thống kê. Verifier không xác nhận quyền pháp lý, fidelity hay sự thật y khoa.

### Citation và phát hiện cập nhật

Có thể dùng cho citation: locator nguồn, title/authors/date khi có, `document_id`, original SHA-256, record SHA-256, batch/event ID và block index do consumer lưu. DOI/PMID trong catalog chỉ hỗ trợ định danh thư mục, không chứng minh đã đọc toàn văn.

So sánh các lần nhận:

- Cùng document ID, cùng original hash: cùng bytes nguồn.
- Cùng document ID, khác original hash: ứng viên cập nhật nội dung.
- Khác document ID, cùng original hash: trùng bytes ở nhiều danh tính.
- Cùng original hash, khác record hash: có thể do thời điểm/event/extractor thay đổi; không tự kết luận nguồn đổi.

Không có citation trang/vùng PDF chính xác trong v0.1.

## G. Known Limitations

1. Chưa có corpus thật/golden annotations để đo fidelity; [PILOT_EVALUATION.md](PILOT_EVALUATION.md) ghi **NOT MEASURED**.
2. `success` không chứng minh text đầy đủ, reading order đúng hoặc nội dung y khoa hợp lệ.
3. PDF mất semantic heading/list/table; trang chỉ giữ nội bộ, không có locator đoạn xuất ra.
4. HTML theo DOM, không render JS/CSS; bảng là text và có thể mất quan hệ ô.
5. Không có phân loại chuẩn full-text/abstract/metadata-only trong schema record.
6. Quyền AI chi tiết không được đóng gói đầy đủ trong record/manifest.
7. Original dedup không giải quyết gần trùng hoặc đồng nhất bài báo đa định dạng.
8. Catalog ID và legacy `document_id` là hai hệ định danh; cần mapping tường minh.
9. Connector PubMed không tải abstract/full text; connector khác và JATS vẫn thuộc công việc tương lai.
10. Schema có thể thay đổi. Chính sách yêu cầu tạo version mới và giữ validator cũ; không bảo đảm mọi output tương lai vẫn chỉ là v0.1.

## H. Recommendations for Main System RAG

**Đề xuất interface bàn giao**, chưa phải tính năng hiện có và không buộc Crawler triển khai RAG:

```text
Handoff
  manifest_path
  structured_raw_version
  artifact_store_binding
  provenance_store_binding
  access_domain
  rights_decision_snapshot_ref
  producer_commit
```

Main System nên:

1. Chỉ nhận batch đã công bố manifest; kiểm tra version và chạy verifier.
2. Đối chiếu quyền hiện hành từ snapshot/hồ sơ có thẩm quyền trước ingestion.
3. Loại record `failed`; review `partial`; kiểm tra chất lượng cả record `success`.
4. Tách metadata-only PubMed khỏi kho text evidence.
5. Tạo chunk trong Main System và giữ: `document_id`, original/record hash, batch/event ID, block range, character range của consumer, locator, metadata citation và quyền.
6. Theo dõi phiên bản nguồn bằng `(document_id, original_sha256)`; theo dõi rendition/extraction bằng thêm record hash và extractor profile.
7. Giữ schema v0.1 nguyên trạng; nếu cần page/section locator, thống nhất contract version mới hoặc sidecar có version và hash binding.

Dữ liệu SYNTHETIC hiện tại phù hợp để thử consumer, verifier và truy vết kỹ thuật. **Chưa phù hợp làm knowledge base y khoa.**

## I. Questions That Must Be Resolved Before Integration

1. Corpus thật đầu tiên ở đâu, ai duyệt nguồn và ai duyệt chất lượng?
2. Ai có thẩm quyền xác nhận quyền embedding/indexing/LLM, và bằng chứng được bàn giao thế nào?
3. Main System chỉ phục vụ nội bộ hay cung cấp snippet/original ra bên ngoài?
4. Citation cấp tài liệu có đủ, hay bắt buộc số trang/section/vùng?
5. Ngưỡng chấp nhận `partial`, bảng mất cấu trúc và PDF nhiều cột là gì?
6. Quy tắc khóa logic khi URL đổi, tài liệu đổi ấn bản hoặc có nhiều định dạng là gì?
7. Main System sẽ nhận diện full-text, abstract-only và metadata-only bằng contract nào?
8. Cần tiếng Việt, tiếng Anh hay cả hai; xử lý language `null` ra sao?
9. Khi tài liệu bị sửa, rút bài hoặc thu hồi quyền, ai cập nhật và loại dữ liệu khỏi index?
10. Hai repo sẽ pin schema, snapshot quyền, phiên bản extractor và mapping catalog như thế nào?
