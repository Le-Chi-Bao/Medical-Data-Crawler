# Báo cáo M0/M1 — 26/11/2026

Baseline: a1d65500dd1043a2f83354a494dba855cabdfdc4.
Trạng thái: IMPLEMENTED / OFFLINE TESTED / READY FOR LIVE PILOT khi có approval.
Chưa LIVE VERIFIED. AC-15 chờ pilot, không đánh dấu đạt bằng fixture.

Đã bổ sung capability registry cho bảy provider, PMC OAI GetRecord độc lập PubMed,
gate quyền từng thao tác, inspection XML có quota, lưu byte response + SHA-256,
provenance/catalog, JATS extractor, projection Structured Raw v0.1, text, báo cáo,
verifier và CLI có phê duyệt một lần. Không thay schema cũ hoặc đặc tả đã khóa.
PubMed metadata tiếp tục hoạt động trong regression; lỗi live redirect_denied
chưa giải quyết, đã ghi backlog. Các nguồn ngoài PubMed/PMC chưa có connector.

## Số liệu của phiên

| Loại | Tài liệu thật mới | Demo tổng hợp |
| --- | --- | --- |
| Metadata only | 0 | 0 |
| Original XML duy nhất | 0 | 1 |
| Tài liệu có extracted text | 0 | 1 |

Demo chạy hai lần tại data/pmc-m1-demo: 2 event/report/record/text files, 1 document,
1 rendition và 1 original. Lần hai duplicates=1, verifier kiểm tra 2 tham chiếu
original, integrity=verified, network_requests=0. Không cộng hai lần chạy thành
hai tài liệu khác nhau. Không kiểm kê lại corpus lịch sử của người dùng.

## Validation

- Baseline mặc định lỗi temp Windows ACL; chạy lại với basetemp riêng dưới data:
  795 passed, 2 skipped, 1 failed. Failure là test PubMed dùng thời gian cố định
  cho approval nhưng reader dùng ngày máy thật; đã cố định clock riêng trong test,
  không đổi logic production hoặc làm yếu expiry.
- Full suite sau sửa: python -m pytest -q --basetemp=data/pytest-m1-final2:
  **846 passed, 2 skipped**. Hai skip legacy do thiếu quyền tạo symlink Windows.
- python -m ruff check src tests scripts: PASS.
- python -m ruff format --check src tests scripts: PASS, 91 files.
- python -m ruff check .: FAIL, 3171 lỗi chỉ trong hai cây local:
  docs/data/catalog-ci-88832710-0827-4aaa-96d9-0590fd818ea9 và
  docs/data/catalog-ci-b23b0e67-7cef-4ea4-919e-366a8c8eed36.
- python -m ruff format --check .: FAIL, 249 file cần format trong các cây
  dependency/vendor local trên; 214 file đã đúng format. Không sửa/ẩn các file đó.
- git diff --check: PASS. Automated tests không dùng dịch vụ ngoài.

M1 có 50 test mới về end-to-end, grant riêng, expiry/revoke, license/third-party,
PMCID, profile XML, entity/DTD/XInclude, depth/size, malformed/partial, ordering,
hash/provenance/catalog, duplicate, tamper, offline CLI, endpoint, DNS unsafe,
TLS/timeout và redirect/throttle. TLS pinning, peer mismatch/rebinding, process
lease và quota chung tiếp tục được kiểm thử bởi suite transport hiện có.
Chưa thử handshake, schema response thực hoặc chất lượng trích xuất trên bài thật.

## Quyền và giới hạn còn lại

Lưu evidence từng bài trước công bố original. Extract cần grant và review riêng.
Không cấp quyền AI/phân phối/reuse rộng; xem PMC_FULLTEXT_ACQUISITION.md.
Chỉ hỗ trợ UTF-8 JATS không namespace, identity encoding, 4 MiB, GetRecord và 1–3
PMCID đã review; chưa discovery tìm kiếm hoặc resumption tokens. Không cam kết
trích xuất hình/công thức và bảng phức tạp. Catalog/FS chưa có transaction chung;
orphan sau crash cần đối soát. Đối sánh DOI/PMID liên nguồn để M5.

Các thay đổi cục bộ từ trước (đặc tả chuyển root sang docs, .vscode, audit và
docs/data) được giữ nguyên, không đưa vào commit phiên này. Dữ liệu/approval/cache
không commit, không push/merge. Xem git log để lấy hash commit của phiên.

Bước kế tiếp: operator review 1–3 PMCID và duyệt bounded pilot theo quickstart,
đánh giá byte/quyền/fidelity trên tài liệu thật; sau đó mở phiên M2 MedlinePlus.
