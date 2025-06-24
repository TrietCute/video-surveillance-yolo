Lệnh chạy: ./run.bat (chạy cả fe và be)
máy số 0 là dùng camera máy tính.

Chỉnh frame muốn skip trong file object-detection.py
Database MongoDB, vào file config để lấy link
Ảnh chụp lại lưu trong thư mục images

Chạy ip web cam:
1. Cài đặt IP Webcam từ GG Play.
2. Vào video preferences, chỉnh camera lại (không dùng Camera2). Chỉnh video resolution và photo resolution. (Đề xuất 800x600).
3. Kéo xuống cuối, chọn Start Server. Sẽ thấy ip từ máy. (Đảm bảo máy tính và điện thoại kết nối cùng wifi)
<<<<<<< HEAD:be/README.txt

Còn lỗi:
- Chưa chụp được ảnh.
- Màn hình frame còn ping cao, bị chậm.
- Chưa test thử nhiều camera.
=======
4. Lệnh chạy:
python object-detection.py --source "http://<IP>:<port của ip web cam (mặc định 8080)>/video" --save-frame

Dừng app: Ctrl + C trong terminal đang chạy.

Chưa có xử lý đa camera, chưa có phần xử lý bất thường, nhận diện khi dùng ip webcam còn bị chậm.

Có thể sửa lại cấu trúc Database (trường hợp có nhiều camera)
{
  "_id": ObjectId,
  "timestamp": ISODate("2025-06-19T22:45:00Z"),     // ngày giờ phát hiện
  "object": "person",                                // đối tượng phát hiện
  "confidence": 0.89,                                // độ tin cậy
  "frame_shape": [720, 1280, 3],                     // kích thước ảnh
  "camera_id": "CAM01",                              // ID camera (tuỳ chọn)
  "image_path": "snapshots/20250619_224500_person.jpg"  // nếu có lưu ảnh
}

Về xử lý sự kiện bất nhờ:
Cách 1: Định nghĩa thủ công
Ví dụ:
if label == "person":
    if in_restricted_area(bbox):  # kiểm tra vùng cấm
        log_event(..., type="intrusion")
🔹 Cách 2: Train mô hình “anomaly detection” riêng
Dùng mô hình học hành vi bình thường:
- Autoencoder
- RNN/LSTM
- CNN+Temporal Attention
→ Nếu đầu vào khác xa hành vi đã học → coi là bất thường.

Về lưu vào CSDL nếu có bất thường (tức là không lưu toàn bộ mà khi nào có bất thường mới lưu - chưa rõ ràng logic chỗ này)
a) Trong file logger:
def log_event(label, conf, frame, save_img=False, reason=None):
    if reason is None:
        return  # Không phải sự kiện cần lưu
    now = datetime.now()
    doc = {
        "timestamp": now,
        "object": label,
        "confidence": round(float(conf), 2),
        "frame_shape": list(frame.shape),
        "event_type": reason   # ← thêm lý do
    }
    ...
    collection.insert_one(doc)

b) Trong file object-detection:
if label == "person":
    if in_restricted_area(box.xyxy):  # nếu trong vùng cấm
        log_event(label, conf, frame, save_img=True, reason="intrusion")
>>>>>>> refs/remotes/origin/main:README.txt
