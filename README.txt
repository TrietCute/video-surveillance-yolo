Chỉnh frame muốn skip trong file object-detection.py
Database MongoDB, vào file config để lấy link
Ảnh chụp lại lưu trong thư mục snapshots


Chạy video:
1. Cần có video trong thư mục test_videos
2. Lệnh chạy:
python object_detection.py --source "test_videos/video_test.mp4" --save-frame

Chạy ip web cam:
1. Cài đặt IP Webcam từ GG Play.
2. Vào video preferences, chỉnh camera lại (không dùng Camera2). Chỉnh video resolution và photo resolution. (Đề xuất 800x600).
3. Kéo xuống cuối, chọn Start Server. Sẽ thấy ip từ máy. (Đảm bảo máy tính và điện thoại kết nối cùng wifi)
4. Lệnh chạy:
python object-detection.py --source "http://<IP>:<port của ip web cam (mặc định 8080)>/video" --save-frame