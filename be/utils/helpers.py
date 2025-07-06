import cv2
import os
from datetime import datetime

from config import VIDEO_CLIP_DURATION, VIDEO_OUTPUT_DIR, FPS


def draw_boxes(frame, boxes, names=None):
    if boxes is None:
        return frame
    for i in range(len(boxes.xyxy)):
        x1, y1, x2, y2 = map(int, boxes.xyxy[i])
        conf = float(boxes.conf[i])
        cls_id = int(boxes.cls[i])
        label = names[cls_id] if names else str(cls_id)
        label_text = f"{label} {conf:.2f}"

        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(frame, label_text, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 255, 0), 2)
    return frame



# Ghi lại video clip khi phát hiện
def record_clip(source, label, room_id=None):
    actual_source = 0 if str(source) == "0" else str(source)
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW) if str(source) == "0" else cv2.VideoCapture(str(source))

    if not cap.isOpened():
        print(f"[⚠️] Không thể mở nguồn video: {actual_source}")
        return None

    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    hour_str = now.strftime("%H")

    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Thư mục lưu theo room (nếu có)
    folder = os.path.join(VIDEO_OUTPUT_DIR, room_id if room_id else "unknown", date_str, hour_str)
    os.makedirs(folder, exist_ok=True)

    filename = f"{label}_{now.strftime('%M%S')}.mp4"
    filepath = os.path.join(folder, filename)

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


