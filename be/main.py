# main.py
import sys
from pathlib import Path
import queue
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
from utils.logger import log_event
from urllib.parse import urlparse

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

# Pydantic Models
class CameraIn(BaseModel):
    url: str
    room_id: str
class CameraUpdateIn(BaseModel):
    url: str
class CameraDeleteIn(BaseModel):
    url: str
class RoomIn(BaseModel):
    name: str

# API Endpoints
@app.get("/")
def root(): return {"status": "API is running"}

# --- Quản lý Phòng (ĐÃ KHÔI PHỤC ĐẦY ĐỦ) ---
@app.get("/rooms")
def list_rooms():
    rooms = list(room_col.find())
    return [{"id": str(r["_id"]), "name": r["name"]} for r in rooms]

@app.post("/rooms")
def add_room(room: RoomIn):
    if room_col.find_one({"name": room.name}):
        raise HTTPException(status_code=400, detail=f"Room with name '{room.name}' already exists.")
    result = room_col.insert_one({"name": room.name})
    logger.info(f"🚪 Đã thêm phòng: {room.name}")
    return {"id": str(result.inserted_id), "name": room.name}

@app.put("/rooms/{room_id}")
def update_room(room_id: str, room: RoomIn):
    try:
        object_id = ObjectId(room_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid room_id format.")
    existing_room = room_col.find_one({"name": room.name})
    if existing_room and existing_room["_id"] != object_id:
        raise HTTPException(status_code=400, detail=f"Room with name '{room.name}' already exists.")
    result = room_col.update_one({"_id": object_id}, {"$set": {"name": room.name}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Room not found.")
    logger.info(f"✏️ Đã cập nhật phòng {room_id} thành '{room.name}'")
    updated_room = room_col.find_one({"_id": object_id})
    return {"id": str(updated_room["_id"]), "name": updated_room["name"]}

@app.delete("/rooms/{room_id}")
def delete_room(room_id: str):
    try:
        object_id = ObjectId(room_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid room_id format.")
    result = room_col.delete_one({"_id": object_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Room not found.")
    logger.info(f"🚪 Đã xóa phòng: {room_id}")
    return {"status": "deleted", "id": room_id}


# --- Quản lý Camera (ĐÃ KHÔI PHỤC ĐẦY ĐỦ) ---
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
    result = camera_col.update_one({"_id": object_id}, {"$set": {"url": camera_data.url}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Camera not found.")
    logger.info(f"✏️ Đã cập nhật URL camera {camera_id}")
    updated_camera = camera_col.find_one({"_id": object_id})
    return {"id": str(updated_camera["_id"]), "url": updated_camera["url"], "room_id": str(updated_camera.get("room_id", ""))}


# --- QUẢN LÝ FILE SỰ KIỆN ---
@app.get("/camera-files")
def camera_files(camera_id: str = Query(...), limit: int = Query(50)):
    try:
        query = {"camera_id": ObjectId(camera_id)}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid camera_id format.")
    events = event_col.find(query)
    video_paths = []
    for event in events:
        path = event.get("video_path")
        if path and isinstance(path, str) and path.strip():
            if path not in video_paths:
                video_paths.append(path.replace("\\", "/"))
    return {"videos": video_paths}

@app.delete("/camera-files")
def delete_camera_file(camera_id: str = Query(...), video_path: str = Query(...)):
    try:
        res = event_col.delete_many({"camera_id": ObjectId(camera_id), "video_path": video_path})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid camera_id format.")
    fs_path = Path(video_path)
    if fs_path.exists():
        try:
            annotated_path = fs_path.parent / "abnormal_annotated.mp4"
            fs_path.unlink()
            if annotated_path.exists():
                annotated_path.unlink()
            logger.info(f"📹 Đã xóa file video: {video_path} và file chú thích.")
        except OSError as e:
            logger.error(f"Lỗi khi xóa file {video_path}: {e}")
            raise HTTPException(status_code=500, detail=f"Error deleting file: {e}")
    return {"deletedCount": res.deleted_count}


# --- HỆ THỐNG XỬ LÝ VIDEO MỚI ---
DETECTOR_MAP = {}
RECORDER_THREADS = {}
FRAME_QUEUES = {}

def video_recorder(cam_id: str, frame_queue: queue.Queue, detector: Detector):
    out_clean = out_annotated = None
    is_recording = False
    video_path = ""
    FPS = 25

    # Truy xuất metadata từ camera_id
    try:
        camera_obj_id = ObjectId(cam_id)
        camera_doc = camera_col.find_one({"_id": camera_obj_id})
        if not camera_doc:
            raise ValueError(f"Không tìm thấy camera với ID: {cam_id}")

        # → Xử lý url thành camera_name
        url = camera_doc.get("url", "")
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname or "unknown_host"
        port = parsed_url.port or ""
        camera_name = f"camera_{hostname.replace('.', '_')}_{port}".strip("_")

        # → Truy xuất room name
        room_name = "unknown_room"
        room_id = camera_doc.get("room_id")
        if room_id:
            room_doc = room_col.find_one({"_id": room_id})
            if room_doc:
                room_name = room_doc.get("name", "unknown_room").replace(" ", "_")

    except Exception as e:
        print(f"[ERROR] Lỗi lấy metadata camera: {e}")
        camera_name = f"camera_{cam_id[:6]}"
        room_name = "unknown_room"

    while detector.running:
        try:
            frame_info = frame_queue.get(timeout=1)
            raw_frame = frame_info["frame"]
            timestamp = frame_info["timestamp"]

            if detector.is_abnormal:
                if not is_recording:
                    is_recording = True

                    # Phân tách ngày và giờ
                    date_str = time.strftime("%Y-%m-%d", time.localtime(timestamp))
                    time_str = time.strftime("%H-%M-%S", time.localtime(timestamp))

                    # Tạo thư mục lưu video
                    folder = os.path.join(VIDEO_OUTPUT_DIR, room_name, camera_name, date_str, time_str)
                    os.makedirs(folder, exist_ok=True)

                    # Tạo writer
                    h, w = raw_frame.shape[:2]
                    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                    path_clean = os.path.join(folder, "abnormal_clean.mp4").replace("\\", "/")
                    path_annotated = os.path.join(folder, "abnormal_annotated.mp4").replace("\\", "/")
                    video_path = path_clean

                    print(f"[DEBUG] 🎥 Bắt đầu ghi: {path_clean}")
                    out_clean = cv2.VideoWriter(path_clean, fourcc, FPS, (w, h))
                    out_annotated = cv2.VideoWriter(path_annotated, fourcc, FPS, (w, h))

                    # Ghi log hoặc sự kiện
                    log_event("abnormal_start", 1.0, cam_id, video_path=video_path, extras={
                        "room_name": room_name,
                        "camera_name": camera_name
                    })

                if out_clean and out_annotated:
                    annotated_frame = detector.get_latest_annotated_frame() or raw_frame
                    out_clean.write(raw_frame)
                    out_annotated.write(annotated_frame)

            elif is_recording:
                is_recording = False
                print(f"[DEBUG] 🛑 Dừng ghi video: {video_path}")
                if out_clean: out_clean.release()
                if out_annotated: out_annotated.release()
                out_clean = out_annotated = None
                video_path = ""

        except queue.Empty:
            if is_recording and not detector.is_abnormal:
                is_recording = False
                print(f"[DEBUG] 🛑 Dừng ghi video (do timeout): {video_path}")
                if out_clean: out_clean.release()
                if out_annotated: out_annotated.release()
                out_clean = out_annotated = None
                video_path = ""
            continue

    # Cleanup nếu vẫn đang ghi
    if is_recording:
        print(f"[DEBUG] 🛑 Dừng ghi video (do cleanup): {video_path}")
        if out_clean: out_clean.release()
        if out_annotated: out_annotated.release()

@app.websocket("/ws/video")
async def websocket_video(websocket: WebSocket, cam_id: str = Query(...)):
    await websocket.accept()
    detector = Detector(cam_id)
    frame_queue = queue.Queue(maxsize=300)
    DETECTOR_MAP[cam_id] = detector
    FRAME_QUEUES[cam_id] = frame_queue
    recorder_thread = Thread(target=video_recorder, args=(cam_id, frame_queue, detector), daemon=True)
    recorder_thread.start()
    RECORDER_THREADS[cam_id] = recorder_thread
    print(f"[INFO] ✅ WebSocket connected for cam_id: {cam_id}. Recorder thread started.")
    async def receive_loop():
        while detector.running:
            try:
                data = await websocket.receive_bytes()
                frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
                if frame is not None:
                    with detector.lock:
                        detector.latest_raw_frame = frame.copy()
                    try:
                        frame_queue.put_nowait({"frame": frame, "timestamp": time.time()})
                    except queue.Full:
                        try:
                            frame_queue.get_nowait()
                        except queue.Empty:
                            pass
                        try:
                            frame_queue.put_nowait({"frame": frame, "timestamp": time.time()})
                        except queue.Full:
                            pass
            except WebSocketDisconnect:
                print(f"[INFO] WebSocket disconnected by client: {cam_id}")
                detector.running = False
                break
            except Exception as e:
                print(f"[ERROR] receive_loop: {e}")
                detector.running = False
                break
    async def detect_loop():
        while detector.running:
            with detector.lock:
                frame = detector.latest_raw_frame.copy() if detector.latest_raw_frame is not None else None
            if frame is not None:
                detector.detect_on_frame(frame)
            await asyncio.sleep(0.5)
    async def stream_loop():
        while detector.running:
            try:
                annotated_frame = detector.get_latest_annotated_frame()
                if annotated_frame is not None:
                    _, jpeg = cv2.imencode(".jpg", annotated_frame)
                    await websocket.send_bytes(jpeg.tobytes())
                await asyncio.sleep(1 / 30)
            except WebSocketDisconnect:
                break 
            except Exception as e:
                print(f"[ERROR] stream_loop: {e}")
                break
    try:
        await asyncio.gather(
            receive_loop(),
            detect_loop(),
            stream_loop()
        )
    finally:
        print(f"[INFO] Cleaning up resources for cam_id: {cam_id}")
        detector.running = False
        if recorder_thread.is_alive():
            recorder_thread.join(timeout=2)
        DETECTOR_MAP.pop(cam_id, None)
        FRAME_QUEUES.pop(cam_id, None)
        RECORDER_THREADS.pop(cam_id, None)
        print(f"[INFO] Resources for {cam_id} cleaned up.")
