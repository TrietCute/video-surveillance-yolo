# utils/logger.py

import os
from datetime import datetime
from pymongo import MongoClient
from config import MONGO_URI, DB_NAME, COLLECTION_NAME
import cv2

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
collection = db[COLLECTION_NAME]


def log_event(label, conf, frame, save_img=False):
    now = datetime.now()
    doc = {
        "timestamp": now,
        "object": label,
        "confidence": round(float(conf), 2),
        "frame_shape": frame.shape,
    }
    collection.insert_one(doc)
    print(f"✅ Ghi nhận: {label} ({conf:.2f})")

    if save_img:
        if not os.path.exists("snapshots"):
            os.makedirs("snapshots")
        filename = now.strftime(f"snapshots/%Y%m%d_%H%M%S_{label}.jpg")
        cv2.imwrite(filename, frame)
        print(f"📸 Ảnh lưu tại: {filename}")
