# object_detection.py

import cv2
from ultralytics import YOLO
import argparse
from utils.logger import log_event

# Load YOLOv8 model
model = YOLO("yolov8n.pt")


def detect(source, save_frame=False):
    cap = cv2.VideoCapture(source)

    if not cap.isOpened():
        print(f"❌ Không mở được nguồn video: {source}")
        return

    frame_count = 0
    frame_skip = 4  # ← xử lý mỗi 4 khung hình (bỏ qua 3 khung)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        if frame_count % frame_skip != 0:
            continue  # Bỏ qua khung hình này

        results = model(frame)

        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls)
                label = model.names[cls_id]
                conf = float(box.conf)

                if label == "person" and conf > 0.5:
                    log_event(label, conf, frame, save_img=save_frame)

        annotated = results[0].plot()
        cv2.imshow("YOLOv8 Surveillance", annotated)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YOLOv8 Video Surveillance")
    parser.add_argument("--source", required=True, help="Video path or IP camera URL")
    parser.add_argument(
        "--save-frame", action="store_true", help="Lưu khung hình khi phát hiện người"
    )
    args = parser.parse_args()

    detect(args.source, save_frame=args.save_frame)
