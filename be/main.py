# main.py
from fastapi import FastAPI, Query, Body, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from bson import ObjectId
from pymongo import MongoClient
from threading import Thread
import shutil, uuid, os, sys
from pathlib import Path
import cv2
import numpy as np
import time
import asyncio
from datetime import datetime
import os
from config import VIDEO_OUTPUT_DIR, FPS
from object_detection.detector import Detector 
from utils.logger import setup_logger, save_camera, log_event


from config import MONGO_URI, DB_NAME, COLLECTION_CAMERAS, COLLECTION_EVENTS, COLLECTION_ROOMS

print("🔥 Python path:", sys.executable)

os.makedirs(VIDEO_OUTPUT_DIR, exist_ok=True)

app = FastAPI()
logger = setup_logger("main")

# MongoDB
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
camera_col = db[COLLECTION_CAMERAS]
event_col = db[COLLECTION_EVENTS]
room_col = db[COLLECTION_ROOMS]

# Directory
TEST_VIDEO_DIR = "data/test-video"
os.makedirs(TEST_VIDEO_DIR, exist_ok=True)

# Stream management
active_threads = {}

@app.get("/")
def root():
    return {"status": "API is running"}

@app.post("/add-camera")
def add_camera(url: str = Body(...), room_id: str = Body(...)):
    if url == "local":
        url = "0"
    cam_id = camera_col.insert_one({"url": url, "room_id": ObjectId(room_id)}).inserted_id
    logger.info(f"📷 Thêm camera: {url} vào phòng {room_id}")
    return {"status": "added", "url": url, "id": str(cam_id), "room_id": room_id}

@app.get("/cameras")
def list_cameras():
    cams = list(camera_col.find({}, {"url": 1, "room_id": 1}))
    return [{"id": str(c["_id"]), "url": c["url"], "room_id": str(c.get("room_id", ""))} for c in cams]

@app.get("/start-stream")
def start_stream(url: str = Query(...)):
    source = "0" if url == "local" else url
    cam_id = save_camera(source)
    logger.info(f"▶️ Bắt đầu stream: {source}")

    if source in active_threads:
        return {"message": "Stream đã chạy", "camera_id": str(cam_id)}

    t = Thread(target=detect, args=(source,))
    t.daemon = True
    t.start()
    active_threads[source] = t
    return {"message": "Đang xử lý stream", "url": source, "camera_id": str(cam_id)}

@app.get("/stop-stream")
def stop_stream(url: str = Query(...)):
    source_key = "0" if url == "local" else url
    stop_detecting(source_key)
    active_threads.pop(source_key, None)
    return {"message": f"Đã dừng stream {url}"}


@app.get("/camera-files")
def camera_files(camera_id: str):
    query = {"camera_id": ObjectId(camera_id)}
    events = event_col.find(query)
    return {"videos": [event.get("video_path", "").replace("\\", "/") for event in events]}

@app.delete("/camera-files")
def delete_camera_file(camera_id: str = Query(...), video_path: str = Query(...)):
    res = event_col.delete_many({"camera_id": ObjectId(camera_id), "video_path": video_path})
    fs_path = Path(video_path)
    if fs_path.exists():
        fs_path.unlink()
    return {"deletedCount": res.deleted_count}

@app.delete("/delete-camera")
def delete_camera(url: str = Body(..., embed=True)):
    result = camera_col.delete_one({"url": url})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Camera not found")
    return {"status": "deleted", "url": url}

@app.post("/test-video")
async def upload_stream(file: UploadFile = File(...)):
    try:
        video_path = os.path.join("data/test-video", file.filename)
        with open(video_path, "wb") as f:
            content = await file.read()
            f.write(content)

        Thread(target=process_and_detect, args=(video_path,)).start()
        return {"status": "started", "file": video_path}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/test-video-stream")
def test_video_stream():
    def generate():
        while True:
            with buffer_lock:
                frame = frame_buffer.get("live")
            if frame is None:
                print("[DEBUG] No frame available in buffer")
                time.sleep(0.05)
                continue

            success, jpeg = cv2.imencode('.jpg', frame)
            if not success:
                print("[ERROR] Failed to encode frame")
                continue

            print("[DEBUG] Yielding frame")
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")

detector = Detector()

@app.websocket("/ws/video")
async def websocket_video(websocket: WebSocket):
    await websocket.accept()
    import asyncio, time

    last_detect_time = 0

    try:
        while True:
            data = await websocket.receive_bytes()
            frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)

            # Always update the latest frame for streaming
            with detector.lock:
                detector.latest_raw_frame = frame.copy()

            # Run detection in the background if enough time has passed
            now = time.time()
            if now - last_detect_time >= 1:
                Thread(target=detector.detect_on_frame, args=(frame.copy(),)).start()
                last_detect_time = now

            # Always send the latest annotated frame (may be slightly behind)
            annotated = detector.get_latest_annotated_frame()
            if annotated is None:
                annotated = frame

            _, jpeg = cv2.imencode(".jpg", annotated)
            await websocket.send_bytes(jpeg.tobytes())

            await asyncio.sleep(1 / 30)  # ~30 FPS

    except WebSocketDisconnect:
        print("[INFO] WebSocket disconnected")
    finally:
        detector.cleanup()

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