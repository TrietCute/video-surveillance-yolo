import cv2
import os
from datetime import datetime

from config import VIDEO_CLIP_DURATION, VIDEO_OUTPUT_DIR, FRAME_WIDTH, FRAME_HEIGHT, FPS


# Vẽ khung phát hiện
def draw_boxes(frame, results):
    for box in results.boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        conf = float(box.conf[0])
        cls = int(box.cls[0])
        label = f"{results.names[cls]} {conf:.2f}"
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(
            frame,
            label,
            (x1, y1 - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )
    return frame


# Ghi lại video clip khi phát hiện
import cv2
import os
from datetime import datetime
from config import VIDEO_OUTPUT_DIR, FPS, VIDEO_CLIP_DURATION

def record_clip(source, label):
    # Chuyển source = 0 nếu là "0" để mở webcam
    actual_source = 0 if str(source) == "0" else str(source)
    if str(source) == "0":
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    else:
        cap = cv2.VideoCapture(str(source))
    
    if not cap.isOpened():
        print(f"[⚠️] Không thể mở nguồn video: {actual_source}")
        return None

    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    hour_str = now.strftime("%H")

    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Tạo thư mục theo ngày/giờ
    folder = os.path.join(VIDEO_OUTPUT_DIR, date_str, hour_str)
    os.makedirs(folder, exist_ok=True)

    # Tên file và đường dẫn
    filename = f"{label}_{now.strftime('%M%S')}.mp4"
    filepath = os.path.join(folder, filename)

    # Ghi video
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(filepath, fourcc, FPS, (frame_width, frame_height))

    frame_count = 0
    max_frames = int(FPS * VIDEO_CLIP_DURATION)

    while frame_count < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        out.write(frame)
        frame_count += 1

    cap.release()
    out.release()

    print(f"[🎞️] Clip đã ghi: {filepath}")
    return filepath

