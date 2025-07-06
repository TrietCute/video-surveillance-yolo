# main.py
from fastapi import FastAPI, Query, Body, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from bson import ObjectId
from pymongo import MongoClient
from threading import Thread
import shutil, uuid, os, sys
from pathlib import Path
from queue import Queue
import cv2
import numpy as np
import time
import asyncio
from datetime import datetime
import os
from config import VIDEO_OUTPUT_DIR, FPS
from object_detection.detector import Detector 
from utils.logger import setup_logger, save_camera, log_event


from config import MONGO_URI, DB_NAME, COLLECTION_CAMERAS, COLLECTION_EVENTS

print("🔥 Python path:", sys.executable)

os.makedirs(VIDEO_OUTPUT_DIR, exist_ok=True)

app = FastAPI()
logger = setup_logger("main")

# MongoDB
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
camera_col = db[COLLECTION_CAMERAS]
event_col = db[COLLECTION_EVENTS]

# Directory
TEST_VIDEO_DIR = "data/test-video"
os.makedirs(TEST_VIDEO_DIR, exist_ok=True)

# Stream management
active_threads = {}

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

# Global maps
DETECTOR_MAP = {}
WRITER_MAP = {}
VIDEO_OUTPUT_DIR = "data/output"
FPS = 30

def record_abnormal_video(cam_id: str):
    detector = DETECTOR_MAP[cam_id]
    out_clean = out_annotated = None
    path_clean = path_annotated = None

    while True:
        frame_info = detector.frame_queue.get()
        frame = frame_info["frame"]
        annotated = frame_info["annotated"]
        timestamp = frame_info["timestamp"]

        if detector.should_record:
            if out_clean is None or out_annotated is None:
                # Start new recording
                ts = time.strftime("%Y-%m-%d/%H-%M-%S", time.localtime(timestamp))
                folder = os.path.join(VIDEO_OUTPUT_DIR, cam_id, ts)
                os.makedirs(folder, exist_ok=True)

                h, w = frame.shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                path_clean = os.path.join(folder, "abnormal_clean.mp4")
                path_annotated = os.path.join(folder, "abnormal_annotated.mp4")

                out_clean = cv2.VideoWriter(path_clean, fourcc, FPS, (w, h))
                out_annotated = cv2.VideoWriter(path_annotated, fourcc, FPS, (w, h))
                log_event("abnormal_start", 1.0, cam_id, video_path=path_clean)

            out_clean.write(frame)
            out_annotated.write(annotated)

        elif out_clean is not None:
            # Stop recording
            out_clean.release()
            out_annotated.release()
            log_event("abnormal_end", 1.0, cam_id, video_path=path_clean)
            out_clean = out_annotated = None
            path_clean = path_annotated = None
            
@app.websocket("/ws/video")
async def websocket_video(websocket: WebSocket, cam_id: str = Query(...)):
    await websocket.accept()

    if cam_id not in DETECTOR_MAP:
        detector = Detector(cam_id)
        DETECTOR_MAP[cam_id] = detector
        Thread(target=record_abnormal_video, args=(cam_id,), daemon=True).start()
    else:
        detector = DETECTOR_MAP[cam_id]

    async def receive_loop():
        try:
            while detector.running:
                data = await websocket.receive_bytes()
                frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
                if frame is not None:
                    with detector.lock:
                        detector.latest_raw_frame = frame.copy()
        except Exception as e:
            print(f"[ERROR] receive_loop: {e}")
        finally:
            detector.running = False  # <== Cờ dừng

    async def detect_loop():
        try:
            while detector.running:
                with detector.lock:
                    frame = detector.latest_raw_frame.copy() if detector.latest_raw_frame is not None else None
                if frame is not None:
                    Thread(target=detector.detect_on_frame, args=(frame,), daemon=True).start()
                await asyncio.sleep(detector.DETECT_INTERVAL)
        except Exception as e:
            print(f"[ERROR] detect_loop: {e}")
        finally:
            detector.running = False  # <== Cờ dừng

    async def stream_loop():
        try:
            while detector.running:
                with detector.lock:
                    frame = detector.latest_raw_frame.copy() if detector.latest_raw_frame is not None else None
                if frame is not None:
                    annotated = detector.get_latest_annotated_frame()
                    if annotated is None:
                        annotated = frame
                    _, jpeg = cv2.imencode(".jpg", annotated)
                    await websocket.send_bytes(jpeg.tobytes())
                await asyncio.sleep(1 / 30)
        except Exception as e:
            print(f"[ERROR] stream_loop: {e}")
        finally:
            detector.running = False  # <== Cờ dừng

    try:
        await asyncio.gather(
            receive_loop(),
            detect_loop(),
            stream_loop()
        )
    finally:
        print(f"[INFO] Cleaning up WebSocket: {cam_id}")
        detector.force_stop_recording()
        detector.cleanup()
        detector.running = False  # đảm bảo đã dừng