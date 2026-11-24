# Medical Document Catalog · Session 06C.1

Catalog SQLite lưu metadata, định danh, phiên bản, quan hệ, tham chiếu quyền và provenance. Catalog là thành phần tùy chọn của pipeline hiện hành và giữ các hợp đồng Structured Raw v0.1, export manifest v0.1 và `document_id` hiện có. Phạm vi kiến thức MVP là K01–K08. Medical RAG dành cho bác sĩ là hệ thống tiêu thụ tương lai, độc lập với Computer Vision. [Kiến trúc đa nguồn](MULTISOURCE_ARCHITECTURE.md) · [Hợp đồng dữ liệu](DATA_CONTRACT.md)

## Khởi tạo và tính toàn vẹn SQLite

`Catalog(data_dir)` mở `catalog.sqlite3` trong thư mục trạng thái do người vận hành quản lý. Trong repo, đặt thư mục dưới `data/` để file database và journal nằm ngoài Git. Mỗi thread hoặc process giữ kết nối riêng. SQLite bật kiểm tra khóa ngoại trên từng kết nối, dùng `BEGIN IMMEDIATE` để tuần tự hóa writer, `synchronous=FULL` và chờ lock tối đa 5 giây. `CatalogError.code` báo lỗi cố định như `database_busy`, `invalid_reference` và `record_conflict`.

Khởi tạo schema trong giao dịch trên database trống bằng `PRAGMA user_version=1` và `application_id=0x4D444331`. Khi mở lại, catalog đối chiếu phiên bản, application ID và DDL của bảng cùng chỉ mục với schema đã đóng gói. `catalog.verify()` chạy `integrity_check` và `foreign_key_check`. Kết quả xác minh thể hiện toàn vẹn SQLite và khóa ngoại tại lúc kiểm tra. [Schema và bootstrap](../src/medical_data_crawler/catalog/_schema.py) · [Lưu trữ và truy vấn](../src/medical_data_crawler/catalog/store.py)

## Bảng và quan hệ

| Bảng | Vai trò và ràng buộc chính |
| --- | --- |
| `access_domain` | ID miền và `visibility` là `public` hoặc `internal`. |
| `source` | Provider, kênh và phiên bản connector tùy chọn. |
| `source_item` | Khóa gốc duy nhất `(domain_id, source_id, native_key)`, locator và tham chiếu quyền tùy chọn. Có thể chờ gắn với `document`. |
| `document` | ID catalog độc lập, category, kind, scope và audience, cùng căn cứ của các nhãn đã biết và tham chiếu quyền tùy chọn. |
| `revision` | Phiên bản của một tài liệu, duy nhất theo `(domain_id, document_id, version_key)`, có ngày phát hành/hiệu lực/hết hiệu lực, thời điểm quan sát, trạng thái, căn cứ tương ứng và tham chiếu quyền tùy chọn. |
| `identifier` | Namespace, giá trị gốc, khóa chuẩn hóa và issuer, chủ sở hữu và căn cứ. Khóa chuẩn hóa duy nhất trong miền. FK ghép bảo đảm revision tùy chọn thuộc đúng document. |
| `observation` | Quan sát của một source item, kèm trường, giá trị, chứng cứ, thời điểm, mức xác minh, giá trị chuẩn hóa và phiên bản connector nếu biết. |
| `rendition` | Biểu diễn của một revision thuộc document, với định dạng, vai trò, MIME khai báo/phát hiện, source item và tham chiếu quyền tùy chọn. SHA-256 và kích thước đi cùng nhau khi có artifact. |
| `document_relation` | Quan hệ có hướng và căn cứ, nối hai document hoặc revision tương ứng trong cùng miền. Chỉ mục duy nhất có điều kiện giới hạn mỗi chapter ở một quan hệ `chapter_of`. |
| `policy_reference` | Authority, mã hồ sơ, phiên bản chính sách và URI giấy phép tùy chọn. Những trường này lưu tham chiếu để đối soát với quyết định bên ngoài catalog. |
| `legacy_reference` | Liên kết đã kiểm chứng từ ID catalog và rendition đến `document_id` v0.1, locator, thời điểm, batch ID, event ID, record SHA-256 và original SHA-256. |

Các bảng theo miền dùng khóa chính `(domain_id, id)` và FK ghép có `domain_id`. Chỉ mục phục vụ lọc category, tìm source item, tra định danh, đọc lịch sử, tra quan hệ theo hai đầu và theo dõi tham chiếu legacy. Mọi truy vấn nhận dữ liệu người dùng qua tham số SQL. [Schema v1](../src/medical_data_crawler/catalog/_schema.py)

## Category, danh tính và lịch sử

Category nhận `medical_textbooks`, `clinical_guidelines`, `research_papers`, `systematic_reviews`, `medical_reference_websites`, `hospital_protocols`, `medical_reports` hoặc `unknown`. `kind` phân biệt document, book, chapter và notice. Scope giữ `unknown` hoặc danh sách nhãn K01–K08 không lặp, gồm danh sách rỗng khi có căn cứ rằng không có nhãn phù hợp. Audience nhận `general`, `medical`, `mixed`, `unknown`. Category, scope và audience có căn cứ độc lập.

Catalog dùng ID do caller chọn và lưu liên kết nguồn một cách tường minh. DOI được chuẩn hóa dạng chữ thường, PMID và PMCID có namespace riêng, ISBN hợp lệ chuẩn hóa về ISBN-13 và gắn với revision của book. Định danh guideline, protocol và report có issuer. Một định danh chuẩn hóa đã có chủ sở hữu trong cùng miền gây `identifier_conflict` khi dùng ID bản ghi khác. Nhiều nguồn báo cùng định danh được thể hiện qua các observation riêng. Trùng tiêu đề, locator hoặc SHA-256 vẫn có thể thuộc các document độc lập.

Các bản ghi coi như bất biến qua API. `write(*records)` kiểm tra tối đa 1.000 bản ghi rồi ghi theo thứ tự phụ thuộc trong một giao dịch. Replay cùng khóa và dữ liệu chuẩn hóa có thể chạy lại. Cùng khóa có dữ liệu khác báo `record_conflict` và rollback cả đợt. Ngoại lệ được kiểm soát là gắn lần đầu một source item chưa liên kết vào document. Replay dữ liệu discovery cũ với binding trống giữ liên kết đã ghi. Dữ kiện điều chỉnh được ghi thành observation hoặc revision có ID riêng để giữ lịch sử.

Một book có các revision theo ấn bản. `edition_of` nối ấn bản đến book. `chapter_of` gắn chapter vào một revision của book. Chương xuất hiện trong hai ấn bản có hai ID chapter để giữ đúng ngữ cảnh trích dẫn và quyền. `supersedes` nối hai revision khác nhau của cùng document và từ chối chu trình. Các loại khác gồm `translation_of`, `preprint_of`, `publication_of` và thông báo có loại `corrects`, `retracts`, `withdraws`, `expression_of_concern_for`. `publication_of` nối bản ghi công bố research paper với systematic review có căn cứ. Thông báo có ID riêng, có thể trỏ đến revision bị ảnh hưởng. Một revision có nhiều rendition, ví dụ PDF và JATS cùng mô tả bản phát hành.

## Metadata và ranh giới tin cậy

Observation lưu từng khẳng định theo nguồn, gồm giá trị thiếu (`None`), giá trị mâu thuẫn và các mức `unknown`, `reported`, `verified`. Bằng chứng đã lưu luôn gắn với source item cung cấp. Mốc quan sát cần timezone và được chuẩn hóa UTC. Các ngày phát hành/hiệu lực giữ độ chính xác `YYYY`, `YYYY-MM` hoặc `YYYY-MM-DD`. Model kiểm tra danh sách trường metadata cho phép, kiểu dữ liệu, kích thước UTF-8 và các chuỗi có ký tự điều khiển. JSON lưu trữ có dạng xác định để so sánh replay. [Model và validator](../src/medical_data_crawler/catalog/model.py)

Một handle domain chỉ đọc, ghi và tìm định danh trong miền đã chọn. `write` từ chối đối tượng mang miền khác. FK kiểm tra nguồn, phiên bản, biểu diễn, quan hệ và tham chiếu quyền trong miền. Source item mang locator `internal:` chỉ được ghi trong miền nội bộ. SHA-256 chỉ là metadata kiểm tra artifact. Quyền lưu và tái sử dụng phải đến từ quyết định có thẩm quyền theo từng tài sản và mục đích. `license_uri` và các mã hồ sơ mang giá trị tham chiếu.

Tiến trình mở database là tiến trình cục bộ tin cậy. Người có quyền mở file SQLite có thể truy cập dữ liệu của các miền trong file đó. Người vận hành kiểm soát thư mục dữ liệu, file database, journal và backup bằng quyền hệ điều hành, và lựa chọn miền dựa trên quyền đã được xác nhận bên ngoài catalog. Tiến trình, tài khoản và thư mục trạng thái riêng cần dùng khi yêu cầu tách vật lý. Xác thực, RBAC theo mục đích, thu hồi và chính sách xử lý PHI thuộc tích hợp vận hành sau. API dùng mã lỗi cố định để tránh lộ tiêu đề, locator, hash hoặc giá trị định danh trong thông báo lỗi.

## API Python

```python
from pathlib import Path

from medical_data_crawler.catalog import (
    AccessDomain,
    Catalog,
    Document,
    Observation,
    Source,
    SourceItem,
)

domain_id = "metadata-fixtures"
with Catalog(Path("data/catalog-example")) as catalog:
    catalog.create_domain(AccessDomain(domain_id, visibility="public"))
    scope = catalog.domain(domain_id)
    scope.write(
        Source(domain_id, "fictional-press", "Fallowglass Press", "publisher"),
        Document(domain_id, "catalog-record"),
        SourceItem(
            domain_id,
            "source-item",
            "fictional-press",
            "fictional-native-key",
            document_id="catalog-record",
        ),
        Observation(
            domain_id,
            "title-claim",
            "source-item",
            "title",
            "Invented Source Title",
            "fixture:claim:title",
            "2026-06-10T09:30:00Z",
        ),
    )
    assert scope.get(Document, "catalog-record").category == "unknown"
    assert len(scope.observations("catalog-record", field="title")) == 1
    page = scope.list(Document, category="unknown", limit=50)
    next_page = (
        scope.list(Document, category="unknown", limit=50, after=page[-1].id) if page else ()
    )
    catalog.verify()
```

`get()`, `find_identifier(namespace, value, issuer=...)` và `find_source_item(source_id, native_key)` trả `None` khi miền hiện tại thiếu mục tương ứng. `list()`, `revisions(document_id)`, `renditions(revision_id)`, `observations(document_id, field=...)`, `relations(document_id)` và `legacy_references(legacy_document_id)` nhận `limit` từ 1 đến 1.000, mặc định 100. Dùng `after` là ID cuối của trang trước. API sắp xếp theo ID và `relations()` trả các cạnh đi và đến. Chỉ `list(Document, ...)` nhận bộ lọc category. [API trong mã nguồn](../src/medical_data_crawler/catalog/store.py)

### Nối một mục Structured Raw v0.1 đã xác minh

```python
reference = scope.link_verified_record(
    manifest_path,
    provenance_store,
    input_index=0,
    source_item_id="reviewed-item",
    rendition_id="matching-html",
)
assert reference.rendition_id == "matching-html"
```

Mở đúng domain và tạo trước source item, document, revision và rendition đã có căn cứ. API nhận `manifest.json` đã công bố và `ProvenanceStore` cùng original store của batch. Nó gọi `verify_batch()`, chọn record theo index, đọc lại và đối chiếu hash record cùng event. Source item và rendition được chọn phải khớp locator, document, định dạng, kích thước và hash original. Miền nội bộ yêu cầu prefix nguồn nội bộ, locator `internal:` và trace intake trong event. Miền công khai yêu cầu locator có dạng HTTPS công khai và từ chối event có trace nội bộ hoặc nguồn có prefix nội bộ. Các kiểm tra này xác minh liên kết kỹ thuật. Quyền công bố cần căn cứ được duyệt riêng. Một legacy document ID có thể xuất hiện ở nhiều batch và chỉ gắn một document catalog trong cùng miền. Phép nối đọc các file gốc, event, record và manifest, rồi lưu một tham chiếu có thể replay. [Adapter v0.1](../src/medical_data_crawler/catalog/_legacy.py)

## Demo tổng hợp và kiểm thử

```powershell
python scripts/demo_catalog.py
python -m pytest -q tests/unit/test_catalog_model.py tests/contract/test_catalog_schema.py tests/integration/test_catalog_workflow.py tests/integration/test_catalog_legacy_link.py
```

Demo dùng một fixture metadata tự tạo, mở lại database tại `data/catalog-demo/catalog.sqlite3` và replay cùng đầu vào. Kết quả có **13 document trong 2 miền**, gồm 12 public fixture và 1 internal fixture, đủ bảy category và `unknown`, 7 revision, 7 identifier, 18 observation, 8 relation và 3 rendition. Cả năm nhóm kiểm tra đạt và `integrity` là `pass`. Metadata PDF/JATS/HTML chỉ mô tả các biểu diễn. Demo dùng dữ liệu cục bộ. [Script](../scripts/demo_catalog.py) · [Fixture](../tests/fixtures/catalog_metadata.json) · [Guard socket/DNS](../tests/conftest.py)

## Migration và giới hạn

Catalog có bootstrap v1 và từ chối các phiên bản ngoài phạm vi hỗ trợ. Khi có schema mới, dùng bản sao nhất quán lấy qua cơ chế backup SQLite hoặc khi writer đã đóng. Thực hiện migration tường minh theo phiên bản, giữ bản backup theo miền và xác minh toàn vẹn trước khi đưa database mới vào dùng. Luồng pipeline đọc và xuất theo các hợp đồng legacy hiện hành.

Session 06C.2 là bước tiếp theo để backfill song song từ nhiều mục v0.1 bằng dry-run và đối soát. Việc nối từng mục hiện có cung cấp primitive cho công cụ đó. Từng lần chạy backfill cần giữ ID, checksum, provenance, byte đã công bố và nhãn `unknown` khi thiếu căn cứ. Chọn domain trước khi lập ánh xạ và đưa trường hợp mất liên kết hoặc chưa rõ quyền vào hàng review. [Lộ trình 06C.2](MULTISOURCE_ROADMAP.md#06c2--backfill-song-song-từ-v01)

Phiên 06C.1 phục vụ một tiến trình local được tin cậy và tải ghi nhỏ. Các chức năng discovery, đọc full text mới, vòng đời quyết định quyền, bảng artifact vật lý, publication, chống sửa đổi cấp hệ thống, RBAC và RAG thuộc những phiên có phạm vi riêng. `catalog.verify()` kiểm tra database. Đối chiếu một file legacy ở lần sử dụng sau cần lại bằng chứng từ `verify_batch()` và quyền hiện hành.
