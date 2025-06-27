from fastapi import FastAPI, Query, Body
from object_detection import detect
from utils.logger import setup_logger, save_camera
from bson import ObjectId
from pymongo import MongoClient
from config import MONGO_URI, DB_NAME, COLLECTION_CAMERAS, COLLECTION_EVENTS
import threading
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
        url = "0"
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
def camera_files(camera_id: str):
    query = {"camera_id": ObjectId(camera_id)}
    events = event_col.find(query)

    result = []
    for event in events:
        path = event.get("video_path", "").replace("\\", "/")  # fix path format
        result.append(path)
    return {"videos": result}

@app.delete("/camera-files")
def delete_camera_file(
    camera_id: str = Query(...), 
    video_path: str = Query(...)
):
    # 1. Xoá record trong Mongo
    res = event_col.delete_many({
        "camera_id": ObjectId(camera_id),
        "video_path": video_path
    })
    # 2. Xoá file trên đĩa
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
