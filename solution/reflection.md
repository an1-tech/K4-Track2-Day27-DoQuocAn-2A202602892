# Reflection

## Những loại lỗi khó phát hiện nhất

Các lỗi lệch nhẹ trên nhiều chỉ số khó phát hiện bằng ngưỡng đơn lẻ.
Tôi bổ sung khoảng cách tổng hợp cho data_batch, chuẩn hóa rows và
mean_amount theo nửa độ rộng baseline, còn null và staleness theo
giới hạn tương ứng. Dùng trực tiếp z-score với ngưỡng ví dụ 1,30 gây
nhiều cảnh báo nhầm; phiên bản chuẩn hóa thống nhất giữ FPR bằng 0
trên practice và public. Các ngưỡng feature và embedding được chọn
theo tài liệu hướng dẫn, không theo nhãn private.

Với lineage, tôi kiểm tra dependency raw.orders và raw.customers của
job dbt:stg_orders theo quy tắc nghiệp vụ được tài liệu cung cấp,
đồng thời kiểm tra orphan output và runtime. Cách này tránh phải chờ
đủ lịch sử mới phát hiện dependency bị thiếu. Contract kiểm tra cả
violations, freshness baseline và SLA khai báo trong payload.

Phiên bản mới đạt 50 điểm practice, 46,90 điểm public và 32,41 điểm
private. Private có TPR 64,81%, FPR 0%, vẫn còn bỏ sót lỗi; report
không đủ chi tiết để quy kết cho từng nhóm. Private đã được chạy ở
phiên bản trước, nên kết quả mới là so sánh hồi cứu trên cùng stream,
không phải đánh giá trên holdout mới. Tôi chốt phiên bản bằng
practice/public trước lần chạy private so sánh và không chỉnh tiếp
theo phản hồi private.

## Đánh đổi giữa chi phí và khả năng phát hiện

Mỗi sự kiện chỉ gọi một công cụ phù hợp. Các phép so sánh dùng dữ liệu
trả về sẵn có; hệ số chuẩn hóa được lưu trong ctx.state. Practice dùng
180/220 credits, public dùng 240/220 credits và bị phạt khoảng 1,82
điểm. Private không bị phạt vượt ngân sách. Cải thiện điểm đến từ chất
lượng phát hiện, không phải giảm chi phí công cụ.

Nếu có dữ liệu kiểm chứng độc lập, tôi sẽ đánh giá lại ngưỡng đa chiều,
tương quan giữa chỉ số và sự thay đổi phân phối. Tôi cũng sẽ thử phân
bổ ngân sách theo thông tin sự kiện và lịch sử, đo cả lỗi bỏ sót lẫn
cảnh báo nhầm thay vì mặc định FPR bằng 0 luôn tối ưu. Tăng ngưỡng hay
bỏ lượt kiểm tra đều cần được kiểm chứng trước khi áp dụng.
