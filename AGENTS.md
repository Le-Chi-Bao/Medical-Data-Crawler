# Quy tắc làm việc

- Luôn đọc toàn bộ DEFINE_PROBLEM_v1.0.md trong workspace (root hoặc docs). Giữ nguyên nội dung và các yêu cầu đã khóa.
- Chỉ triển khai task trong phạm vi phiên được phê duyệt. Dừng để làm rõ khi task mâu thuẫn với đặc tả.
- Bảo toàn byte gốc và provenance. Không ghi đè hoặc xóa original. Chỉ điền metadata và nhãn có căn cứ.
- Không tự chạy bulk crawling. Dùng fixture cục bộ cho automated tests.
- Luôn chạy kiểm thử và lint phù hợp. Báo cáo trung thực kết quả và phần chưa xác minh.
- Kiểm tra staged diff. Không commit secrets, dữ liệu tải về, cache hoặc virtual environment.
- Có thể tự commit các task thuộc phạm vi session đã duyệt bằng Conventional Commits tiếng Anh. Không tự push hoặc merge.
