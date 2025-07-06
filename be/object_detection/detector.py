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
    def __init__(self, cam_id: str):
        self.model = YOLO("best.pt")
        self.cam_id = cam_id
        self.running = True
        self.lock = Lock()

        # Trạng thái phát hiện
        self.latest_raw_frame = None
        self.latest_boxes = None
        self.last_detect_time = 0
        self.last_abnormal_time = 0
        
        # Cờ hiệu cho biết có sự kiện bất thường đang diễn ra hay không
        self.is_abnormal = False

        # Các hằng số
        self.DETECT_INTERVAL = 1  # Chỉ chạy phát hiện mỗi giây một lần
        self.ABNORMAL_END_DELAY = 5  # Tăng thời gian chờ để tránh dừng ghi hình quá sớm
        self.STAY_THRESHOLD = 10  # Thời gian một người được phép đứng gần cửa

    def outside_working_hours(self):
        now = time.localtime()
        return now.tm_hour < 8 or now.tm_hour >= 20

    def detect_on_frame(self, frame):
        now = time.time()

        # Giới hạn tần suất phát hiện để tiết kiệm tài nguyên
        if now - self.last_detect_time < self.DETECT_INTERVAL:
            return

        # Chỉ phát hiện các class cho phép
        class_ids = [
            i for i, name in self.model.names.items()
            if name.lower() in ALLOWED_CLASSES
        ]
        results = self.model(frame, classes=class_ids, verbose=True) # Thêm verbose=False để log gọn hơn
        
        with self.lock:
            self.latest_boxes = results[0].boxes if results else None

        # Tách các loại object ra từng nhóm
        person_boxes, weapon_boxes, animal_boxes, door_boxes = [], [], [], []

        if not self.latest_boxes:
            # Nếu không phát hiện đối tượng nào, kiểm tra xem có nên kết thúc trạng thái bất thường không
            if self.is_abnormal and (now - self.last_abnormal_time > self.ABNORMAL_END_DELAY):
                print(f"[INFO] 🛑 Kết thúc trạng thái bất thường cho cam {self.cam_id} do không có phát hiện.")
                self.is_abnormal = False
                log_event("abnormal_end", 1.0, self.cam_id, video_path="")
            self.last_detect_time = now
            return

        for r in results:
            for box in r.boxes:
                label = self.model.names[int(box.cls)].lower()
                
                if label in HUMAN_CLASSES:
                    person_boxes.append(box)
                elif label in WEAPON_CLASSES:
                    weapon_boxes.append(box)
                elif label in DANGEROUS_ANIMALS:
                    animal_boxes.append(box)
                elif label == "door":
                    door_boxes.append(box)

        # === LOGIC KIỂM TRA SỰ KIỆN BẤT THƯỜNG ===
        is_currently_abnormal = False

        # 1. Động vật nguy hiểm
        if animal_boxes:
            is_currently_abnormal = True
            log_event("dangerous_animal", float(animal_boxes[0].conf), self.cam_id, video_path="")

        # 2. Người ngoài giờ làm việc
        if person_boxes and self.outside_working_hours():
            is_currently_abnormal = True
            log_event("person_outside_working_hours", float(person_boxes[0].conf), self.cam_id, video_path="")

        # 3. Người cầm vũ khí
        for pbox in person_boxes:
            px1, py1, px2, py2 = map(int, pbox.xyxy[0])
            for wbox in weapon_boxes:
                wx1, wy1, wx2, wy2 = map(int, wbox.xyxy[0])
                if not (wx2 < px1 or wx1 > px2 or wy2 < py1 or wy1 > py2):
                    is_currently_abnormal = True
                    log_event("person_with_weapon", float(wbox.conf), self.cam_id, video_path="")
                    break
            if is_currently_abnormal: break

        # 4. Người đứng gần cửa quá lâu
        near_door = False
        for pbox in person_boxes:
            px1, py1, px2, py2 = map(int, pbox.xyxy[0])
            pcx, pcy = (px1 + px2) // 2, (py1 + py2) // 2
            for dbox in door_boxes:
                dx1, dy1, dx2, dy2 = map(int, dbox.xyxy[0])
                if dx1 <= pcx <= dx2 and dy1 <= pcy <= dy2:
                    near_door = True
                    break
            if near_door: break

        if near_door:
            if not hasattr(self, "door_start_time"):
                self.door_start_time = now
            elif now - self.door_start_time > self.STAY_THRESHOLD:
                is_currently_abnormal = True
                log_event("person_standing_too_long_near_door", 1.0, self.cam_id, video_path="")
        else:
            if hasattr(self, "door_start_time"):
                del self.door_start_time
        
        # === CẬP NHẬT TRẠNG THÁI BẤT THƯỜNG CHUNG ===
        if is_currently_abnormal:
            self.last_abnormal_time = now
            if not self.is_abnormal:
                print(f"[INFO] 🔥 Bắt đầu trạng thái bất thường cho cam {self.cam_id}")
                self.is_abnormal = True
        elif self.is_abnormal and (now - self.last_abnormal_time > self.ABNORMAL_END_DELAY):
            print(f"[INFO] 🛑 Kết thúc trạng thái bất thường cho cam {self.cam_id}")
            self.is_abnormal = False
            log_event("abnormal_end", 1.0, self.cam_id, video_path="")

        self.last_detect_time = now

    def get_latest_annotated_frame(self):
        with self.lock:
            frame = self.latest_raw_frame.copy() if self.latest_raw_frame is not None else None
            if frame is None:
                return None
            
            # Vẽ các box phát hiện mới nhất lên frame
            if self.latest_boxes:
                frame = draw_boxes(frame, self.latest_boxes, self.model.names)     
            return frame

    def cleanup(self):
        print(f"Cleanup detector for cam {self.cam_id}")
        pass
