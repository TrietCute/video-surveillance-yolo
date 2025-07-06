import cv2
import os
import time
from datetime import datetime
from threading import Lock, Thread
from ultralytics import YOLO
from utils.helpers import draw_boxes
from utils.logger import log_event
from config import VIDEO_OUTPUT_DIR, FPS, MONGO_URI, DB_NAME, COLLECTION_CAMERAS
from .alert_logic import check_dangerous_animal, check_weapon
from .pose_analyzer import analyze_pose
from pymongo import MongoClient
from bson import ObjectId

class Detector:
    def __init__(self):
        self.model = YOLO("yolov8n.pt")
        self.ANIMAL_CLASSES = {"dog", "cat", "bear", "elephant", "tiger", "lion"}

        self.abnormal_mode = False
        self.start_abnormal_time = 0
        self.last_detect_time = 0
        self.DETECT_INTERVAL = 1  # seconds
        self.ABNORMAL_DURATION = 30  # seconds

        self.out_clean = None
        self.out_annotated = None
        self.path_clean = ""

        self.lock = Lock()
        self.latest_raw_frame = None
        self.latest_boxes = None

        client = MongoClient(MONGO_URI)
        self.camera_col = client[DB_NAME][COLLECTION_CAMERAS]

    def contains_person_or_animal(self, results, threshold=0.5):
        for r in results:
            for box in r.boxes:
                label = self.model.names[int(box.cls)]
                conf = float(box.conf)
                if label == "person" and conf > threshold:
                    return True, conf
                if label in self.ANIMAL_CLASSES and conf > threshold:
                    return True, conf
        return False, 0.0

    def start_video_writers(self, frame, label, room_id=None, camera_id=None):
        h, w, _ = frame.shape
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        now = datetime.now()
        ts = now.strftime("%M%S")
        date_str = now.strftime("%Y-%m-%d")
        hour_str = now.strftime("%H")

        room_folder = str(room_id) if room_id else "unknown_room"
        camera_folder = str(camera_id) if camera_id else "unknown_camera"

        folder = os.path.join(VIDEO_OUTPUT_DIR, room_folder, camera_folder, date_str, hour_str)
        os.makedirs(folder, exist_ok=True)

        raw_path = os.path.join(folder, f"{label}_{ts}_clean.mp4")
        anno_path = os.path.join(folder, f"{label}_{ts}_annotated.mp4")

        return (
            cv2.VideoWriter(raw_path, fourcc, FPS, (w, h)),
            cv2.VideoWriter(anno_path, fourcc, FPS, (w, h))
        ), (raw_path, anno_path)

    def outside_working_hours(self):
        now = datetime.now()
        return now.hour < 8 or now.hour >= 18

    def detect_on_frame(self, frame, camera_id=None):
        now = time.time()

        with self.lock:
            self.latest_raw_frame = frame.copy()

        if now - self.last_detect_time < self.DETECT_INTERVAL:
            return

        results = self.model(frame)
        self.latest_boxes = results[0].boxes if len(results) > 0 else None
        abnormal, conf = self.contains_person_or_animal(results)

        room_id = None
        if camera_id:
            cam = self.camera_col.find_one({"_id": ObjectId(camera_id)})
            if cam:
                room_id = cam.get("room_id")

        analyze_pose(results, frame, source_id=str(camera_id or "ws-stream"))
        check_dangerous_animal(results, source_id=str(camera_id or "ws-stream"), video_path=self.path_clean if self.abnormal_mode else "")
        check_weapon(results, source_id=str(camera_id or "ws-stream"), video_path=self.path_clean if self.abnormal_mode else "")

        for r in results:
            for box in r.boxes:
                label = self.model.names[int(box.cls)]
                conf = float(box.conf)
                if label == "person" and self.outside_working_hours():
                    log_event("person_outside_working_hours", conf, str(camera_id or "ws-stream"), video_path="")

        if abnormal and not self.abnormal_mode:
            self.abnormal_mode = True
            self.start_abnormal_time = now
            writers, paths = self.start_video_writers(frame, label="abnormal", room_id=room_id, camera_id=camera_id)
            self.out_clean, self.out_annotated = writers
            self.path_clean, _ = paths
            log_event("abnormal_detected", conf, str(camera_id or "ws-stream"), self.path_clean)

        if self.abnormal_mode:
            annotated_frame = draw_boxes(frame.copy(), results[0].boxes)
            if self.out_clean:
                self.out_clean.write(frame)
            if self.out_annotated:
                self.out_annotated.write(annotated_frame)

            if now - self.start_abnormal_time >= self.ABNORMAL_DURATION:
                self.abnormal_mode = False
                if self.out_clean:
                    self.out_clean.release()
                    self.out_clean = None
                if self.out_annotated:
                    self.out_annotated.release()
                    self.out_annotated = None
                self.path_clean = ""

        self.last_detect_time = now

    def get_latest_annotated_frame(self):
        with self.lock:
            if self.latest_raw_frame is None:
                return None
            annotated = self.latest_raw_frame.copy()
            if self.latest_boxes is not None:
                annotated = draw_boxes(annotated, self.latest_boxes)
            return annotated

    def cleanup(self):
        if self.out_clean:
            self.out_clean.release()
        if self.out_annotated:
            self.out_annotated.release()
