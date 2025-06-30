# pose_analyzer.py
import numpy as np
from utils.logger import log_event

def is_person_lying_down(keypoints):
    """
    Xác định người nằm nếu vai trái-phải và hông trái-phải gần nhau theo trục y
    """
    if keypoints.shape[0] < 6:
        return False

    left_shoulder = keypoints[5]
    right_shoulder = keypoints[6]
    left_hip = keypoints[11]
    right_hip = keypoints[12]

    avg_shoulder_y = (left_shoulder[1] + right_shoulder[1]) / 2
    avg_hip_y = (left_hip[1] + right_hip[1]) / 2

    vertical_diff = abs(avg_shoulder_y - avg_hip_y)
    return vertical_diff < 30  # tùy chỉnh ngưỡng này

def analyze_pose(results, frame, source_id="unknown"):
    for r in results:
        if hasattr(r, "keypoints") and r.keypoints is not None:
            for kp in r.keypoints.xy:
                keypoints = kp.cpu().numpy()
                if is_person_lying_down(keypoints):
                    log_event("person_lie_down", 1.0, source_id)
