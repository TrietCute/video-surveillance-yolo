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
from collections import deque
from urllib.parse import urlparse
from utils.logger import log_event

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
    video_path = ""
    FPS = 25
    BUFFER_SECONDS = 10
    buffer_frames = deque(maxlen=BUFFER_SECONDS * FPS)

    is_recording = False
    abnormal_last_time = 0
    start_time = None
    folder_path = ""
    frame_count = 0

    def save_clip():
        nonlocal out_clean, out_annotated, video_path, folder_path, frame_count
        if not folder_path or not video_path:
            print("[ERROR] ❌ Không có đường dẫn để lưu clip.")
            return False

        success = True
        
        # Đóng các VideoWriter an toàn
        try:
            if out_clean:
                out_clean.release()
                out_clean = None
                print(f"[INFO] 🎞 Đã đóng writer cho clean video")
        except Exception as e:
            print(f"[ERROR] Lỗi khi đóng clean video writer: {e}")
            success = False

        try:
            if out_annotated:
                out_annotated.release()
                out_annotated = None
                print(f"[INFO] 🎞 Đã đóng writer cho annotated video")
        except Exception as e:
            print(f"[ERROR] Lỗi khi đóng annotated video writer: {e}")
            success = False

        # Chờ một chút để đảm bảo file được flush
        time.sleep(0.5)

        # Kiểm tra file đã được tạo và có kích thước hợp lý
        clean_path = os.path.join(folder_path, "abnormal_clean.mp4")
        annotated_path = os.path.join(folder_path, "abnormal_annotated.mp4")
        
        files_status = []
        for file_path, file_type in [(clean_path, "clean"), (annotated_path, "annotated")]:
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                if file_size > 0:
                    files_status.append(f"✅ {file_type}: {file_size} bytes")
                    print(f"[INFO] ✅ File {file_type} đã lưu thành công: {file_path} ({file_size} bytes)")
                else:
                    files_status.append(f"❌ {file_type}: file trống")
                    print(f"[WARNING] ⚠️ File {file_type} trống: {file_path}")
                    success = False
            else:
                files_status.append(f"❌ {file_type}: không tồn tại")
                print(f"[ERROR] ❌ Không tìm thấy file {file_type}: {file_path}")
                success = False

        print(f"[INFO] 📊 Tổng số frame đã ghi: {frame_count}")
        print(f"[INFO] 📁 Trạng thái files: {' | '.join(files_status)}")
        
        if success:
            print(f"[INFO] 🎞 Clip lưu thành công tại: {video_path}")
        else:
            print(f"[ERROR] ❌ Một số file không được lưu đúng cách")
            
        return success

    def stop_recording(reason: str):
        nonlocal is_recording, abnormal_last_time, start_time, video_path, folder_path, frame_count
        if is_recording:
            print(f"[DEBUG] 🛑 Dừng ghi video ({reason}): {video_path}")
            print(f"[DEBUG] 📊 Tổng frame đã ghi trước khi dừng: {frame_count}")
            
            save_success = save_clip()
            is_recording = False
            
            # Chỉ log event nếu lưu thành công
            if save_success and os.path.exists(video_path):
                try:
                    log_event("abnormal_end", 1.0, cam_id, video_path=video_path)
                    print(f"[INFO] ✅ Đã log sự kiện kết thúc cho: {video_path}")
                except Exception as e:
                    print(f"[ERROR] Lỗi khi log event: {e}")
            else:
                print("[ERROR] ❌ Không thể log sự kiện vì file video không được lưu thành công.")
            
            # Reset counters
            frame_count = 0

    # Khởi tạo biến trạng thái
    is_recording = False
    abnormal_last_time = 0
    start_time = None
    video_path = ""
    folder_path = ""
    frame_count = 0

    # Metadata camera
    try:
        camera_obj_id = ObjectId(cam_id)
        camera_doc = camera_col.find_one({"_id": camera_obj_id})
        if not camera_doc:
            raise ValueError(f"Không tìm thấy camera với ID: {cam_id}")

        url = camera_doc.get("url", "")
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname or "unknown_host"
        port = parsed_url.port or ""
        camera_name = f"camera_{hostname.replace('.', '_')}_{port}".strip("_")

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

    print(f"[INFO] 🎥 Bắt đầu video recorder cho camera: {camera_name} trong phòng: {room_name}")

    while detector.running:
        try:
            frame_info = frame_queue.get(timeout=1)
            raw_frame = frame_info["frame"]
            timestamp = frame_info["timestamp"]

            if raw_frame is None or raw_frame.size == 0:
                print("[WARNING] ⚠️ Frame rỗng, bỏ qua")
                continue

            annotated = detector.get_latest_annotated_frame()
            if annotated is None:
                annotated = raw_frame.copy()

            # Thêm frame vào buffer
            buffer_frames.append({
                "raw": raw_frame.copy(),
                "annotated": annotated.copy()
            })

            if detector.is_abnormal:
                abnormal_last_time = time.time()

                if not is_recording:
                    is_recording = True
                    start_time = timestamp
                    frame_count = 0

                    # Tạo đường dẫn thư mục
                    date_str = time.strftime("%Y-%m-%d", time.localtime(timestamp))
                    time_str = time.strftime("%H-%M-%S", time.localtime(timestamp))
                    folder_path = os.path.join(VIDEO_OUTPUT_DIR, room_name, camera_name, date_str, time_str)
                    
                    try:
                        os.makedirs(folder_path, exist_ok=True)
                        print(f"[INFO] 📁 Tạo thư mục thành công: {folder_path}")
                    except Exception as e:
                        print(f"[ERROR] Không thể tạo thư mục: {folder_path}, lỗi: {e}")
                        continue

                    # Thiết lập đường dẫn file
                    path_clean = os.path.join(folder_path, "abnormal_clean.mp4").replace("\\", "/")
                    path_annotated = os.path.join(folder_path, "abnormal_annotated.mp4").replace("\\", "/")
                    video_path = path_clean

                    # Khởi tạo VideoWriter
                    h, w = raw_frame.shape[:2]
                    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                    
                    try:
                        out_clean = cv2.VideoWriter(path_clean, fourcc, FPS, (w, h))
                        out_annotated = cv2.VideoWriter(path_annotated, fourcc, FPS, (w, h))
                        
                        # Kiểm tra xem VideoWriter có được khởi tạo thành công không
                        if not out_clean.isOpened():
                            print(f"[ERROR] ❌ Không thể khởi tạo VideoWriter cho: {path_clean}")
                            continue
                        if not out_annotated.isOpened():
                            print(f"[ERROR] ❌ Không thể khởi tạo VideoWriter cho: {path_annotated}")
                            continue
                            
                        print(f"[DEBUG] 🎥 Bắt đầu ghi abnormal: {path_clean}")
                        print(f"[DEBUG] 📂 Bắt đầu ghi vào thư mục: {folder_path}")
                        
                        # Log sự kiện bắt đầu
                        try:
                            log_event("abnormal_start", 1.0, cam_id, video_path=video_path)
                        except Exception as e:
                            print(f"[ERROR] Lỗi khi log event start: {e}")

                        # Ghi buffer frames
                        for bf in buffer_frames:
                            try:
                                out_clean.write(bf["raw"])
                                out_annotated.write(bf["annotated"])
                                frame_count += 1
                            except Exception as e:
                                print(f"[ERROR] Lỗi khi ghi buffer frame: {e}")
                                
                    except Exception as e:
                        print(f"[ERROR] Lỗi khi khởi tạo VideoWriter: {e}")
                        continue

                # Ghi frame hiện tại
                if is_recording and out_clean and out_annotated:
                    try:
                        out_clean.write(raw_frame)
                        out_annotated.write(annotated)
                        frame_count += 1
                        
                        # Log tiến trình mỗi 100 frame
                        if frame_count % 100 == 0:
                            print(f"[DEBUG] 📊 Đã ghi {frame_count} frames")
                            
                    except Exception as e:
                        print(f"[ERROR] Lỗi khi ghi frame: {e}")

            elif is_recording:
                # Kiểm tra xem có nên dừng ghi không
                if time.time() - abnormal_last_time >= 3:
                    stop_recording("3s không còn bất thường")

        except queue.Empty:
            # Mất kết nối khi đang ghi
            if is_recording and (time.time() - abnormal_last_time >= 3):
                stop_recording("mất kết nối khi đang ghi")
            continue
        except Exception as e:
            print(f"[ERROR] Lỗi trong video recorder loop: {e}")
            if is_recording:
                stop_recording("lỗi trong quá trình ghi")
            continue

    # Cleanup khi thoát
    if is_recording:
        stop_recording("kết thúc chương trình")
    
    print(f"[INFO] 🏁 Video recorder cho camera {cam_id} đã kết thúc")

@app.websocket("/ws/video")
async def websocket_video(websocket: WebSocket, cam_id: str = Query(...)):
    await websocket.accept()
    print(f"[INFO] 🔌 WebSocket connected for camera: {cam_id}")

    detector = Detector(cam_id)
    frame_queue = queue.Queue(maxsize=300)

    DETECTOR_MAP[cam_id] = detector
    FRAME_QUEUES[cam_id] = frame_queue

    recorder_thread = Thread(target=video_recorder, args=(cam_id, frame_queue, detector), daemon=True)
    recorder_thread.start()
    RECORDER_THREADS[cam_id] = recorder_thread

    async def receive_loop():
        try:
            while detector.running:
                data = await websocket.receive_bytes()
                frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
                if frame is not None:
                    timestamp = time.time()
                    
                    # Cập nhật frame cho detector
                    with detector.lock:
                        detector.latest_raw_frame = frame.copy()
                    
                    # Đưa frame vào queue cho recorder
                    try:
                        frame_queue.put_nowait({
                            "frame": frame.copy(),
                            "timestamp": timestamp
                        })
                    except queue.Full:
                        # Nếu queue đầy, bỏ qua frame cũ nhất
                        try:
                            frame_queue.get_nowait()
                            frame_queue.put_nowait({
                                "frame": frame.copy(),
                                "timestamp": timestamp
                            })
                        except queue.Empty:
                            pass
                    
                    # Log định kỳ để debug
                    if hasattr(receive_loop, 'frame_count'):
                        receive_loop.frame_count += 1
                    else:
                        receive_loop.frame_count = 1
                    
                    if receive_loop.frame_count % 100 == 0:
                        print(f"[DEBUG] 📊 Đã nhận {receive_loop.frame_count} frames từ client")
                        
        except WebSocketDisconnect:
            print(f"[INFO] 📱 Client disconnected: {cam_id}")
        except Exception as e:
            print(f"[ERROR] receive_loop: {e}")
        finally:
            detector.running = False
            print(f"[INFO] 🛑 Receive loop stopped for {cam_id}")

    async def detect_loop():
        try:
            detect_count = 0
            while detector.running:
                with detector.lock:
                    frame = detector.latest_raw_frame.copy() if detector.latest_raw_frame is not None else None
                    
                if frame is not None:
                    # Chạy detection trong thread riêng
                    Thread(target=detector.detect_on_frame, args=(frame,), daemon=True).start()
                    detect_count += 1
                    
                    if detect_count % 10 == 0:
                        print(f"[DEBUG] 🔍 Đã chạy {detect_count} lần detection. Abnormal: {detector.is_abnormal}")
                        
                await asyncio.sleep(detector.DETECT_INTERVAL)
        except Exception as e:
            print(f"[ERROR] detect_loop: {e}")
        finally:
            detector.running = False
            print(f"[INFO] 🛑 Detect loop stopped for {cam_id}")

    async def stream_loop():
        try:
            stream_count = 0
            while detector.running:
                with detector.lock:
                    frame = detector.latest_raw_frame.copy() if detector.latest_raw_frame is not None else None
                    
                if frame is not None:
                    annotated = detector.get_latest_annotated_frame()
                    if annotated is None:
                        annotated = frame
                        
                    _, jpeg = cv2.imencode(".jpg", annotated)
                    await websocket.send_bytes(jpeg.tobytes())
                    stream_count += 1
                    
                    if stream_count % 100 == 0:
                        print(f"[DEBUG] 📺 Đã stream {stream_count} frames")
                        
                await asyncio.sleep(1 / 30)
        except WebSocketDisconnect:
            print(f"[INFO] 📱 Client disconnected during streaming: {cam_id}")
        except Exception as e:
            print(f"[ERROR] stream_loop: {e}")
        finally:
            detector.running = False
            print(f"[INFO] 🛑 Stream loop stopped for {cam_id}")

    try:
        print(f"[INFO] 🚀 Starting WebSocket loops for {cam_id}")
        await asyncio.gather(
            receive_loop(),
            detect_loop(),
            stream_loop()
        )
    except Exception as e:
        print(f"[ERROR] WebSocket error for {cam_id}: {e}")
    finally:
        print(f"[INFO] 🧹 Cleaning up WebSocket: {cam_id}")
        detector.cleanup()
        detector.running = False
        
        # Đợi recorder thread kết thúc
        if recorder_thread.is_alive():
            print(f"[INFO] ⏳ Waiting for recorder thread to finish...")
            recorder_thread.join(timeout=5)
            if recorder_thread.is_alive():
                print(f"[WARNING] ⚠️ Recorder thread didn't finish in time")
        
        # Cleanup resources
        DETECTOR_MAP.pop(cam_id, None)
        FRAME_QUEUES.pop(cam_id, None)
        RECORDER_THREADS.pop(cam_id, None)
        
        print(f"[INFO] ✅ Resources for {cam_id} cleaned up.")


def video_recorder(cam_id: str, frame_queue: queue.Queue, detector: Detector):
    """Improved video recorder with better error handling and logging"""
    out_clean = out_annotated = None
    video_path = ""
    FPS = 25
    BUFFER_SECONDS = 10
    buffer_frames = deque(maxlen=BUFFER_SECONDS * FPS)

    is_recording = False
    abnormal_last_time = 0
    start_time = None
    folder_path = ""
    frame_count = 0
    total_frames_received = 0

    def save_clip():
        nonlocal out_clean, out_annotated, video_path, folder_path, frame_count
        if not folder_path or not video_path:
            print(f"[ERROR] ❌ Không có đường dẫn để lưu clip. folder_path: {folder_path}, video_path: {video_path}")
            return False

        success = True
        
        print(f"[INFO] 💾 Đang lưu clip với {frame_count} frames...")
        
        # Đóng các VideoWriter an toàn
        try:
            if out_clean:
                out_clean.release()
                out_clean = None
                print(f"[INFO] 🎞 Đã đóng writer cho clean video")
        except Exception as e:
            print(f"[ERROR] Lỗi khi đóng clean video writer: {e}")
            success = False

        try:
            if out_annotated:
                out_annotated.release()
                out_annotated = None
                print(f"[INFO] 🎞 Đã đóng writer cho annotated video")
        except Exception as e:
            print(f"[ERROR] Lỗi khi đóng annotated video writer: {e}")
            success = False

        # Chờ một chút để đảm bảo file được flush
        time.sleep(0.5)

        # Kiểm tra file đã được tạo và có kích thước hợp lý
        clean_path = os.path.join(folder_path, "abnormal_clean.mp4")
        annotated_path = os.path.join(folder_path, "abnormal_annotated.mp4")
        
        files_status = []
        for file_path, file_type in [(clean_path, "clean"), (annotated_path, "annotated")]:
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                if file_size > 0:
                    files_status.append(f"✅ {file_type}: {file_size} bytes")
                    print(f"[INFO] ✅ File {file_type} đã lưu thành công: {file_path} ({file_size} bytes)")
                else:
                    files_status.append(f"❌ {file_type}: file trống")
                    print(f"[WARNING] ⚠️ File {file_type} trống: {file_path}")
                    success = False
            else:
                files_status.append(f"❌ {file_type}: không tồn tại")
                print(f"[ERROR] ❌ Không tìm thấy file {file_type}: {file_path}")
                success = False

        print(f"[INFO] 📊 Tổng số frame đã ghi: {frame_count}")
        print(f"[INFO] 📁 Trạng thái files: {' | '.join(files_status)}")
        print(f"[INFO] 🎞 Clip lưu tại: {video_path}")
        
        if success:
            print(f"[INFO] ✅ Clip lưu thành công tại: {video_path}")
        else:
            print(f"[ERROR] ❌ Một số file không được lưu đúng cách")
            
        return success

    def stop_recording(reason: str):
        nonlocal is_recording, abnormal_last_time, start_time, video_path, folder_path, frame_count
        if is_recording:
            print(f"[DEBUG] 🛑 Dừng ghi video ({reason}): {video_path}")
            print(f"[DEBUG] 📊 Tổng frame đã ghi trước khi dừng: {frame_count}")
            
            save_success = save_clip()
            is_recording = False
            
            # Chỉ log event nếu lưu thành công
            if save_success and os.path.exists(video_path):
                try:
                    log_event("abnormal_end", 1.0, cam_id, video_path=video_path)
                    print(f"[INFO] ✅ Đã log sự kiện kết thúc cho: {video_path}")
                except Exception as e:
                    print(f"[ERROR] Lỗi khi log event: {e}")
            else:
                print("[ERROR] ❌ Không thể log sự kiện vì file video không được lưu thành công.")
            
            # Reset counters
            frame_count = 0

    # Khởi tạo metadata camera
    try:
        camera_obj_id = ObjectId(cam_id)
        camera_doc = camera_col.find_one({"_id": camera_obj_id})
        if not camera_doc:
            raise ValueError(f"Không tìm thấy camera với ID: {cam_id}")

        url = camera_doc.get("url", "")
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname or "unknown_host"
        port = parsed_url.port or ""
        camera_name = f"camera_{hostname.replace('.', '_')}_{port}".strip("_")

        room_name = "unknown_room"
        room_id = camera_doc.get("room_id")
        if room_id:
            room_doc = room_col.find_one({"_id": room_id})
            if room_doc:
                room_name = room_doc.get("name", "unknown_room").replace(" ", "_")

        print(f"[INFO] 🎥 Video recorder metadata - Camera: {camera_name}, Room: {room_name}")

    except Exception as e:
        print(f"[ERROR] Lỗi lấy metadata camera: {e}")
        camera_name = f"camera_{cam_id[:6]}"
        room_name = "unknown_room"

    print(f"[INFO] 🎥 Bắt đầu video recorder cho camera: {camera_name} trong phòng: {room_name}")

    # Main recording loop
    while detector.running:
        try:
            frame_info = frame_queue.get(timeout=1)
            raw_frame = frame_info["frame"]
            timestamp = frame_info["timestamp"]
            total_frames_received += 1

            if raw_frame is None or raw_frame.size == 0:
                print("[WARNING] ⚠️ Frame rỗng, bỏ qua")
                continue

            # Log định kỳ để debug
            if total_frames_received % 500 == 0:
                print(f"[DEBUG] 📊 Recorder đã nhận {total_frames_received} frames, đang ghi: {is_recording}")

            annotated = detector.get_latest_annotated_frame()
            if annotated is None:
                annotated = raw_frame.copy()

            # Thêm frame vào buffer
            buffer_frames.append({
                "raw": raw_frame.copy(),
                "annotated": annotated.copy()
            })

            # Kiểm tra trạng thái abnormal
            if detector.is_abnormal:
                abnormal_last_time = time.time()

                if not is_recording:
                    print(f"[INFO] 🚨 Bắt đầu ghi video do phát hiện bất thường")
                    is_recording = True
                    start_time = timestamp
                    frame_count = 0

                    # Tạo đường dẫn thư mục
                    date_str = time.strftime("%Y-%m-%d", time.localtime(timestamp))
                    time_str = time.strftime("%H-%M-%S", time.localtime(timestamp))
                    folder_path = os.path.join(VIDEO_OUTPUT_DIR, room_name, camera_name, date_str, time_str)
                    
                    try:
                        os.makedirs(folder_path, exist_ok=True)
                        print(f"[INFO] 📁 Tạo thư mục thành công: {folder_path}")
                    except Exception as e:
                        print(f"[ERROR] Không thể tạo thư mục: {folder_path}, lỗi: {e}")
                        continue

                    # Thiết lập đường dẫn file
                    path_clean = os.path.join(folder_path, "abnormal_clean.mp4").replace("\\", "/")
                    path_annotated = os.path.join(folder_path, "abnormal_annotated.mp4").replace("\\", "/")
                    video_path = path_clean

                    print(f"[INFO] 📂 Video paths:")
                    print(f"  Clean: {path_clean}")
                    print(f"  Annotated: {path_annotated}")

                    # Khởi tạo VideoWriter
                    h, w = raw_frame.shape[:2]
                    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                    
                    try:
                        out_clean = cv2.VideoWriter(path_clean, fourcc, FPS, (w, h))
                        out_annotated = cv2.VideoWriter(path_annotated, fourcc, FPS, (w, h))
                        
                        # Kiểm tra xem VideoWriter có được khởi tạo thành công không
                        if not out_clean.isOpened():
                            print(f"[ERROR] ❌ Không thể khởi tạo VideoWriter cho: {path_clean}")
                            continue
                        if not out_annotated.isOpened():
                            print(f"[ERROR] ❌ Không thể khởi tạo VideoWriter cho: {path_annotated}")
                            continue
                            
                        print(f"[INFO] 🎥 VideoWriter khởi tạo thành công cho {w}x{h} @ {FPS}fps")
                        
                        # Log sự kiện bắt đầu
                        try:
                            log_event("abnormal_start", 1.0, cam_id, video_path=video_path)
                        except Exception as e:
                            print(f"[ERROR] Lỗi khi log event start: {e}")

                        # Ghi buffer frames
                        buffer_count = 0
                        for bf in buffer_frames:
                            try:
                                out_clean.write(bf["raw"])
                                out_annotated.write(bf["annotated"])
                                buffer_count += 1
                                frame_count += 1
                            except Exception as e:
                                print(f"[ERROR] Lỗi khi ghi buffer frame: {e}")
                        
                        print(f"[INFO] 📼 Đã ghi {buffer_count} frames từ buffer")
                                
                    except Exception as e:
                        print(f"[ERROR] Lỗi khi khởi tạo VideoWriter: {e}")
                        continue

                # Ghi frame hiện tại
                if is_recording and out_clean and out_annotated:
                    try:
                        out_clean.write(raw_frame)
                        out_annotated.write(annotated)
                        frame_count += 1
                        
                        # Log tiến trình mỗi 100 frame
                        if frame_count % 100 == 0:
                            print(f"[DEBUG] 📊 Đã ghi {frame_count} frames")
                            
                    except Exception as e:
                        print(f"[ERROR] Lỗi khi ghi frame: {e}")

            elif is_recording:
                # Kiểm tra xem có nên dừng ghi không
                if time.time() - abnormal_last_time >= 3:
                    stop_recording("3s không còn bất thường")

        except queue.Empty:
            # Timeout - kiểm tra xem có nên dừng ghi không
            if is_recording and abnormal_last_time > 0 and (time.time() - abnormal_last_time >= 3):
                stop_recording("timeout - mất kết nối")
            continue
        except Exception as e:
            print(f"[ERROR] Lỗi trong video recorder loop: {e}")
            if is_recording:
                stop_recording("lỗi trong quá trình ghi")
            continue

    # Cleanup khi thoát
    if is_recording:
        stop_recording("kết thúc chương trình")
    
    print(f"[INFO] 🏁 Video recorder cho camera {cam_id} đã kết thúc. Tổng frames nhận: {total_frames_received}")