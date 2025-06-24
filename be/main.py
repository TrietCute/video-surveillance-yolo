from fastapi import FastAPI, Query, Body
from object_detection import detect
from utils.logger import setup_logger, save_camera
from pymongo import MongoClient
from config import MONGO_URI, DB_NAME, COLLECTION_CAMERAS, COLLECTION_EVENTS
from threading import Thread
import threading
from datetime import datetime
import os
from fastapi import HTTPException

active_threads = {}  # Global dict để quản lý các stream đang chạy

# FastAPI App
app = FastAPI()
logger = setup_logger("main")

# Mongo
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
camera_col = db[COLLECTION_CAMERAS]
event_col = db[COLLECTION_EVENTS]


@app.get("/")
def root():
    return {"status": "API is running"}


@app.post("/add-camera")
def add_camera(url: str = Body(..., embed=True)):
    if url == "local":
        url = "0"  # để đồng bộ với log_event
    cam_id = save_camera(url)
    logger.info(f"📷 Thêm camera: {url}")
    return {"status": "added", "url": url, "id": str(cam_id)}


@app.get("/cameras")
def list_cameras():
    cams = list(camera_col.find({}, {"url": 1}))
    return [{"id": str(c["_id"]), "url": c["url"]} for c in cams]


@app.get("/start-stream")
def start_stream(url: str = Query(...)):
    if url == "local":
        source = 0  # webcam laptop
    else:
        source = url
    cam_id = save_camera(source)
    logger.info(f"▶️ Bắt đầu stream: {source}")

    # Nếu đã chạy, không chạy lại
    if url in active_threads:
        return {"message": "Stream đã chạy", "camera_id": str(cam_id)}

    t = threading.Thread(target=detect, args=(source,))
    t.daemon = True
    t.start()
    active_threads[source] = t
    return {"message": "Đang xử lý stream", "url": source, "camera_id": str(cam_id)}


@app.get("/stop-stream")
def stop_stream(url: str = Query(...)):
    from object_detection import stop_detecting

    source_key = "0" if url == "local" else url
    stop_detecting(source_key)

    active_threads.pop(source_key, None)
    return {"message": f"Đã dừng stream {url}"}



@app.get("/camera-files")
def camera_files(camera_id: str, date: str, hour: int):
    from config import IMAGE_OUTPUT_DIR, VIDEO_OUTPUT_DIR

    base_paths = [(IMAGE_OUTPUT_DIR, "snapshots"), (VIDEO_OUTPUT_DIR, "videos")]
    result = {"snapshots": [], "videos": []}

    for folder, key in base_paths:
        path = os.path.join(folder, date, f"{hour:02d}")
        if os.path.exists(path):
            files = os.listdir(path)
            result[key] = [f"/{path}/{f}" for f in files]
    return result


@app.delete("/delete-camera")
def delete_camera(url: str = Body(..., embed=True)):
    result = camera_col.delete_one({"url": url})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Camera not found")
    return {"status": "deleted", "url": url}
