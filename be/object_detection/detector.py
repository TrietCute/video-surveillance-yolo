import cv2
import os
import time
from datetime import datetime
from threading import Lock, Thread
from ultralytics import YOLO
from utils.helpers import draw_boxes
from utils.logger import log_event
from config import VIDEO_OUTPUT_DIR, FPS
from .alert_logic import check_dangerous_animal, check_weapon
from .pose_analyzer import analyze_pose


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

    def start_video_writers(self, frame, label):
        os.makedirs(VIDEO_OUTPUT_DIR, exist_ok=True)
        h, w, _ = frame.shape
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        ts = datetime.now().strftime("%M%S")
        raw_path = os.path.join(VIDEO_OUTPUT_DIR, f"{label}_{ts}_clean.mp4")
        anno_path = os.path.join(VIDEO_OUTPUT_DIR, f"{label}_{ts}_annotated.mp4")
        return (cv2.VideoWriter(raw_path, fourcc, FPS, (w, h)),
                cv2.VideoWriter(anno_path, fourcc, FPS, (w, h))), (raw_path, anno_path)

    def outside_working_hours(self):
        now = datetime.now()
        return now.hour < 8 or now.hour >= 18

    def detect_on_frame(self, frame):
        now = time.time()

        with self.lock:
            self.latest_raw_frame = frame.copy()

        if now - self.last_detect_time < self.DETECT_INTERVAL:
            return  # chưa tới thời gian detect

        results = self.model(frame)
        self.latest_boxes = results[0].boxes if len(results) > 0 else None
        abnormal, conf = self.contains_person_or_animal(results)

        # logic
        analyze_pose(results, frame, source_id="ws-stream")
        check_dangerous_animal(results, source_id="ws-stream", video_path=self.path_clean if self.abnormal_mode else "")
        check_weapon(results, source_id="ws-stream", video_path=self.path_clean if self.abnormal_mode else "")

        for r in results:
            for box in r.boxes:
                label = self.model.names[int(box.cls)]
                conf = float(box.conf)
                if label == "person" and self.outside_working_hours():
                    log_event("person_outside_working_hours", conf, "ws-stream", video_path="")

        if abnormal and not self.abnormal_mode:
            self.abnormal_mode = True
            self.start_abnormal_time = now
            writers, paths = self.start_video_writers(frame, "ws")
            self.out_clean, self.out_annotated = writers
            self.path_clean, _ = paths
            log_event("abnormal_ws", conf, "ws-stream", self.path_clean)

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
