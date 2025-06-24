import os
import cv2
import logging
from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId

from config import (
    MONGO_URI,
    DB_NAME,
    COLLECTION_EVENTS,
    COLLECTION_CAMERAS,
    IMAGE_OUTPUT_DIR,
    VIDEO_OUTPUT_DIR,
)
from utils.helpers import record_clip

# Thiết lập MongoDB
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
event_collection = db[COLLECTION_EVENTS]
camera_collection = db[COLLECTION_CAMERAS]


# Logger
def setup_logger(name="app"):
    logger = logging.getLogger(name)
    if not logger.hasHandlers():
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


logger = setup_logger("detector")


# Lưu camera vào MongoDB nếu chưa có
def save_camera(url: str) -> ObjectId:
    cam = camera_collection.find_one({"url": url})
    if cam:
        return cam["_id"]
    result = camera_collection.insert_one({"url": url, "created_at": datetime.now()})
    logger.info(f"📡 Đã lưu camera mới: {url}")
    return result.inserted_id


# Ghi log sự kiện phát hiện
def log_event(label, conf, frame=None, save_img=True, source=None):
    
    now = datetime.now()
    timestamp = now.isoformat()
    source_str = str(source) if source is not None else None
    camera_id = save_camera(source_str) if source_str else None
    if camera_id is None:
        logger.error("❌ Không tìm thấy hoặc lưu camera. Bỏ qua sự kiện.")
        return

    doc = {
        "timestamp": timestamp,
        "object": label,
        "confidence": round(float(conf), 2),
        "camera_id": camera_id,
    }

    if frame is not None:
        doc["frame_shape"] = frame.shape

    # Lưu ảnh nếu cần
    if save_img and frame is not None:
        date_str = now.strftime("%Y-%m-%d")
        hour_str = now.strftime("%H")
        folder = os.path.join(IMAGE_OUTPUT_DIR, date_str, hour_str)
        os.makedirs(folder, exist_ok=True)

        filename = os.path.join(folder, f"{label}_{now.strftime('%M%S')}.jpg")
        success = cv2.imwrite(filename, frame)
        if success:
            doc["image_path"] = filename
            logger.info(f"📸 Ảnh lưu tại: {filename}")
        else:
            logger.warning("⚠️ Không thể lưu ảnh")

    # Lưu video nếu có source
    if source is not None:
        video_path = record_clip(source, label)
        if video_path:
            doc["video_path"] = video_path
            logger.info(f"🎞  Clip lưu tại: {video_path}")

    event_collection.insert_one(doc)
    logger.info(f"✅ Ghi log sự kiện: {label} ({conf:.2f})")
