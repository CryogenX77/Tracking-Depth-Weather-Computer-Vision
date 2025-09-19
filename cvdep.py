import cv2
import numpy as np
import mediapipe as mp
import requests
import threading
import time
import math # --- NEW ---

# --- CONFIGURATION CONSTANTS ---
class CONFIG:
    """
    Main configuration class for the application.
    """
    # Webcam & Display
    CAM_INDEX = 0
    FRAME_WIDTH = 1280
    FRAME_HEIGHT = 720
    
    # Performance
    TARGET_FPS = 60

    # Face Detection & Tracking
    FACE_DETECTION_CONFIDENCE = 0.6

    # Depth Estimation
    KNOWN_FACE_HEIGHT_CM = 18.0
    FOCAL_LENGTH = 750

    # --- NEW: TRAJECTORY COMPENSATION ---
    # This value MUST be calibrated to your turret's actual projectile speed in meters/second.
    PROJECTILE_VELOCITY_MPS = 100 # Muzzle velocity in meters per second
    GRAVITY_MPS2 = 9.81           # Acceleration due to gravity

    # Weather API
    OPENWEATHER_API_KEY = "YOUR_API_KEY_HERE"
    WEATHER_CITY = "Gurugram"
    WEATHER_UNITS = "metric"
    WEATHER_UPDATE_INTERVAL_SEC = 600

    # UI & Aesthetics
    class UI:
        FONT = cv2.FONT_HERSHEY_SIMPLEX
        FONT_SCALE_MAIN = 0.6
        FONT_SCALE_INFO = 0.5
        FONT_THICKNESS = 1
        COLOR_PRIMARY = (0, 255, 255)
        COLOR_SECONDARY = (255, 128, 0)
        COLOR_ACCENT = (255, 0, 255)
        COLOR_BG = (40, 40, 40)
        COLOR_TEXT = (255, 255, 255)
        COLOR_SHADOW = (0, 0, 0)
        BOX_CORNER_RADIUS = 15
        ARROW_THICKNESS = 2
        PANEL_ALPHA = 0.4
        TRAJECTORY_AIM_COLOR = (0, 255, 0) # --- NEW: Color for the aim point ---
        # --- NEW: Visual scaling factor for the compensation arrow/crosshair ---
        PIXELS_PER_DEGREE_COMP = 8


# --- HELPER & UTILITY FUNCTIONS ---
def draw_rounded_rectangle(img, top_left, bottom_right, color, radius, thickness=-1):
    """Draws a rounded rectangle on an image."""
    x1, y1 = top_left
    x2, y2 = bottom_right
    
    cv2.ellipse(img, (x1 + radius, y1 + radius), (radius, radius), 180, 0, 90, color, thickness)
    cv2.ellipse(img, (x2 - radius, y1 + radius), (radius, radius), 270, 0, 90, color, thickness)
    cv2.ellipse(img, (x1 + radius, y2 - radius), (radius, radius), 90, 0, 90, color, thickness)
    cv2.ellipse(img, (x2 - radius, y2 - radius), (radius, radius), 0, 0, 90, color, thickness)
    
    cv2.rectangle(img, (x1 + radius, y1), (x2 - radius, y2), color, thickness)
    cv2.rectangle(img, (x1, y1 + radius), (x2, y2 - radius), color, thickness)

def draw_text_with_shadow(img, text, position, font, scale, color, thickness):
    """Draws text with a subtle drop shadow for better readability."""
    x, y = position
    shadow_pos = (x + 1, y + 1)
    cv2.putText(img, text, shadow_pos, font, scale, CONFIG.UI.COLOR_SHADOW, thickness, cv2.LINE_AA)
    cv2.putText(img, text, position, font, scale, color, thickness, cv2.LINE_AA)

# --- CORE MODULES ---
class WeatherFetcher:
    # (No changes to this class)
    def __init__(self, api_key, city, units, update_interval):
        self.api_key = api_key
        self.city = city
        self.units = units
        self.update_interval = update_interval
        self.weather_data = None
        self.last_update_time = 0
        self.lock = threading.Lock()
        self.start()

    def _fetch_weather(self):
        try:
            url = f"http://api.openweathermap.org/data/2.5/weather?q={self.city}&appid={self.api_key}&units={self.units}"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            with self.lock:
                self.weather_data = {
                    "temp": data['main']['temp'], "humidity": data['main']['humidity'],
                    "wind_speed": data['wind']['speed'], "description": data['weather'][0]['description'].title(),
                    "icon": data['weather'][0]['main']
                }
                self.last_update_time = time.time()
        except requests.exceptions.RequestException:
            with self.lock:
                self.weather_data = {"error": "Weather N/A"}

    def get_weather(self):
        with self.lock:
            return self.weather_data

    def start(self):
        if self.api_key == "YOUR_API_KEY_HERE":
            self.weather_data = {"error": "API Key Missing"}
            return
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()

    def _run(self):
        while True:
            if time.time() - self.last_update_time > self.update_interval:
                self._fetch_weather()
            time.sleep(1)

class FaceTracker:
    def __init__(self):
        self.mp_face_detection = mp.solutions.face_detection
        self.face_detection = self.mp_face_detection.FaceDetection(
            model_selection=1,
            min_detection_confidence=CONFIG.FACE_DETECTION_CONFIDENCE
        )

    def process_frame(self, frame):
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_detection.process(frame_rgb)
        
        main_face_data = None
        largest_area = 0
        
        if results.detections:
            for detection in results.detections:
                bboxC = detection.location_data.relative_bounding_box
                ih, iw, _ = frame.shape
                x, y, w, h = int(bboxC.xmin * iw), int(bboxC.ymin * ih), \
                             int(bboxC.width * iw), int(bboxC.height * ih)

                area = w * h
                if area > largest_area:
                    largest_area = area
                    
                    depth_cm = (CONFIG.KNOWN_FACE_HEIGHT_CM * CONFIG.FOCAL_LENGTH) / h
                    
                    frame_center_x, frame_center_y = iw // 2, ih // 2
                    face_center_x, face_center_y = x + w // 2, y + h // 2
                    
                    offset_x = face_center_x - frame_center_x
                    offset_y = face_center_y - frame_center_y
                    
                    servo_x_angle = np.interp(offset_x, [-iw // 2, iw // 2], [-45, 45])
                    direct_servo_y_angle = np.interp(offset_y, [-ih // 2, ih // 2], [45, -45])

                    # --- MODIFIED: Trajectory Compensation Calculation ---
                    depth_m = depth_cm / 100.0
                    compensation_angle_deg = 0
                    if depth_m > 0:
                        try:
                            time_of_flight = depth_m / CONFIG.PROJECTILE_VELOCITY_MPS
                            vertical_drop_m = 0.5 * CONFIG.GRAVITY_MPS2 * (time_of_flight ** 2)
                            compensation_angle_rad = math.atan(vertical_drop_m / depth_m)
                            compensation_angle_deg = math.degrees(compensation_angle_rad)
                        except ZeroDivisionError:
                            compensation_angle_deg = 0

                    final_servo_y_angle = direct_servo_y_angle + compensation_angle_deg

                    main_face_data = {
                        "bbox": (x, y, w, h),
                        "face_center": (face_center_x, face_center_y),
                        "frame_center": (frame_center_x, frame_center_y),
                        "servo_comp": (round(servo_x_angle, 1), round(final_servo_y_angle, 1)),
                        "depth_cm": round(depth_cm, 1),
                        "compensation_angle": round(compensation_angle_deg, 2) # --- NEW ---
                    }
                    
        return main_face_data

class UIRenderer:
    def __init__(self, frame_width, frame_height):
        self.frame_width = frame_width
        self.frame_height = frame_height

    def draw_face_overlay(self, frame, face_data):
        if not face_data:
            return

        x, y, w, h = face_data["bbox"]
        face_center = face_data["face_center"]
        frame_center = face_data["frame_center"]
        servo_comp = face_data["servo_comp"]
        depth = face_data["depth_cm"]
        compensation_angle = face_data["compensation_angle"] # --- NEW ---
        
        # Draw bounding box and main arrow
        cv2.rectangle(frame, (x, y), (x + w, y + h), CONFIG.UI.COLOR_PRIMARY, 2)
        cv2.arrowedLine(frame, face_center, frame_center, CONFIG.UI.COLOR_ACCENT, 
                        CONFIG.UI.ARROW_THICKNESS, line_type=cv2.LINE_AA)

        # --- NEW: Draw the compensated aim point crosshair ---
        vertical_offset_pixels = int(compensation_angle * CONFIG.UI.PIXELS_PER_DEGREE_COMP)
        aim_point_x = face_center[0]
        aim_point_y = face_center[1] - vertical_offset_pixels
        
        # Draw a small circle and cross lines for the aim point
        cv2.circle(frame, (aim_point_x, aim_point_y), 5, CONFIG.UI.TRAJECTORY_AIM_COLOR, 1)
        cv2.line(frame, (aim_point_x - 10, aim_point_y), (aim_point_x + 10, aim_point_y), CONFIG.UI.TRAJECTORY_AIM_COLOR, 1)
        cv2.line(frame, (aim_point_x, aim_point_y - 10), (aim_point_x, aim_point_y + 10), CONFIG.UI.TRAJECTORY_AIM_COLOR, 1)


        # --- MODIFIED: Display face-specific data including compensation ---
        info_text_1 = f"Servo X: {servo_comp[0]} deg"
        info_text_2 = f"Servo Y: {servo_comp[1]} deg (Comp: +{compensation_angle})"
        info_text_3 = f"Depth: {depth} cm"
        
        draw_text_with_shadow(frame, info_text_1, (x, y - 50), CONFIG.UI.FONT, 
                              CONFIG.UI.FONT_SCALE_MAIN, CONFIG.UI.COLOR_TEXT, CONFIG.UI.FONT_THICKNESS)
        draw_text_with_shadow(frame, info_text_2, (x, y - 30), CONFIG.UI.FONT, 
                              CONFIG.UI.FONT_SCALE_MAIN, CONFIG.UI.COLOR_TEXT, CONFIG.UI.FONT_THICKNESS)
        draw_text_with_shadow(frame, info_text_3, (x, y - 10), CONFIG.UI.FONT, 
                              CONFIG.UI.FONT_SCALE_MAIN, CONFIG.UI.COLOR_TEXT, CONFIG.UI.FONT_THICKNESS)

    def draw_info_panel(self, frame, fps, weather_data):
        # (No changes to this method)
        panel_width, panel_height, margin = 250, 150, 15
        top_left = (self.frame_width - panel_width - margin, margin)
        bottom_right = (self.frame_width - margin, panel_height + margin)
        overlay = frame.copy()
        draw_rounded_rectangle(overlay, top_left, bottom_right, CONFIG.UI.COLOR_BG, CONFIG.UI.BOX_CORNER_RADIUS)
        cv2.addWeighted(overlay, CONFIG.UI.PANEL_ALPHA, frame, 1 - CONFIG.UI.PANEL_ALPHA, 0, frame)
        draw_rounded_rectangle(frame, top_left, bottom_right, CONFIG.UI.COLOR_SECONDARY, CONFIG.UI.BOX_CORNER_RADIUS, thickness=2)
        
        text_x, text_y_start = top_left[0] + 15, top_left[1] + 25
        draw_text_with_shadow(frame, f"FPS: {fps:.1f}", (text_x, text_y_start), CONFIG.UI.FONT, CONFIG.UI.FONT_SCALE_INFO, CONFIG.UI.COLOR_TEXT, CONFIG.UI.FONT_THICKNESS)
        
        weather_icon_map = {"Clear": "☀️", "Clouds": "☁️", "Rain": "🌧️", "Drizzle": "💧", "Thunderstorm": "⛈️", "Snow": "❄️", "Mist": "🌫️"}
        if weather_data and "error" not in weather_data:
            icon = weather_icon_map.get(weather_data["icon"], "")
            draw_text_with_shadow(frame, f"Location: {CONFIG.WEATHER_CITY}", (text_x, text_y_start + 30), CONFIG.UI.FONT, CONFIG.UI.FONT_SCALE_INFO, CONFIG.UI.COLOR_TEXT, CONFIG.UI.FONT_THICKNESS)
            draw_text_with_shadow(frame, f"Weather: {weather_data['description']} {icon}", (text_x, text_y_start + 55), CONFIG.UI.FONT, CONFIG.UI.FONT_SCALE_INFO, CONFIG.UI.COLOR_TEXT, CONFIG.UI.FONT_THICKNESS)
            draw_text_with_shadow(frame, f"Temp: {weather_data['temp']:.1f}°C", (text_x, text_y_start + 80), CONFIG.UI.FONT, CONFIG.UI.FONT_SCALE_INFO, CONFIG.UI.COLOR_TEXT, CONFIG.UI.FONT_THICKNESS)
            draw_text_with_shadow(frame, f"Humidity: {weather_data['humidity']}%", (text_x, text_y_start + 105), CONFIG.UI.FONT, CONFIG.UI.FONT_SCALE_INFO, CONFIG.UI.COLOR_TEXT, CONFIG.UI.FONT_THICKNESS)
        else:
            status = weather_data['error'] if weather_data else "Loading..."
            draw_text_with_shadow(frame, status, (text_x, text_y_start + 30), CONFIG.UI.FONT, CONFIG.UI.FONT_SCALE_INFO, CONFIG.UI.COLOR_ACCENT, CONFIG.UI.FONT_THICKNESS)

# --- MAIN APPLICATION ---
def main():
    cap = cv2.VideoCapture(CONFIG.CAM_INDEX)
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CONFIG.FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CONFIG.FRAME_HEIGHT)
    
    face_tracker = FaceTracker()
    ui_renderer = UIRenderer(int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    weather_fetcher = WeatherFetcher(
        CONFIG.OPENWEATHER_API_KEY, CONFIG.WEATHER_CITY, 
        CONFIG.WEATHER_UNITS, CONFIG.WEATHER_UPDATE_INTERVAL_SEC
    )
    prev_frame_time = 0
    
    while True:
        success, frame = cap.read()
        if not success:
            break
        
        frame = cv2.flip(frame, 1)
        face_data = face_tracker.process_frame(frame)
        weather_data = weather_fetcher.get_weather()
        
        new_frame_time = time.time()
        if prev_frame_time > 0:
            fps = 1 / (new_frame_time - prev_frame_time)
        else:
            fps = 0
        prev_frame_time = new_frame_time

        ui_renderer.draw_face_overlay(frame, face_data)
        ui_renderer.draw_info_panel(frame, fps, weather_data)
        cv2.imshow("Autonomous Targeting UI", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
