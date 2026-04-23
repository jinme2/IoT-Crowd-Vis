import cv2
import imutils
import time
import numpy as np
import requests
import threading
from picamera2 import Picamera2
from ultralytics import YOLO
from gpiozero import LED # 개별 LED 제어용

# --- CONFIGURATION ---
# Network settings
SERVER_URL = "https://iot11-backend.onrender.com/upload"
CAMERA_ID = 1
ROOM_NAME = "tdmspace"
POST_INTERVAL = 300.0 # 5분
last_post_time = 0
last_sent_count = -1

# --- LED & CROWD SETTINGS ---
# GPIO 핀 번호 (BCM 모드 기준)
PIN_RED = 17
PIN_YELLOW = 22
PIN_GREEN = 27

# LED 초기화
try:
    led_red = LED(PIN_RED)
    led_yellow = LED(PIN_YELLOW)
    led_green = LED(PIN_GREEN)
    
    # 시작 시 LED 테스트 (순차 점등)
    print("[LED TEST] Red")
    led_red.on()
    time.sleep(0.5)
    led_red.off()
    
    print("[LED TEST] Yellow")
    led_yellow.on()
    time.sleep(0.5)
    led_yellow.off()
    
    print("[LED TEST] Green")
    led_green.on()
    time.sleep(0.5)
    led_green.off()
    
except Exception as e:
    print(f"[LED WARNING] Failed to initialize LEDs: {e}")
    led_red = None
    led_yellow = None
    led_green = None

# 혼잡도 기준 
MAX_CAPACITY = 32.0
RATIO_WARNING = 0.5     # 50% (15명)
RATIO_CRITICAL = 0.7    # 70% (21명)

# --- DETECTION & TRACKING SETTINGS ---
CONFIDENCE_THRESHOLD = 0.35
NMS_THRESHOLD = 0.7
PERSON_CLASS_ID = 0

TOTAL_CROSSED = 0
ACTIVE_TRACKERS = []
TRACKER_TTL = 15
MIN_TRACKER_SIZE_RATIO = 0.005
FRAME_SKIP_RATE = 10
frame_count = 0
IOU_THRESHOLD = 0.3
MAX_CONSECUTIVE_MISSES = 3

# --- YOLOv8 MODEL INITIALIZATION ---
print("[INFO] Loading YOLOv8 model...")
model = YOLO('yolov8n.pt')

# --- INITIALIZATION ---
print("[INFO] Initializing camera...")
picam2 = Picamera2()
camera_config = picam2.create_video_configuration(main={"size": (640, 480)})
picam2.configure(camera_config)
picam2.start()
time.sleep(2)

print("[INFO] Camera ready. Starting Hybrid tracking...")

# --- Helper Functions ---
def get_iou(boxA, boxB):
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    interArea = max(0, xB - xA) * max(0, yB - yA)
    if interArea == 0: return 0
    boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
    return interArea / float(boxAArea + boxBArea - interArea)

def send_data_to_server(url, count, cam_id, room_name):
    try:
        data = {
            "camera_id": cam_id,
            "room": room_name,
            "people_count": count
        }
        response = requests.post(url, json=data, timeout=10, headers={'Content-Type': 'application/json; charset=utf-8'})
        response_data = response.json()
        print(f"[POST SUCCESS] Sent {count} people. Status: {response_data.get('status')}")
    except Exception as e:
        print(f"[POST FAILED] Error: {e}")

def update_led_status(count):
    if led_red is None: return
    
    try:
        ratio = count / MAX_CAPACITY
        
        # 모든 LED 끄기 (초기화)
        led_red.off()
        led_yellow.off()
        led_green.off()
        
        if ratio >= RATIO_CRITICAL: # 70% 이상 (Red ON)
            led_red.on()
        elif ratio >= RATIO_WARNING: # 50% 이상 (Yellow ON)
            led_yellow.on()
        else: # 50% 미만 (Green ON)
            led_green.on()
            
    except Exception as e:
        print(f"[LED ERROR] Failed to update LED: {e}")

# --- MAIN LOOP ---
start_time = time.time()

try:
    while True:
        current_loop_time = time.time()
        frame = picam2.capture_array()

        if frame.shape[2] == 4: frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        frame = imutils.resize(frame, width=min(416, frame.shape[1]))
        (H, W) = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        trackers_to_remove = []
        if frame_count % FRAME_SKIP_RATE == 0:
            for t in ACTIVE_TRACKERS: t['revalidated'] = False

        # 1. Update Trackers
        for i, tracker_data in enumerate(ACTIVE_TRACKERS):
            tracker = tracker_data['tracker']
            (success, box) = tracker.update(rgb)
            (x, y, w, h) = [int(v) for v in box]
            is_valid = True

            if w * h < (W * H * MIN_TRACKER_SIZE_RATIO) or \
               x < -W * 0.05 or x + w > W * 1.05 or \
               y < -H * 0.05 or y + h > H * 1.05:
                is_valid = False

            if not is_valid or not success:
                tracker_data['ttl'] -= 1
                if tracker_data['ttl'] <= 0: trackers_to_remove.append(i)

            if success and is_valid:
                if tracker_data['ttl'] > 0:
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.putText(frame, f"ID {tracker_data['id']}", (x, y - 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 2)
                    tracker_data['box'] = (x, y, x + w, y + h)

        for i in sorted(trackers_to_remove, reverse=True): del ACTIVE_TRACKERS[i]

        # 2. Run Detection
        if frame_count % FRAME_SKIP_RATE == 0:
            results = model.predict(frame, conf=CONFIDENCE_THRESHOLD, iou=NMS_THRESHOLD,
                                    classes=[PERSON_CLASS_ID], verbose=False, imgsz=320)
            if results and results[0].boxes is not None:
                for box in results[0].boxes:
                    xyxy = box.xyxy[0].cpu().numpy().astype(int)
                    (x1, y1, x2, y2) = xyxy
                    new_box_xywh = (x1, y1, x2 - x1, y2 - y1)
                    is_new = True
                    for tracker_data in ACTIVE_TRACKERS:
                        if get_iou(tracker_data['box'], (x1, y1, x2, y2)) > IOU_THRESHOLD:
                            is_new = False
                            tracker_data['miss_count'] = 0
                            tracker_data['revalidated'] = True
                            break
                    if is_new:
                        new_tracker = cv2.TrackerCSRT_create()
                        new_tracker.init(rgb, new_box_xywh)
                        TOTAL_CROSSED += 1
                        ACTIVE_TRACKERS.append({
                            'tracker': new_tracker, 'box': (x1, y1, x2, y2), 'ttl': TRACKER_TTL,
                            'id': TOTAL_CROSSED, 'revalidated': True, 'miss_count': 0
                        })

            ghosts_to_remove = []
            for i, tracker_data in enumerate(ACTIVE_TRACKERS):
                if not tracker_data['revalidated']:
                    tracker_data['miss_count'] += 1
                    if tracker_data['miss_count'] > MAX_CONSECUTIVE_MISSES:
                        ghosts_to_remove.append(i)
            for i in sorted(ghosts_to_remove, reverse=True): del ACTIVE_TRACKERS[i]

        # 3. Display Info & Update LED
        current_active = len(ACTIVE_TRACKERS)
        
        # --- LED Update ---
        update_led_status(current_active)
        
        ratio_percent = int((current_active / MAX_CAPACITY) * 100)
        # 디버깅용 텍스트 표시 (현재 LED 상태)
        led_text = "RED" if ratio_percent >= 70 else "YELLOW" if ratio_percent >= 50 else "GREEN"
        cv2.putText(frame, f"Active: {current_active} ({ratio_percent}%) - {led_text}", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        
        try:
            fps = (1.0 / (current_loop_time - start_time))
        except ZeroDivisionError: fps = 0
        start_time = current_loop_time
        cv2.putText(frame, f"FPS: {int(fps)}", (W - 100, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        # 4. Send Data (Strict 5-minute interval)
        current_time = time.time()
        if (current_time - last_post_time > POST_INTERVAL):
            post_thread = threading.Thread(target=send_data_to_server,
                                           args=(SERVER_URL, current_active, CAMERA_ID, ROOM_NAME),
                                           daemon=True)
            post_thread.start()
            last_post_time = current_time
            last_sent_count = current_active

        cv2.imshow("YOLOv8-CSRT Tracker", frame)
        frame_count += 1
        if cv2.waitKey(1) & 0xFF == ord('q'): break

except KeyboardInterrupt:
    pass
finally:
    print("[INFO] Shutting down...")
    if led_red:
        led_red.off()
        led_yellow.off()
        led_green.off()
        led_red.close()
        led_yellow.close()
        led_green.close()
    picam2.stop()
    cv2.destroyAllWindows()
