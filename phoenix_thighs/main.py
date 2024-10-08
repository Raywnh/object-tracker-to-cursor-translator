import cv2
import image_process as imgr
import mouse_movement as mov
import queue
import threading
import serial
import time
import temporal_smoothing_algo as tmpa
from pynput.keyboard import KeyCode, Listener

arduino = serial.Serial('COM7', 115200)
serial_lock = threading.Lock()

frameQueue = queue.Queue()
resultQueue = queue.Queue()
mouseQueue = queue.Queue()


def key_input():
    def on_press(key):
        if key == KeyCode.from_char('.'):
            with serial_lock:
                arduino.write(b"Keyed\n")
    with Listener(on_press=on_press) as listener:
        listener.join()

def mouse_thread():
    while True:
        pos = mouseQueue.get()
        if pos:
            x, y = pos
            
            coords = "{},{}\n".format(x, y)
            with serial_lock:
                arduino.write(coords.encode())
        
def capture_thread(cap):
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frameQueue.put(frame)

def process_thread():
    while True:
        frame = frameQueue.get()
        frame = cv2.flip(frame, 1)
        
        if frame is None:
            break
        pos, centroid = imgr.detect_colored_object(frame)
        resultQueue.put((pos, centroid, frame))


cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FPS, 60)
# time.sleep(2)
  
smoothCursor = mov.SmoothCursor(window_size=5)
prev_x = None
prev_y = None

sma_filter = tmpa.AverageBoundingBoxTracker(window_size=10, min_movement_threshold=10)

t1 = threading.Thread(target=capture_thread, args=(cap, ), daemon=True)
t2 = threading.Thread(target=process_thread, args=(), daemon=True)
t3 = threading.Thread(target=mouse_thread, args=(), daemon=True)
t4 = threading.Thread(target=key_input, args=(), daemon=True)

t1.start()
t2.start()
t3.start()
t4.start()

while True:
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
    
    if not resultQueue.empty():
        pos, centroid, frame = resultQueue.get()
        
        if pos and centroid:
            x, y, w, h = pos
            centroid_x, centroid_y = centroid
            sma_filter.update(tmpa.BoundingBox(centroid_x, centroid_y, w, h))
            smooth_bbox = sma_filter.get_smoothed_bounding_box()
            
            if smooth_bbox:
                cv2.circle(frame, (smooth_bbox.x, smooth_bbox.y), 50, (0, 255, 0), 1)

                scaled_x = int((smooth_bbox.x / 640) * 1920)
                scaled_y = int((smooth_bbox.y / 480) * 1080)
                
                if not prev_x and not prev_y:
                    prev_x = scaled_x
                    prev_y = scaled_y
                
                move_x = scaled_x - prev_x
                move_y = scaled_y - prev_y
                
                prev_x = scaled_x
                prev_y = scaled_y
                
                mouseQueue.put((move_x, move_y))
                
        cv2.imshow('frame', frame)
        
cap.release()
cv2.destroyAllWindows()

t1.join()
t2.join()
t3.join()
t4.join()