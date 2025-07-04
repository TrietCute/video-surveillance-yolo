#config.py
MONGO_URI = "mongodb+srv://Tris:Ttn2911%40@cluster0.etkomsx.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
DB_NAME = "surveillance"
COLLECTION_EVENTS = "events"
COLLECTION_CAMERAS = "cameras"
COLLECTION_ROOMS = "rooms"

# Video clip ghi lại khi có đối tượng
ABNORMAL_END_DELAY = 3  # giây chờ trước khi kết thúc video nếu không còn bất thường

VIDEO_OUTPUT_DIR = "data/output"
VIDEO_CLIP_DURATION = 10  # seconds
FPS = 5  # khi ở chế độ liên tục
dangerous_animals = ["dog", "cat", "snake", "lion", "cow"]
POSE_SUSPICIOUS_ANGLE_THRESHOLD = 45 
POSE_KEYPOINTS_PERSON = ["nose", "left_shoulder", "right_shoulder", "left_hip", "right_hip"]

