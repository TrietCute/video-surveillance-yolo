import cv2
import numpy as np
import time
import datetime
import os
from ultralytics import YOLO
from utils.logger import log_event, setup_logger
from utils.helpers import draw_boxes
from config import VIDEO_CLIP_DURATION, VIDEO_OUTPUT_DIR, FPS

logger = setup_logger("detector")
model = YOLO("yolov8n-pose.pt")  # Use pose model
stop_flags = {}
realtime_state = {}
test_video_frames = {}  # Global dict for test stream

TRACK_CLASSES = {"person", "cat", "dog", "snake","cow"}

# --- Common ---
def contains_target(results, threshold=0.5):
    for r in results:
        for box in r.boxes:
            cls_id = int(box.cls)
            label = model.names[cls_id]
            conf = float(box.conf)
            if label in TRACK_CLASSES and conf > threshold:
                return True
    return False

def get_target_confidence(results, threshold=0.5):
    for r in results:
        for box in r.boxes:
            cls_id = int(box.cls)
            label = model.names[cls_id]
            conf = float(box.conf)
            if label in TRACK_CLASSES and conf > threshold:
                return conf
    return 0.0

def prepare_output_directory():
    now = datetime.datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    hour_str = now.strftime("%H")
    os.makedirs(os.path.join(VIDEO_OUTPUT_DIR, date_str, hour_str), exist_ok=True)
    return date_str, hour_str

# --- Stop ---
def stop_detecting(source):
    stop_flags[str(source)] = True

# --- Camera or Video File Detect ---
def initialize_video_capture(source):
    actual_source = 0 if str(source) == "0" else str(source)
    cap = cv2.VideoCapture(actual_source, cv2.CAP_DSHOW if str(source) == "0" else 0)
    if not cap.isOpened():
        logger.error(f"❌ Không thể mở nguồn video: {actual_source}")
        return None, actual_source
    logger.info(f"📹 Đang xử lý nguồn: {actual_source}")
    return cap, actual_source

def start_recording(cap, label, date_str, hour_str):
    now = datetime.datetime.now()
    filename = f"{label}_{now.strftime('%M%S')}.mp4"
    filepath = os.path.join(VIDEO_OUTPUT_DIR, date_str, hour_str, filename)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    frame_size = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    out = cv2.VideoWriter(filepath, fourcc, FPS, frame_size)
    logger.info(f"🎥 Bắt đầu ghi video: {filepath}")
    return out, filepath

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

            results = model(frame)
            annotated_frame = draw_boxes(frame.copy(), results[0]) if results else frame

            if contains_target(results) and not recording:
                out, filepath = start_recording(cap, "target", date_str, hour_str)
                recording = True
                record_start_time = time.time()
                log_event("target", get_target_confidence(results), source=str(source), video_path=filepath)

            if recording and out is not None:
                out.write(frame)
                if time.time() - record_start_time >= VIDEO_CLIP_DURATION:
                    recording = False
                    out.release()
                    out = None

            if display:
                cv2.imshow("Surveillance", annotated_frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

    finally:
        if cap: cap.release()
        if out: out.release()
        if display:
            cv2.destroyAllWindows()

# --- Realtime Frame (test video) ---
def start_recording_frame(frame, label, date_str, hour_str):
    now = datetime.datetime.now()
    filename = f"{label}_{now.strftime('%M%S')}.mp4"
    filepath = os.path.join(VIDEO_OUTPUT_DIR, date_str, hour_str, filename)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    h, w, _ = frame.shape
    out = cv2.VideoWriter(filepath, fourcc, FPS, (w, h))
    logger.info(f"🎥 Ghi realtime: {filepath}")
    return out, filepath

def process_frame_realtime(frame_bytes, source_id="test-video", display=True):
    if source_id not in realtime_state:
        realtime_state[source_id] = {
            "recording": False,
            "record_start_time": None,
            "out": None,
            "date_str": None,
            "hour_str": None,
        }

    state = realtime_state[source_id]

    np_arr = np.frombuffer(frame_bytes, np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if frame is None:
        return

    results = model(frame)
    annotated_frame = draw_boxes(frame.copy(), results[0]) if results else frame
    test_video_frames[source_id] = annotated_frame.copy()

    if contains_target(results) and not state["recording"]:
        state["date_str"], state["hour_str"] = prepare_output_directory()
        state["out"], filepath = start_recording_frame(frame, "realtime", state["date_str"], state["hour_str"])
        state["recording"] = True
        state["record_start_time"] = time.time()
        log_event("target", get_target_confidence(results), source=source_id, video_path=filepath)

    if state["recording"] and state["out"] is not None:
        state["out"].write(frame)
        if time.time() - state["record_start_time"] >= VIDEO_CLIP_DURATION:
            state["recording"] = False
            state["out"].release()
            state["out"] = None
