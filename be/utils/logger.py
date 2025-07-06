# utils/logger.py
import logging
from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId

from config import (
    MONGO_URI,
    DB_NAME,
    COLLECTION_EVENTS,
    COLLECTION_CAMERAS,
    COLLECTION_ROOMS
)

# Thiết lập MongoDB
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
event_collection = db[COLLECTION_EVENTS]
camera_collection = db[COLLECTION_CAMERAS]
room_collection = db[COLLECTION_ROOMS]

# Logger setup
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


# utils/logger.py
from bson import ObjectId, errors

def log_event(object_name, confidence, camera_id, video_path):
    from config import DB_NAME, COLLECTION_EVENTS, MONGO_URI
    from pymongo import MongoClient
    from datetime import datetime

    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    events = db[COLLECTION_EVENTS]
    camera_collection = db[COLLECTION_CAMERAS]
    room_collection = db[COLLECTION_ROOMS]

    # Ensure video_path is string
    if not isinstance(video_path, str):
        video_path = str(video_path)

    # Thử truy vấn room_id từ camera nếu camera_id hợp lệ
    room_id = None
    try:
        camera_obj = camera_collection.find_one({"_id": ObjectId(camera_id)})
        if camera_obj:
            room_id = camera_obj.get("room_id")
    except (errors.InvalidId, TypeError):
        print(f"[⚠️] Không phải ObjectId hợp lệ: {camera_id}")

    event = {
        "timestamp": datetime.now().isoformat(),
        "object": object_name,
        "confidence": round(confidence, 2),
        "camera_id": ObjectId(camera_id),
        "video_path": video_path,
        "room_id": str(room_id) if room_id else None,
    }

    print(f"[INFO] 🎞 Clip lưu tại: {video_path}")
    print(f"[INFO] ✅ Ghi log sự kiện: {object_name} ({confidence})")

    events.insert_one(event)
