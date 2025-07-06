import time
import os
import cv2
import numpy as np
from threading import Lock
from ultralytics import YOLO
from queue import Queue
from utils.helpers import draw_boxes
from utils.logger import log_event
from .allowed_classes import ALLOWED_CLASSES, DANGEROUS_ANIMALS, WEAPON_CLASSES, HUMAN_CLASSES
from config import VIDEO_OUTPUT_DIR

class Detector:
    def __init__(self, cam_id: str, event_queue: Queue = None):
        self.model = YOLO("yolov8l-oiv7.pt")
        self.cam_id = cam_id
        self.event_queue = event_queue
        self.running = True
        self.lock = Lock()
        self.latest_raw_frame = None
        self.latest_boxes = None
        self.last_detect_time = 0
        self.last_abnormal_time = 0
        self.abnormal_state = False

        self.should_record = False
        self.frame_queue = Queue(maxsize=300)

        self.DETECT_INTERVAL = 1
        self.ABNORMAL_END_DELAY = 5

    def outside_working_hours(self):
        now = time.localtime()
        return now.tm_hour < 8 or now.tm_hour >= 20

    def detect_on_frame(self, frame):
        now = time.time()
        if now - self.last_detect_time < self.DETECT_INTERVAL:
            return

        class_ids = [i for i, name in self.model.names.items() if name.lower() in ALLOWED_CLASSES]
        results = self.model(frame, classes=class_ids)
        self.latest_boxes = results[0].boxes if results else None

        person_boxes, weapon_boxes, animal_boxes, door_boxes = [], [], [], []

        for r in results:
            for box in r.boxes:
                label = self.model.names[int(box.cls)].lower()
                conf = float(box.conf)
                if label in HUMAN_CLASSES:
                    person_boxes.append(box)
                    if self.outside_working_hours():
                        log_event("person_outside_working_hours", conf, self.cam_id, video_path="")
                elif label in WEAPON_CLASSES:
                    weapon_boxes.append(box)
                elif label in DANGEROUS_ANIMALS:
                    animal_boxes.append(box)
                elif label == "door":
                    door_boxes.append(box)

        for box in animal_boxes:
            log_event("dangerous_animal", float(box.conf), self.cam_id, video_path="")

        for pbox in person_boxes:
            px1, py1, px2, py2 = map(int, pbox.xyxy[0])
            for wbox in weapon_boxes:
                wx1, wy1, wx2, wy2 = map(int, wbox.xyxy[0])
                if not (wx2 < px1 or wx1 > px2 or wy2 < py1 or wy1 > py2):
                    log_event("person_with_weapon", float(wbox.conf), self.cam_id, video_path="")

        # Kiểm tra người đứng gần cửa
        STAY_THRESHOLD = 10  # giây
        near_door = False
        is_standing_too_long = False

        for pbox in person_boxes:
            px1, py1, px2, py2 = map(int, pbox.xyxy[0])
            pcx, pcy = (px1 + px2) // 2, (py1 + py2) // 2

            for dbox in door_boxes:
                dx1, dy1, dx2, dy2 = map(int, dbox.xyxy[0])
                if dx1 <= pcx <= dx2 and dy1 <= pcy <= dy2:
                    near_door = True
                    break
            if near_door:
                break

        if near_door:
            if not hasattr(self, "door_start_time"):
                self.door_start_time = now
            elif now - self.door_start_time > STAY_THRESHOLD:
                is_standing_too_long = True
                video_path = os.path.join(VIDEO_OUTPUT_DIR, f"{self.cam_id}_door_{int(now)}.mp4")
                log_event("person_standing_too_long_near_door", 1.0, self.cam_id, video_path=video_path)
        else:
            if hasattr(self, "door_start_time"):
                del self.door_start_time

        # Kiểm tra trạng thái bất thường
        abnormal = (
            bool(animal_boxes) or
            (person_boxes and self.outside_working_hours()) or
            (person_boxes and weapon_boxes) or
            is_standing_too_long
        )

        annotated = draw_boxes(frame.copy(), self.latest_boxes, self.model.names) if self.latest_boxes else frame.copy()

        if abnormal:
            self.last_abnormal_time = now
            if not self.abnormal_state:
                self.abnormal_state = True
                self.should_record = True
                video_path = os.path.join(VIDEO_OUTPUT_DIR, f"{self.cam_id}_{int(now)}.mp4")
                if self.event_queue:
                    self.event_queue.put({"type": "start", "frame": frame.copy(), "annotated": annotated, "timestamp": now, "video_path": video_path})
            else:
                if self.event_queue:
                    self.event_queue.put({"type": "continue", "frame": frame.copy(), "annotated": annotated, "timestamp": now})
        elif self.abnormal_state and (now - self.last_abnormal_time > self.ABNORMAL_END_DELAY):
            self.abnormal_state = False
            self.should_record = False
            if self.event_queue:
                self.event_queue.put({"type": "stop", "timestamp": now})

        self.last_detect_time = now

    def get_latest_annotated_frame(self):
        with self.lock:
            frame = self.latest_raw_frame.copy() if self.latest_raw_frame is not None else None
            if frame is None:
                return None
            if self.latest_boxes:
                frame = draw_boxes(frame, self.latest_boxes, self.model.names)
            return frame

    def cleanup(self):
        pass

    def force_stop_recording(self):
        if self.abnormal_state and self.event_queue:
            self.abnormal_state = False
            self.event_queue.put({
                "type": "stop",
                "timestamp": time.time()
            })

     # === Hàm detect_on_frame mới: detect và vẽ box tất cả object ===

    # def detect_on_frame(self, frame):
    #     now = time.time()
    #     if now - self.last_detect_time < self.DETECT_INTERVAL:
    #         return

    #     results = self.model(frame)
    #     self.latest_boxes = results[0].boxes if results else None

    #     if self.latest_boxes:
    #         annotated = draw_boxes(frame.copy(), self.latest_boxes, self.model.names)
    #     else:
    #         annotated = frame.copy()

    #     if self.event_queue:
    #         self.event_queue.put({
    #             "type": "frame",
    #             "frame": frame.copy(),
    #             "annotated": annotated,
    #             "timestamp": now
    #         })

    #     self.last_detect_time = now
    # def get_latest_annotated_frame(self):
    #     with self.lock:
    #         frame = self.latest_raw_frame.copy() if self.latest_raw_frame is not None else None
    #         if frame is None:
    #             return None
    #         if self.latest_boxes:
    #             frame = draw_boxes(frame, self.latest_boxes, self.model.names)
    #         return frame

    # def cleanup(self):
    #     pass
    # def force_stop_recording(self):
    #     if self.abnormal_state and self.event_queue:
    #         self.abnormal_state = False
    #         self.event_queue.put({
    #             "type": "stop",
    #             "timestamp": time.time()
    #         }) 