from utils.logger import log_event

DANGEROUS_ANIMALS = {"dog", "cat", "tiger", "bear", "lion", "elephant"}
WEAPONS = {"knife", "gun", "pistol"}

def check_dangerous_animal(results, source_id="unknown", video_path=""):
    for r in results:
        for box in r.boxes:
            label = r.names[int(box.cls)]
            conf = float(box.conf)
            if label in DANGEROUS_ANIMALS:
                log_event("dangerous_animal", conf, source_id, video_path)

def check_weapon(results, source_id="unknown", video_path=""):
    for r in results:
        for box in r.boxes:
            label = r.names[int(box.cls)]
            conf = float(box.conf)
            if label in WEAPONS:
                log_event("weapon_detected", conf, source_id, video_path)
