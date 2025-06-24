# object_detection.py

import cv2
from ultralytics import YOLO
from utils.logger import log_event, setup_logger
from utils.helpers import draw_boxes
import time

logger = setup_logger("detector")

# Load YOLOv8 model
model = YOLO("yolov8n.pt")

stop_flags = {}


def stop_detecting(source):
    stop_flags[str(source)] = True


def detect(source, save_frame=False, display=True):
    stop_flags[str(source)] = False

    # Phân biệt local webcam (OpenCV cần int 0)
    actual_source = 0 if str(source) == "0" else str(source)

    if str(source) == "0":
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    else:
        cap = cv2.VideoCapture(str(source))
        
    if not cap.isOpened():
        logger.error(f"❌ Không thể mở nguồn video: {actual_source}")
        return

    logger.info(f"📹 Đang xử lý nguồn: {actual_source}")
    frame_count = 0
    frame_skip = 2

    while True:
        if stop_flags.get(str(source), False):
            logger.info("⏹ Nhận tín hiệu dừng, kết thúc stream.")
            break

        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        if frame_count % frame_skip != 0:
            continue

        results = model(frame)

        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls)
                label = model.names[cls_id]
                conf = float(box.conf)

                if label == "person" and conf > 0.5:
                    log_event(label, conf, frame, save_img=save_frame, source=str(source))

        if results and len(results) > 0:
            annotated = results[0].plot()
            if display:
                cv2.imshow("YOLOv8 Surveillance", annotated)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

    cap.release()
    if display:
        cv2.destroyAllWindows()

