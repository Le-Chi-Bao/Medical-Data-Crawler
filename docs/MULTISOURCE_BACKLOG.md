# Backlog nguồn độc lập

- PubMed live metadata tại baseline a1d6550 gặp redirect_denied. Giữ nguyên chính
  sách chặn redirect và implementation PubMed; chưa thử lại trong M0/M1.
  Cần pilot metadata mới được duyệt để xác định response/redirect chính thức,
  không nới allowlist hoặc chuyển hướng sang scraping.
- PMC chưa live verified; chờ operator chọn 1–3 PMCID liên quan da, review quyền,
  cấp hồ sơ pilot, xác nhận mạng/egress và thực thi có phê duyệt.
- Theo dõi profile JATS namespace, XML quá 4 MiB, license thiếu URI, fidelity bảng,
  quản lý orphan sau crash và identity DOI/PMID liên nguồn trước mở rộng.
