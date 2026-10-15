# Reflection

## Những loại lỗi khó phát hiện nhất

Khó khăn đầu tiên là phát hiện lỗi cấu trúc lineage. Phiên bản ban đầu
chỉ kiểm tra thời gian chạy, đạt 43,94 điểm practice và bỏ sót bốn lỗi:
hai missing_upstream và hai orphan_output.

Tôi bổ sung đối chiếu nguồn được khai báo, kiểm tra số downstream và
học các nguồn xuất hiện ổn định từ lịch sử của cùng job. Sau thay đổi,
practice đạt 50 điểm, bắt đủ 33 lỗi, không cảnh báo nhầm và vẫn dùng
180/220 credits.

Khó khăn tiếp theo là khả năng tổng quát hóa. Public đạt 43,84 điểm,
TPR 92,31% và FPR 1,65%; private đạt 27,78 điểm, TPR 55,56% và FPR 0%.
Kết quả cho thấy đạt tối đa trên practice chưa bảo đảm phát hiện tốt
các lỗi tinh vi ở luồng mới. Report private không cung cấp chi tiết
theo nhóm, nên tôi chưa xác định được chính xác loại lỗi bị bỏ sót.

## Đánh đổi giữa chi phí và khả năng phát hiện

Mỗi sự kiện chỉ gọi một công cụ kiểm tra phù hợp; các phép so sánh và
lịch sử được xử lý bằng ctx.baseline và ctx.state. Tuy vậy, public
vẫn dùng 240/220 credits và bị phạt vượt ngân sách. Private không bị
phạt chi phí.

Nếu có một lượt thiết kế và đánh giá mới, tôi sẽ thử kết hợp nhiều
tín hiệu lệch nhẹ thay vì chỉ dùng các ngưỡng riêng lẻ, rồi đánh giá
cả khả năng bắt lỗi và cảnh báo nhầm trên dữ liệu kiểm chứng phù hợp.
Tôi cũng sẽ cải thiện giai đoạn học ban đầu của lineage và cách thích
nghi khi topology thay đổi hợp lệ.

Với ngân sách chặt, tôi sẽ đánh giá chính sách phân bổ lượt kiểm tra
dựa trên thông tin sự kiện và lịch sử, đồng thời đo số lỗi bị bỏ sót
do tiết kiệm chi phí. Các cải tiến này là hướng đề xuất, chưa được
triển khai trong phiên bản đã tạo private_report.json.