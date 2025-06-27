# object_detection.py

import cv2
from ultralytics import YOLO
from utils.logger import log_event, setup_logger
from utils.helpers import draw_boxes
import time
import datetime
import os

from config import VIDEO_CLIP_DURATION, VIDEO_OUTPUT_DIR, FPS

logger = setup_logger("detector")

# Load YOLOv8 model
model = YOLO("yolov8n.pt")
stop_flags = {}

def stop_detecting(source):
    stop_flags[str(source)] = True

def initialize_video_capture(source):
    actual_source = 0 if str(source) == "0" else str(source)
    cap = cv2.VideoCapture(actual_source, cv2.CAP_DSHOW if str(source) == "0" else 0)
    if not cap.isOpened():
        logger.error(f"❌ Không thể mở nguồn video: {actual_source}")
        return None, actual_source
    logger.info(f"📹 Đang xử lý nguồn: {actual_source}")
    return cap, actual_source

def prepare_output_directory():
    now = datetime.datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    hour_str = now.strftime("%H")
    os.makedirs(os.path.join(VIDEO_OUTPUT_DIR, date_str, hour_str), exist_ok=True)
    return date_str, hour_str

def start_recording(cap, label, date_str, hour_str):
    now = datetime.datetime.now()
    filename = f"{label}_{now.strftime('%M%S')}.mp4"
    filepath = os.path.join(VIDEO_OUTPUT_DIR, date_str, hour_str, filename)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    frame_size = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    out = cv2.VideoWriter(filepath, fourcc, FPS, frame_size)
    logger.info(f"🎥 Bắt đầu ghi video: {filepath}")
    return out, filepath

def process_frame(frame, model):
    results = model(frame)
    annotated_frame = draw_boxes(frame.copy(), results[0]) if results else frame
    return results, annotated_frame

def handle_recording(recording, out, frame, record_start_time, max_duration):
    if recording and out is not None:
        out.write(frame)
        if time.time() - record_start_time >= max_duration:
            logger.info("🛑 Kết thúc ghi video.")
            recording = False
            out.release()
            out = None
    return recording, out

def cleanup(cap, out, display):
    if cap is not None and cap.isOpened():
        cap.release()
    if out is not None:
        out.release()
    if display:
        cv2.destroyAllWindows()

def detect(source, display=True):
    stop_flags[str(source)] = False
    cap, _ = initialize_video_capture(source)
    if cap is None:
        return

    out = None
    recording = False
    record_start_time = None

    date_str, hour_str = prepare_output_directory()

    try:
        while not stop_flags.get(str(source), False):
            ret, frame = cap.read()
            if not ret:
                break

            results, annotated_frame = process_frame(frame, model)

            if contains_person(results) and not recording:
                out, filepath = start_recording(cap, "person", date_str, hour_str)
                recording = True
                record_start_time = time.time()
                log_event("person", get_person_confidence(results), source=str(source), video_path=filepath)

            recording, out = handle_recording(recording, out, frame, record_start_time, VIDEO_CLIP_DURATION)

            if display:
                cv2.imshow("YOLOv8 Surveillance", annotated_frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

    finally:
        cleanup(cap, out, display)


def contains_person(results, threshold=0.5):
    for r in results:
        for box in r.boxes:
            cls_id = int(box.cls)
            label = model.names[cls_id]
            conf = float(box.conf)
            if label == "person" and conf > threshold:
                return True
    return False


def get_person_confidence(results, threshold=0.5):
    for r in results:
        for box in r.boxes:
            cls_id = int(box.cls)
            label = model.names[cls_id]
            conf = float(box.conf)
            if label == "person" and conf > threshold:
                return conf
    return 0.0

