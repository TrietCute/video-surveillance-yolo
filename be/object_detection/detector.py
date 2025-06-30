import cv2
import os
import time
from datetime import datetime
from threading import Lock
from ultralytics import YOLO
from utils.helpers import draw_boxes
from utils.logger import log_event
from config import VIDEO_OUTPUT_DIR, FPS


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
        self.lock = Lock()

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

    def process_frame(self, frame):
        now = time.time()
        annotated_frame = frame.copy()

        if now - self.last_detect_time >= self.DETECT_INTERVAL:
            results = self.model(frame)
            abnormal, conf = self.contains_person_or_animal(results)

            if abnormal and not self.abnormal_mode:
                self.abnormal_mode = True
                self.start_abnormal_time = now
                writers, paths = self.start_video_writers(frame, "ws")
                self.out_clean, self.out_annotated = writers
                path_clean, path_annotated = paths
                log_event("abnormal_ws", conf, "ws-stream", path_clean)

            if self.abnormal_mode:
                annotated_frame = draw_boxes(frame.copy(), results[0])
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

            self.last_detect_time = now

        return annotated_frame

    def cleanup(self):
        if self.out_clean:
            self.out_clean.release()
        if self.out_annotated:
            self.out_annotated.release()
