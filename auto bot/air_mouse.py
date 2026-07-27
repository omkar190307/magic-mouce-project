"""
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║              *  A I   A I R   M O U S E  *                           ║
║                                                                      ║
║   Futuristic Hand-Gesture Cursor Control System                      ║
║   Apple trackpad-class smoothness | Multi-display | 60 FPS           ║
║                                                                      ║
║   Gestures:                                                          ║
║     Index finger        -> Move cursor                               ║
║     Idx + Mid pinch     -> Left click (quick) / Drag (hold)          ║
║     Idx + Ring pinch    -> Right click                               ║
║     Three fingers up    -> Scroll up                                 ║
║     Pinky up            -> Scroll down                               ║
║     Thumb + Idx pinch   -> Copy (Ctrl+C)                             ║
║     Thumb + Mid pinch   -> Paste (Ctrl+V)                            ║
║                                                                      ║
║   Controls: Q / ESC = Quit  |  D = Toggle HUD                       ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""

# ═══════════════════════════════════════════════════════════════
#  DPI AWARENESS (must be set before any GUI operations)
# ═══════════════════════════════════════════════════════════════
import sys
import ctypes

IS_WINDOWS = sys.platform.startswith('win32')

if IS_WINDOWS:
    import ctypes.wintypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass



# ═══════════════════════════════════════════════════════════════
#  IMPORTS
# ═══════════════════════════════════════════════════════════════
import cv2
import mediapipe as mp
import numpy as np
import time
import math
import sys
import os
from collections import deque
from enum import Enum, auto
from screeninfo import get_monitors

from config import (
    CAMERA_INDEX, CAMERA_WIDTH, CAMERA_HEIGHT,
    MAX_HANDS, MODEL_COMPLEXITY, MIN_DETECTION_CONFIDENCE, MIN_TRACKING_CONFIDENCE,
    EMA_ALPHA, DEAD_ZONE_PIXELS, PREDICTION_WEIGHT,
    SLOW_SPEED_THRESHOLD, FAST_SPEED_THRESHOLD,
    ACCELERATION_FACTOR, PRECISION_FACTOR,
    MARGIN_LEFT, MARGIN_RIGHT, MARGIN_TOP, MARGIN_BOTTOM,
    PINCH_THRESHOLD, PINCH_RATIO_THRESHOLD, CLICK_COOLDOWN_MS, DRAG_HOLD_THRESHOLD_MS,
    GESTURE_CONFIRM_FRAMES, SCROLL_SPEED, SCROLL_COOLDOWN_MS,
    SHOW_HUD, WINDOW_NAME,
)


# ── MediaPipe Task API ────────────────────────────────────────
BaseOptions = mp.tasks.BaseOptions
HandLandmarker = mp.tasks.vision.HandLandmarker
HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
HandLandmarkerResult = mp.tasks.vision.HandLandmarkerResult
VisionRunningMode = mp.tasks.vision.RunningMode
HandConnections = mp.tasks.vision.HandLandmarksConnections

# Model file path (relative to this script)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(SCRIPT_DIR, "hand_landmarker.task")


# ═══════════════════════════════════════════════════════════════
#  NATIVE MOUSE CONTROLLER (Windows API via ctypes)
#  Direct SendInput — faster than PyAutoGUI, zero dependency,
#  full multi-monitor support, Python 3.14 compatible.
# ═══════════════════════════════════════════════════════════════

INPUT_MOUSE = 0
MOUSEEVENTF_LEFTDOWN  = 0x0002
MOUSEEVENTF_LEFTUP    = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP   = 0x0010
MOUSEEVENTF_WHEEL     = 0x0800
WHEEL_DELTA           = 120


if IS_WINDOWS:
    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx",          ctypes.c_long),
            ("dy",          ctypes.c_long),
            ("mouseData",   ctypes.c_ulong),
            ("dwFlags",     ctypes.c_ulong),
            ("time",        ctypes.c_ulong),
            ("dwExtraInfo", ctypes.c_size_t),
        ]

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk",         ctypes.c_uint16),
            ("wScan",       ctypes.c_uint16),
            ("dwFlags",     ctypes.c_uint32),
            ("time",        ctypes.c_uint32),
            ("dwExtraInfo", ctypes.c_size_t),
        ]

    class _INPUT_UNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [
            ("type",   ctypes.c_ulong),
            ("union",  _INPUT_UNION),
        ]


class MouseController:
    """
    Native mouse controller using Windows SendInput API on Windows,
    with graceful fallback on other platforms.
    """

    @staticmethod
    def _send(flags, mouse_data=0):
        if not IS_WINDOWS:
            return
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.union.mi.dx = 0
        inp.union.mi.dy = 0
        inp.union.mi.mouseData = mouse_data
        inp.union.mi.dwFlags = flags
        inp.union.mi.time = 0
        inp.union.mi.dwExtraInfo = 0
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    @staticmethod
    def move(x, y):
        if IS_WINDOWS:
            ctypes.windll.user32.SetCursorPos(int(x), int(y))

    @classmethod
    def click(cls):
        cls._send(MOUSEEVENTF_LEFTDOWN)
        time.sleep(0.01)
        cls._send(MOUSEEVENTF_LEFTUP)

    @classmethod
    def right_click(cls):
        cls._send(MOUSEEVENTF_RIGHTDOWN)
        time.sleep(0.01)
        cls._send(MOUSEEVENTF_RIGHTUP)

    @classmethod
    def mouse_down(cls):
        cls._send(MOUSEEVENTF_LEFTDOWN)

    @classmethod
    def mouse_up(cls):
        cls._send(MOUSEEVENTF_LEFTUP)

    @classmethod
    def scroll(cls, amount):
        cls._send(MOUSEEVENTF_WHEEL, int(amount * WHEEL_DELTA))

    @staticmethod
    def get_screen_size():
        if IS_WINDOWS:
            w = ctypes.windll.user32.GetSystemMetrics(0)
            h = ctypes.windll.user32.GetSystemMetrics(1)
            return w, h
        return 1920, 1080


mouse = MouseController()



class KeyboardController:
    INPUT_KEYBOARD = 1
    KEYEVENTF_KEYUP = 0x0002
    VK_CONTROL = 0x11
    VK_C = 0x43
    VK_V = 0x56

    @staticmethod
    def _send(vk, flags):
        if not IS_WINDOWS:
            return
        inp = INPUT()
        inp.type = KeyboardController.INPUT_KEYBOARD
        inp.union.ki.wVk = vk
        inp.union.ki.wScan = 0
        inp.union.ki.dwFlags = flags
        inp.union.ki.time = 0
        inp.union.ki.dwExtraInfo = 0
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


    @classmethod
    def press_combo(cls, vk1, vk2):
        cls._send(vk1, 0)
        cls._send(vk2, 0)
        time.sleep(0.01)
        cls._send(vk2, cls.KEYEVENTF_KEYUP)
        cls._send(vk1, cls.KEYEVENTF_KEYUP)

    @classmethod
    def copy(cls):
        cls.press_combo(cls.VK_CONTROL, cls.VK_C)

    @classmethod
    def paste(cls):
        cls.press_combo(cls.VK_CONTROL, cls.VK_V)


keyboard = KeyboardController()


# ═══════════════════════════════════════════════════════════════
#  DRAG STATE MACHINE
# ═══════════════════════════════════════════════════════════════
class DragState(Enum):
    IDLE = auto()
    PINCH_DETECTED = auto()
    DRAGGING = auto()


# ═══════════════════════════════════════════════════════════════
#  DISPLAY MANAGER — Multi-Monitor Coordinate Mapping
# ═══════════════════════════════════════════════════════════════
class DisplayManager:

    def __init__(self):
        self.monitors = []
        self.min_x = 0
        self.min_y = 0
        self.max_x = 1920
        self.max_y = 1080
        self.total_width = 1920
        self.total_height = 1080
        self.refresh()
        self._print_info()

    def refresh(self):
        try:
            self.monitors = get_monitors()
        except Exception as e:
            print(f"  [WARN] Monitor detection failed: {e}")
            self.monitors = []

        if not self.monitors:
            w, h = mouse.get_screen_size()
            self.min_x, self.min_y = 0, 0
            self.max_x, self.max_y = w, h
        else:
            self.min_x = min(m.x for m in self.monitors)
            self.min_y = min(m.y for m in self.monitors)
            self.max_x = max(m.x + m.width for m in self.monitors)
            self.max_y = max(m.y + m.height for m in self.monitors)

        self.total_width = max(self.max_x - self.min_x, 1)
        self.total_height = max(self.max_y - self.min_y, 1)

    def _print_info(self):
        print(f"\n  {'=' * 54}")
        print(f"  |  DISPLAY CONFIGURATION")
        print(f"  {'=' * 54}")
        if self.monitors:
            for i, m in enumerate(self.monitors):
                tag = " * PRIMARY" if m.is_primary else ""
                print(f"  |  Monitor {i + 1}{tag}")
                print(f"  |    Resolution : {m.width} x {m.height}")
                print(f"  |    Position   : ({m.x}, {m.y})")
                if i < len(self.monitors) - 1:
                    print(f"  |  {'-' * 50}")
        else:
            print(f"  |  Fallback: {self.total_width} x {self.total_height}")
        print(f"  |  {'-' * 50}")
        print(f"  |  Virtual Desktop : {self.total_width} x {self.total_height}")
        print(f"  |  Bounds          : ({self.min_x}, {self.min_y}) -> "
              f"({self.max_x}, {self.max_y})")
        print(f"  {'=' * 54}\n")

    def normalized_to_screen(self, nx, ny):
        margin_x = min(MARGIN_LEFT + MARGIN_RIGHT, 0.90)
        margin_y = min(MARGIN_TOP + MARGIN_BOTTOM, 0.90)
        nx = (nx - MARGIN_LEFT) / max(1.0 - margin_x, 0.01)
        ny = (ny - MARGIN_TOP) / max(1.0 - margin_y, 0.01)
        nx = max(0.0, min(1.0, nx))
        ny = max(0.0, min(1.0, ny))
        sx = self.min_x + nx * self.total_width
        sy = self.min_y + ny * self.total_height
        return sx, sy


    def move_cursor(self, x, y):
        x = max(self.min_x, min(self.max_x - 1, int(x)))
        y = max(self.min_y, min(self.max_y - 1, int(y)))
        mouse.move(x, y)


# ═══════════════════════════════════════════════════════════════
#  CURSOR SMOOTHER — 4-Layer Pipeline
# ═══════════════════════════════════════════════════════════════
class CursorSmoother:

    def __init__(self):
        self.prev_x = 0.0
        self.prev_y = 0.0
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.prev_time = time.perf_counter()
        self.initialized = False

    def reset(self):
        self.initialized = False
        self.vel_x = 0.0
        self.vel_y = 0.0

    def smooth(self, raw_x, raw_y):
        now = time.perf_counter()
        dt = min(now - self.prev_time, 0.1)
        self.prev_time = now


        if not self.initialized:
            self.prev_x = raw_x
            self.prev_y = raw_y
            self.initialized = True
            return raw_x, raw_y

        # Layer 1: Dead Zone
        dx = raw_x - self.prev_x
        dy = raw_y - self.prev_y
        if math.hypot(dx, dy) < DEAD_ZONE_PIXELS:
            return self.prev_x, self.prev_y

        # Layer 2: EMA
        ema_x = EMA_ALPHA * raw_x + (1.0 - EMA_ALPHA) * self.prev_x
        ema_y = EMA_ALPHA * raw_y + (1.0 - EMA_ALPHA) * self.prev_y

        # Layer 3: Velocity Prediction
        if dt > 0.001:
            self.vel_x = 0.6 * ((ema_x - self.prev_x) / dt) + 0.4 * self.vel_x
            self.vel_y = 0.6 * ((ema_y - self.prev_y) / dt) + 0.4 * self.vel_y

        pred_x = ema_x + self.vel_x * dt * PREDICTION_WEIGHT
        pred_y = ema_y + self.vel_y * dt * PREDICTION_WEIGHT

        # Layer 4: Adaptive Speed Curve
        speed = math.hypot(self.vel_x, self.vel_y)
        if speed < SLOW_SPEED_THRESHOLD:
            t = speed / max(SLOW_SPEED_THRESHOLD, 1.0)
            factor = PRECISION_FACTOR + (1.0 - PRECISION_FACTOR) * t
        elif speed > FAST_SPEED_THRESHOLD:
            factor = ACCELERATION_FACTOR
        else:
            t = (speed - SLOW_SPEED_THRESHOLD) / max(FAST_SPEED_THRESHOLD - SLOW_SPEED_THRESHOLD, 1.0)
            factor = 1.0 + (ACCELERATION_FACTOR - 1.0) * t
        factor = min(factor, 2.5)

        final_x = self.prev_x + (pred_x - self.prev_x) * factor
        final_y = self.prev_y + (pred_y - self.prev_y) * factor
        self.prev_x = final_x
        self.prev_y = final_y
        return final_x, final_y


# ═══════════════════════════════════════════════════════════════
#  HAND DATA WRAPPER
#  Wraps the new MediaPipe Task API result to provide a
#  consistent landmark access pattern.
# ═══════════════════════════════════════════════════════════════
class HandData:
    """
    Wraps a single hand's landmark list from the MediaPipe Task API
    to provide scale-invariant and orientation-robust gesture detection.
    """

    def __init__(self, landmarks_list):
        """landmarks_list: list of NormalizedLandmark from result.hand_landmarks[0]"""
        self.landmarks = landmarks_list
        # Hand reference scale = distance from Wrist (0) to Middle MCP (9)
        self.palm_size = max(self.distance(0, 9), 0.01)

    def get(self, idx):
        """Get landmark by index. Returns object with .x, .y, .z"""
        return self.landmarks[idx]

    def distance(self, idx1, idx2):
        """Euclidean 2D distance between two landmarks (normalized)."""
        a = self.landmarks[idx1]
        b = self.landmarks[idx2]
        return math.hypot(a.x - b.x, a.y - b.y)

    def relative_distance(self, idx1, idx2):
        """Scale-invariant distance relative to palm length (works at any distance from camera)."""
        return self.distance(idx1, idx2) / self.palm_size

    def is_pinched(self, idx1, idx2):
        """Dual threshold: True if scale-invariant ratio < PINCH_RATIO_THRESHOLD OR absolute distance < PINCH_THRESHOLD."""
        return (self.relative_distance(idx1, idx2) < PINCH_RATIO_THRESHOLD) or (self.distance(idx1, idx2) < PINCH_THRESHOLD)


    def finger_extended(self, tip_idx, pip_idx):
        """Orientation-invariant check: fingertip is further from wrist (0) than PIP joint."""
        dist_tip = self.distance(0, tip_idx)
        dist_pip = self.distance(0, pip_idx)
        return dist_tip > (dist_pip * 1.05)

    def get_finger_states(self):
        """Returns [index, middle, ring, pinky] extension states."""
        return [
            self.finger_extended(8, 6),      # Index
            self.finger_extended(12, 10),    # Middle
            self.finger_extended(16, 14),    # Ring
            self.finger_extended(20, 18),    # Pinky
        ]



# ═══════════════════════════════════════════════════════════════
#  GESTURE DETECTOR — 6 Gestures + Drag State Machine
# ═══════════════════════════════════════════════════════════════
class GestureDetector:

    def __init__(self):
        self.drag_state = DragState.IDLE
        self.pinch_start_time = 0.0
        self.last_click_time = 0.0
        self.last_right_click_time = 0.0
        self.last_scroll_time = 0.0
        self.last_copy_time = 0.0
        self.last_paste_time = 0.0
        self.left_pinch_frames = 0
        self.right_pinch_frames = 0
        self.scroll_up_frames = 0
        self.scroll_down_frames = 0
        self.copy_frames = 0
        self.paste_frames = 0
        self.current_gesture = "IDLE"
        self.pinch_progress = 0.0

    def detect(self, hand: HandData):
        """Returns (gesture_name: str, should_move_cursor: bool)"""
        now_ms = time.time() * 1000.0
        fingers = hand.get_finger_states()

        # Scale-invariant + absolute fallback pinch detection (Thumb 4 + Fingertips 8, 12, 16, 20)
        left_pinching  = hand.is_pinched(4, 8)
        right_pinching = hand.is_pinched(4, 12)
        copy_pinching  = hand.is_pinched(4, 16)
        paste_pinching = hand.is_pinched(4, 20)

        three_fingers_up = fingers[0] and fingers[1] and fingers[2] and not fingers[3]
        pinky_only       = (fingers[3] and not fingers[0] and not fingers[1]) or (not fingers[0] and not fingers[1] and not fingers[2] and not fingers[3] and not copy_pinching and not paste_pinching)

        # PRIORITY 1: Active drag (Thumb + Index pinch held)
        if self.drag_state == DragState.DRAGGING:
            if not left_pinching:
                self.drag_state = DragState.IDLE
                self.left_pinch_frames = 0
                self.pinch_progress = 0.0
                mouse.mouse_up()
                self.current_gesture = "DRAG END"
                return "DRAG END", True
            else:
                self.current_gesture = "DRAGGING"
                return "DRAGGING", True

        # PRIORITY 2: Left pinch / Click / Start Drag (Thumb + Index)
        if left_pinching:
            self.left_pinch_frames += 1
            self.right_pinch_frames = 0
            self.scroll_up_frames = 0
            self.scroll_down_frames = 0

            if self.left_pinch_frames >= GESTURE_CONFIRM_FRAMES:
                if self.drag_state == DragState.IDLE:
                    self.drag_state = DragState.PINCH_DETECTED
                    self.pinch_start_time = now_ms
                    self.current_gesture = "PINCH"
                    self.pinch_progress = 0.0

                elif self.drag_state == DragState.PINCH_DETECTED:
                    hold_duration = now_ms - self.pinch_start_time
                    self.pinch_progress = min(hold_duration / DRAG_HOLD_THRESHOLD_MS, 1.0)

                    if hold_duration >= DRAG_HOLD_THRESHOLD_MS:
                        self.drag_state = DragState.DRAGGING
                        mouse.mouse_down()
                        self.current_gesture = "DRAG START"
                        return "DRAG START", True
                    else:
                        self.current_gesture = "PINCH"

            return self.current_gesture, True
        else:
            if self.drag_state == DragState.PINCH_DETECTED:
                if now_ms - self.last_click_time > CLICK_COOLDOWN_MS:
                    mouse.click()
                    self.last_click_time = now_ms
                    self.current_gesture = "LEFT CLICK"
                self.drag_state = DragState.IDLE
                self.pinch_progress = 0.0
                self.left_pinch_frames = 0
                return "LEFT CLICK", True
            self.left_pinch_frames = 0

        # PRIORITY 3: Right click (Thumb + Middle)
        if right_pinching:
            self.right_pinch_frames += 1
            if self.right_pinch_frames >= GESTURE_CONFIRM_FRAMES:
                if now_ms - self.last_right_click_time > CLICK_COOLDOWN_MS:
                    mouse.right_click()
                    self.last_right_click_time = now_ms
                    self.current_gesture = "RIGHT CLICK"
                return "RIGHT CLICK", True
            return "RIGHT CLICK", True
        else:
            self.right_pinch_frames = 0

        # PRIORITY 4: Copy (Thumb + Ring)
        if copy_pinching:
            self.copy_frames += 1
            if self.copy_frames >= GESTURE_CONFIRM_FRAMES:
                if now_ms - self.last_copy_time > 600.0:
                    keyboard.copy()
                    self.last_copy_time = now_ms
                    self.current_gesture = "COPY"
                return "COPY", True
            return "COPY", True
        else:
            self.copy_frames = 0

        # PRIORITY 5: Paste (Thumb + Pinky)
        if paste_pinching:
            self.paste_frames += 1
            if self.paste_frames >= GESTURE_CONFIRM_FRAMES:
                if now_ms - self.last_paste_time > 600.0:
                    keyboard.paste()
                    self.last_paste_time = now_ms
                    self.current_gesture = "PASTE"
                return "PASTE", True
            return "PASTE", True
        else:
            self.paste_frames = 0

        # PRIORITY 6: Scroll up (3 fingers up)
        if three_fingers_up:
            self.scroll_up_frames += 1
            self.scroll_down_frames = 0
            if self.scroll_up_frames >= GESTURE_CONFIRM_FRAMES:
                if now_ms - self.last_scroll_time > SCROLL_COOLDOWN_MS:
                    mouse.scroll(SCROLL_SPEED)
                    self.last_scroll_time = now_ms
                    self.current_gesture = "SCROLL UP"
            return "SCROLL UP", True
        else:
            self.scroll_up_frames = 0

        # PRIORITY 7: Scroll down (Pinky up / Index & Middle down)
        if pinky_only:
            self.scroll_down_frames += 1
            self.scroll_up_frames = 0
            if self.scroll_down_frames >= GESTURE_CONFIRM_FRAMES:
                if now_ms - self.last_scroll_time > SCROLL_COOLDOWN_MS:
                    mouse.scroll(-SCROLL_SPEED)
                    self.last_scroll_time = now_ms
                    self.current_gesture = "SCROLL DOWN"
            return "SCROLL DOWN", True
        else:
            self.scroll_down_frames = 0

        # Default: Move cursor
        self.current_gesture = "MOVE"
        return "MOVE", True




# ═══════════════════════════════════════════════════════════════
#  HAND CONNECTIONS for manual drawing
# ═══════════════════════════════════════════════════════════════
HAND_BONE_CONNECTIONS = [
    # Thumb
    (0, 1), (1, 2), (2, 3), (3, 4),
    # Index
    (0, 5), (5, 6), (6, 7), (7, 8),
    # Middle
    (0, 9), (9, 10), (10, 11), (11, 12),
    # Ring
    (0, 13), (13, 14), (14, 15), (15, 16),
    # Pinky
    (0, 17), (17, 18), (18, 19), (19, 20),
    # Palm
    (5, 9), (9, 13), (13, 17),
]


# ═══════════════════════════════════════════════════════════════
#  HUD — Premium Futuristic Debug Overlay
# ═══════════════════════════════════════════════════════════════
class HUD:

    # Color Palette (BGR)
    CYAN        = (255, 255, 0)
    MAGENTA     = (255, 0, 200)
    NEON_GREEN  = (0, 255, 140)
    NEON_BLUE   = (255, 160, 0)
    NEON_PINK   = (180, 50, 255)
    NEON_ORANGE = (0, 180, 255)
    NEON_RED    = (60, 60, 255)
    WHITE       = (240, 240, 240)
    GRAY        = (120, 120, 140)
    DARK_PANEL  = (25, 25, 40)

    GESTURE_COLORS = {
        "IDLE":         (80, 80, 100),
        "NO HAND":      (80, 80, 100),
        "MOVE":         (0, 255, 140),
        "LEFT CLICK":   (255, 255, 0),
        "RIGHT CLICK":  (255, 0, 200),
        "PINCH":        (0, 180, 255),
        "PINCH_HOLD":   (0, 180, 255),
        "DRAG START":   (60, 60, 255),
        "DRAGGING":     (60, 60, 255),
        "DRAG END":     (0, 255, 140),
        "SCROLL UP":    (255, 160, 0),
        "SCROLL DOWN":  (255, 160, 0),
        "COPY":         (255, 255, 255),
        "PASTE":        (255, 255, 255),
    }

    def __init__(self, display_manager):
        self.dm = display_manager
        self.fps_history = deque(maxlen=60)
        self.visible = SHOW_HUD
        self.gesture_flash_time = 0.0
        self.last_gesture = ""

    def toggle(self):
        self.visible = not self.visible

    def _draw_panel(self, frame, x, y, w, h, border_color=None):
        fh, fw = frame.shape[:2]
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(fw, x + w), min(fh, y + h)
        if x2 <= x1 or y2 <= y1:
            return
        sub = frame[y1:y2, x1:x2]
        dark = np.full_like(sub, self.DARK_PANEL)
        cv2.addWeighted(sub, 0.25, dark, 0.75, 0, sub)
        frame[y1:y2, x1:x2] = sub
        color = border_color or self.CYAN
        cv2.rectangle(frame, (x1, y1), (x2 - 1, y2 - 1), color, 1)

    def _draw_glow_circle(self, frame, cx, cy, radius, color):
        fh, fw = frame.shape[:2]
        if not (0 <= cx < fw and 0 <= cy < fh):
            return
        glow = tuple(max(0, c // 3) for c in color)
        cv2.circle(frame, (cx, cy), radius + 4, glow, 2)
        cv2.circle(frame, (cx, cy), radius, color, -1)
        bright = tuple(min(255, c + 60) for c in color)
        cv2.circle(frame, (cx, cy), max(1, radius // 2), bright, -1)

    def draw(self, frame, gesture_name, fps, hand_data, pinch_progress=0.0):
        h, w = frame.shape[:2]

        if hand_data:
            self._draw_hand(frame, hand_data, w, h)

        if not self.visible:
            return frame

        if gesture_name != self.last_gesture:
            self.gesture_flash_time = time.time()
            self.last_gesture = gesture_name

        # FPS Panel
        self.fps_history.append(fps)
        avg_fps = sum(self.fps_history) / len(self.fps_history)
        fps_color = self.NEON_GREEN if avg_fps >= 50 else self.NEON_ORANGE if avg_fps >= 30 else self.NEON_RED
        self._draw_panel(frame, 8, 8, 145, 50, fps_color)
        cv2.putText(frame, "FPS", (18, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.4, self.GRAY, 1, cv2.LINE_AA)
        cv2.putText(frame, f"{avg_fps:.0f}", (55, 45), cv2.FONT_HERSHEY_DUPLEX, 0.9, fps_color, 2, cv2.LINE_AA)

        # Gesture Panel
        g_color = self.GESTURE_COLORS.get(gesture_name, self.WHITE)
        panel_w = 200
        gx = w - panel_w - 8
        flash_dt = time.time() - self.gesture_flash_time
        if flash_dt < 0.3:
            alpha = 1.0 - (flash_dt / 0.3)
            bright_panel = tuple(min(255, int(c + 80 * alpha)) for c in g_color)
        else:
            bright_panel = g_color
        self._draw_panel(frame, gx, 8, panel_w, 50, bright_panel)
        cv2.putText(frame, gesture_name.replace("_", " "), (gx + 12, 42),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, g_color, 2, cv2.LINE_AA)
        cv2.circle(frame, (gx + panel_w - 20, 33), 6, g_color, -1)

        # Pinch Progress Bar
        if pinch_progress > 0.01:
            bar_x, bar_y, bar_w, bar_h = gx, 62, panel_w, 6
            self._draw_panel(frame, bar_x, bar_y, bar_w, bar_h + 4)
            fill_w = int(bar_w * pinch_progress)
            bar_color = self.NEON_ORANGE if pinch_progress < 1.0 else self.NEON_RED
            cv2.rectangle(frame, (bar_x + 1, bar_y + 1),
                          (bar_x + fill_w, bar_y + bar_h + 2), bar_color, -1)

        # Monitor map
        self._draw_monitor_map(frame, 8, h - 75, 180, 60)

        # Legend
        self._draw_legend(frame, w - 205, h - 145, 198, 132)

        # Scan lines
        self._draw_scan_lines(frame, h, w)

        return frame

    def _draw_hand(self, frame, hand_data: HandData, w, h):
        lms = hand_data.landmarks

        # Draw bones
        for (a, b) in HAND_BONE_CONNECTIONS:
            p1 = (int(lms[a].x * w), int(lms[a].y * h))
            p2 = (int(lms[b].x * w), int(lms[b].y * h))
            cv2.line(frame, p1, p2, (100, 180, 0), 2, cv2.LINE_AA)

        # Draw all landmarks
        for i, lm in enumerate(lms):
            cx, cy = int(lm.x * w), int(lm.y * h)
            cv2.circle(frame, (cx, cy), 3, self.CYAN, -1)

        # Highlight fingertips
        tip_colors = {4: self.NEON_PINK, 8: self.NEON_GREEN, 12: self.CYAN,
                      16: self.MAGENTA, 20: self.NEON_BLUE}
        for tip_idx, color in tip_colors.items():
            cx, cy = int(lms[tip_idx].x * w), int(lms[tip_idx].y * h)
            self._draw_glow_circle(frame, cx, cy, 7, color)

        # Cursor crosshair on index tip
        ix, iy = int(lms[8].x * w), int(lms[8].y * h)
        s = 18
        cv2.line(frame, (ix - s, iy), (ix + s, iy), self.NEON_GREEN, 1, cv2.LINE_AA)
        cv2.line(frame, (ix, iy - s), (ix, iy + s), self.NEON_GREEN, 1, cv2.LINE_AA)
        cv2.circle(frame, (ix, iy), 12, self.NEON_GREEN, 1, cv2.LINE_AA)

    def _draw_monitor_map(self, frame, x, y, map_w, map_h):
        self._draw_panel(frame, x, y, map_w, map_h)
        cv2.putText(frame, "DISPLAYS", (x + 8, y + 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, self.GRAY, 1, cv2.LINE_AA)
        if not self.dm.monitors:
            return
        pad, label_h = 12, 18
        scale = min((map_w - pad * 2) / max(self.dm.total_width, 1),
                     (map_h - pad - label_h) / max(self.dm.total_height, 1))
        for i, m in enumerate(self.dm.monitors):
            mx = int(x + pad + (m.x - self.dm.min_x) * scale)
            my = int(y + label_h + (m.y - self.dm.min_y) * scale)
            mw, mh = max(int(m.width * scale), 8), max(int(m.height * scale), 6)
            color = self.CYAN if m.is_primary else self.NEON_BLUE
            cv2.rectangle(frame, (mx, my), (mx + mw, my + mh), color, 1)
            cv2.putText(frame, str(i + 1), (mx + 3, my + mh - 3),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1, cv2.LINE_AA)

    def _draw_legend(self, frame, x, y, w, h):
        self._draw_panel(frame, x, y, w, h)
        entries = [
            ("Index Up",       "Move",    self.NEON_GREEN),
            ("Idx+Mid Pinch",  "Click",   self.CYAN),
            ("Hold Pinch",     "Drag",    self.NEON_RED),
            ("Idx+Ring Pinch", "R-Click", self.MAGENTA),
            ("3 Fingers",      "Scrl Up", self.NEON_BLUE),
            ("Pinky Up",       "Scrl Dn", self.NEON_BLUE),
            ("Thumb+Idx",      "Copy",    self.WHITE),
            ("Thumb+Mid",      "Paste",   self.WHITE),
        ]
        for i, (gesture, action, color) in enumerate(entries):
            ly = y + 16 + i * 18
            cv2.circle(frame, (x + 10, ly - 3), 3, color, -1)
            cv2.putText(frame, gesture, (x + 20, ly),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.32, self.GRAY, 1, cv2.LINE_AA)
            cv2.putText(frame, action, (x + 130, ly),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.32, color, 1, cv2.LINE_AA)

    def _draw_scan_lines(self, frame, h, w):
        overlay = frame.copy()
        for row in range(0, h, 4):
            cv2.line(overlay, (0, row), (w, row), (0, 0, 0), 1)
        cv2.addWeighted(overlay, 0.07, frame, 0.93, 0, frame)


# ═══════════════════════════════════════════════════════════════
#  MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════
class AirMouseApp:

    def __init__(self):
        self._print_banner()
        print("  Initializing subsystems...\n")

        self.display = DisplayManager()
        self.smoother = CursorSmoother()
        self.gesture = GestureDetector()

        # ── MediaPipe HandLandmarker (new Task API) ───────────
        MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
        if not os.path.exists(MODEL_PATH) or os.path.getsize(MODEL_PATH) == 0:
            print(f"  [INFO] Model file missing or corrupted. Downloading from official source...")
            try:
                import urllib.request
                def progress(count, block_size, total_size):
                    if total_size > 0:
                        percent = int(count * block_size * 100 / total_size)
                        sys.stdout.write(f"\r  Downloading hand_landmarker.task... {percent}%")
                        sys.stdout.flush()
                urllib.request.urlretrieve(MODEL_URL, MODEL_PATH, progress)
                print("\n  [INFO] Download complete!")
            except Exception as e:
                print(f"\n  [ERROR] Failed to download model: {e}")
                print(f"  [INFO]  Please manually download from: {MODEL_URL}")
                sys.exit(1)

        print(f"  Loading model: hand_landmarker.task...", end=" ", flush=True)

        # Using VIDEO mode (synchronous) for simplicity
        options = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=VisionRunningMode.VIDEO,
            num_hands=MAX_HANDS,
            min_hand_detection_confidence=MIN_DETECTION_CONFIDENCE,
            min_hand_presence_confidence=MIN_DETECTION_CONFIDENCE,
            min_tracking_confidence=MIN_TRACKING_CONFIDENCE,
        )
        self.landmarker = HandLandmarker.create_from_options(options)
        print("OK")

        # ── Camera ────────────────────────────────────────────
        print("  Opening camera...", end=" ", flush=True)
        self.cap = None
        attempts = [
            (CAMERA_INDEX, cv2.CAP_DSHOW) if IS_WINDOWS else (CAMERA_INDEX, None),
            (CAMERA_INDEX, None),
            (0, None),
            (1, None),
        ]
        for cam_idx, api in attempts:
            cap = cv2.VideoCapture(cam_idx, api) if api is not None else cv2.VideoCapture(cam_idx)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
            cap.set(cv2.CAP_PROP_FPS, 60)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if cap.isOpened():
                ret, test_frame = cap.read()
                if ret and test_frame is not None:
                    self.cap = cap
                    break
                cap.release()

        if self.cap is None or not self.cap.isOpened():
            print("FAILED! Could not open any camera device.")
            sys.exit(1)
        actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
        print(f"OK ({actual_w}x{actual_h} @ {actual_fps:.0f}fps)")


        self.hud = HUD(self.display)
        self.prev_frame_time = time.perf_counter()
        self.fps = 0.0
        self.frame_count = 0
        self.timestamp_ms = 0

    def _print_banner(self):
        print(r"""
   ================================================================
   |                                                              |
   |     AAAAA  IIIII RRRR     M   M  OOO  U   U  SSSS EEEEE     |
   |    A   A   I   R   R    MM MM O   O U   U S     E         |
   |    AAAAA   I   RRRR     M M M O   O U   U  SSS  EEEE      |
   |    A   A   I   R  R     M   M O   O U   U     S E         |
   |    A   A IIIII R   R    M   M  OOO   UUU  SSSS  EEEEE     |
   |                                                              |
   |    *  Futuristic Hand-Gesture Cursor Control System  *       |
   |                                                              |
   |--------------------------------------------------------------|
   |  Index Tip           -> Move Cursor                          |
   |  Thumb + Idx Pinch   -> Left Click (tap) / Drag (hold)       |
   |  Thumb + Mid Pinch   -> Right Click                          |
   |  Thumb + Ring Pinch  -> Copy (Ctrl+C)                        |
   |  Thumb + Pinky Pinch -> Paste (Ctrl+V)                       |
   |  Three Fingers Up    -> Scroll Up                            |
   |  Pinky Up            -> Scroll Down                          |
   |--------------------------------------------------------------|
   |  Q / ESC = Quit   |   D = Toggle HUD                        |
   ================================================================
""")


    def run(self):
        print("\n  * AI Air Mouse is ACTIVE -- show your hand!")
        print(f"  * Press Q or ESC to quit  |  D to toggle HUD\n")

        try:
            while self.cap.isOpened():
                success, frame = self.cap.read()
                if not success:
                    continue

                self.frame_count += 1
                frame = cv2.flip(frame, 1)

                # FPS
                now = time.perf_counter()
                dt = now - self.prev_frame_time
                self.prev_frame_time = now
                self.fps = 1.0 / max(dt, 0.001)

                # ── MediaPipe Detection (new Task API) ────────
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                self.timestamp_ms += int(dt * 1000) + 1  # Monotonically increasing
                result = self.landmarker.detect_for_video(mp_image, self.timestamp_ms)

                # ── Process results ───────────────────────────
                gesture_name = "NO HAND"
                hand_data = None
                pinch_progress = 0.0

                if result.hand_landmarks and len(result.hand_landmarks) > 0:
                    hand_data = HandData(result.hand_landmarks[0])

                    gesture_name, should_move = self.gesture.detect(hand_data)
                    pinch_progress = self.gesture.pinch_progress

                    if should_move:
                        idx_tip = hand_data.get(8)
                        raw_x, raw_y = self.display.normalized_to_screen(idx_tip.x, idx_tip.y)
                        smooth_x, smooth_y = self.smoother.smooth(raw_x, raw_y)
                        self.display.move_cursor(smooth_x, smooth_y)
                else:
                    if self.gesture.drag_state == DragState.DRAGGING:
                        mouse.mouse_up()
                        self.gesture.drag_state = DragState.IDLE
                    self.gesture.left_pinch_frames = 0
                    self.gesture.right_pinch_frames = 0
                    self.gesture.pinch_progress = 0.0
                    self.smoother.reset()
                    self.gesture.current_gesture = "NO HAND"

                # ── Render HUD ────────────────────────────────
                frame = self.hud.draw(frame, gesture_name, self.fps, hand_data, pinch_progress)

                cv2.imshow(WINDOW_NAME, frame)

                # Check if user closed window using 'X' titlebar button
                if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                    print("\n  [INFO] Window closed by user.")
                    break

                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or key == 27:
                    break
                elif key in (ord('d'), ord('D')):
                    self.hud.toggle()
                    print(f"  [HUD] {'ON' if self.hud.visible else 'OFF'}")


        except KeyboardInterrupt:
            print("\n  Interrupted.")
        finally:
            self._cleanup()

    def _cleanup(self):
        print(f"\n  {'─' * 40}")
        print(f"  Shutting down... (frames: {self.frame_count})")
        if self.gesture.drag_state == DragState.DRAGGING:
            mouse.mouse_up()
        self.cap.release()
        cv2.destroyAllWindows()
        self.landmarker.close()
        print(f"  Goodbye!")
        print(f"  {'─' * 40}\n")


if __name__ == "__main__":
    app = AirMouseApp()
    app.run()
