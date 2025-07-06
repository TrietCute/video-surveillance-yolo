# main.py
import sys
from pathlib import Path
from fastapi import FastAPI, Query, HTTPException, WebSocket, WebSocketDisconnect
from bson import ObjectId
from pymongo import MongoClient
from pydantic import BaseModel
from threading import Thread
import os
import cv2
import numpy as np
import time
import asyncio

# --- Block code đảm bảo import hoạt động đáng tin cậy ---
FILE = Path(__file__).resolve()
ROOT = FILE.parents[0]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))
# -----------------------------------------------------------

from config import MONGO_URI, DB_NAME, COLLECTION_CAMERAS, COLLECTION_EVENTS, COLLECTION_ROOMS, VIDEO_OUTPUT_DIR
from object_detection.detector import Detector
from utils.logger import setup_logger

print("🔥 Python path:", sys.executable)

os.makedirs(VIDEO_OUTPUT_DIR, exist_ok=True)

app = FastAPI()
logger = setup_logger("main")

# Kết nối MongoDB
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
camera_col = db[COLLECTION_CAMERAS]
event_col = db[COLLECTION_EVENTS]
room_col = db[COLLECTION_ROOMS]

# Khởi tạo bộ phát hiện đối tượng
detector = Detector()

# Pydantic Models cho request body
class CameraIn(BaseModel):
    url: str
    room_id: str

class CameraUpdateIn(BaseModel):
    url: str

class CameraDeleteIn(BaseModel):
    url: str

class RoomIn(BaseModel):
    name: str

@app.get("/")
def root():
    return {"status": "API is running"}

# --- Quản lý Phòng ---
@app.get("/rooms")
def list_rooms():
    rooms = list(room_col.find())
    return [{"id": str(r["_id"]), "name": r["name"]} for r in rooms]

@app.post("/rooms")
def add_room(room: RoomIn):
    # Kiểm tra phòng đã tồn tại chưa
    existing_room = room_col.find_one({"name": room.name})
    if existing_room:
        raise HTTPException(status_code=400, detail=f"Room with name '{room.name}' already exists.")
    
    new_room_data = {"name": room.name}
    result = room_col.insert_one(new_room_data)
    logger.info(f"🚪 Đã thêm phòng: {room.name}")
    return {"id": str(result.inserted_id), "name": room.name}



@app.delete("/rooms/{room_id}")
def delete_room(room_id: str):
    try:
        # Chuyển đổi room_id từ string sang ObjectId
        object_id = ObjectId(room_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid room_id format.")

    # Xóa phòng trong collection rooms
    result = room_col.delete_one({"_id": object_id})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Room not found.")

    # (Nâng cao): Bạn cũng nên xóa các camera thuộc về phòng này
    # camera_col.delete_many({"room_id": object_id})
    # logger.info(f"Đã xóa các camera thuộc phòng {room_id}")

    logger.info(f"🚪 Đã xóa phòng: {room_id}")
    return {"status": "deleted", "id": room_id}


# --- Quản lý Camera ---
@app.post("/add-camera")
def add_camera(camera: CameraIn):
    if camera.url == "local":
        camera.url = "0"
    cam_id = camera_col.insert_one({"url": camera.url, "room_id": ObjectId(camera.room_id)}).inserted_id
    logger.info(f"📷 Thêm camera: {camera.url} vào phòng {camera.room_id}")
    return {"status": "added", "url": camera.url, "id": str(cam_id), "room_id": camera.room_id}

@app.get("/cameras")
def list_cameras():
    cams = list(camera_col.find({}, {"url": 1, "room_id": 1}))
    return [{"id": str(c["_id"]), "url": c["url"], "room_id": str(c.get("room_id", ""))} for c in cams]

@app.delete("/delete-camera")
def delete_camera(camera: CameraDeleteIn):
    result = camera_col.delete_one({"url": camera.url})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Camera not found")
    logger.info(f"🗑️ Đã xóa camera: {camera.url}")
    return {"status": "deleted", "url": camera.url}
@app.put("/cameras/{camera_id}")
def update_camera(camera_id: str, camera_data: CameraUpdateIn):
    try:
        object_id = ObjectId(camera_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid camera_id format.")

    result = camera_col.update_one(
        {"_id": object_id},
        {"$set": {"url": camera_data.url}}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Camera not found.")

    logger.info(f"✏️ Đã cập nhật URL camera {camera_id}")
    # Trả về camera đã được cập nhật
    updated_camera = camera_col.find_one({"_id": object_id})
    return {
        "id": str(updated_camera["_id"]),
        "url": updated_camera["url"],
        "room_id": str(updated_camera.get("room_id", ""))
    }

# --- Quản lý File Sự kiện ---
@app.get("/camera-files")
def camera_files(camera_id: str = Query(...)):
    try:
        query = {"camera_id": ObjectId(camera_id)}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid camera_id format.")
        
    events = event_col.find(query)
    return {"videos": [event.get("video_path", "").replace("\\", "/") for event in events]}

@app.delete("/camera-files")
def delete_camera_file(camera_id: str = Query(...), video_path: str = Query(...)):
    try:
        res = event_col.delete_many({"camera_id": ObjectId(camera_id), "video_path": video_path})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid camera_id format.")

    fs_path = Path(video_path)
    if fs_path.exists():
        try:
            fs_path.unlink()
            logger.info(f"📹 Đã xóa file video: {video_path}")
        except OSError as e:
            logger.error(f"Lỗi khi xóa file {video_path}: {e}")
            raise HTTPException(status_code=500, detail=f"Error deleting file: {e}")
            
    return {"deletedCount": res.deleted_count}

# --- WebSocket cho Video Stream và Phát hiện ---
@app.websocket("/ws/video")
async def websocket_video(websocket: WebSocket):
    await websocket.accept()
    logger.info("🔌 WebSocket client connected.")
    
    last_detect_time = 0
    detection_interval = 1.0

    try:
        while True:
            data = await websocket.receive_bytes()
            frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)

            if frame is None:
                continue

            with detector.lock:
                detector.latest_raw_frame = frame.copy()

            now = time.time()
            if now - last_detect_time >= detection_interval:
                Thread(target=detector.detect_on_frame, args=(frame.copy(),)).start()
                last_detect_time = now

            annotated_frame = detector.get_latest_annotated_frame()
            if annotated_frame is None:
                annotated_frame = frame

            _, jpeg = cv2.imencode(".jpg", annotated_frame)
            await websocket.send_bytes(jpeg.tobytes())

            await asyncio.sleep(1 / 30)

    except WebSocketDisconnect:
        logger.info("🔌 WebSocket client disconnected.")
    except Exception as e:
        logger.error(f"Lỗi WebSocket: {e}")
    finally:
        detector.cleanup()
        detector.running = False  # đảm bảo đã dừng


#Room management
@app.get("/rooms")
def list_rooms():
    rooms = list(room_col.find())
    return [{"id": str(r["_id"]), "name": r["name"]} for r in rooms]

@app.post("/rooms")
def add_room(name: str = Body(..., embed=True)):
    room = {"name": name}
    result = room_col.insert_one(room)
    return {"id": str(result.inserted_id), "name": name}