"""
╔══════════════════════════════════════════════════════════════╗
║  AI AIR MOUSE — Configuration                               ║
║  All tunable parameters in one place                        ║
╚══════════════════════════════════════════════════════════════╝
"""

# ═══════════════════════════════════════════════════════════════
#  CAMERA
# ═══════════════════════════════════════════════════════════════
CAMERA_INDEX = 0                  # Default webcam (change if multiple cameras)
CAMERA_WIDTH = 1280               # Preferred capture resolution width
CAMERA_HEIGHT = 720               # Preferred capture resolution height

# ═══════════════════════════════════════════════════════════════
#  MEDIAPIPE HANDS
# ═══════════════════════════════════════════════════════════════
MAX_HANDS = 1                     # Track one hand for performance
MODEL_COMPLEXITY = 0              # 0 = lite (fast), 1 = full (accurate)
MIN_DETECTION_CONFIDENCE = 0.5    # Lowered to 0.5 for reliable tracking in all lighting
MIN_TRACKING_CONFIDENCE = 0.5     # Lowered to 0.5 for smooth frame-to-frame tracking

# ═══════════════════════════════════════════════════════════════
#  CURSOR SMOOTHING ENGINE
# ═══════════════════════════════════════════════════════════════
EMA_ALPHA = 0.40                  # EMA blend factor (higher = more responsive)
DEAD_ZONE_PIXELS = 4              # Ignore movements smaller than this (anti-jitter)
PREDICTION_WEIGHT = 0.15          # Velocity-based prediction lookahead (0 = off)
SLOW_SPEED_THRESHOLD = 80.0       # Below this speed → precision mode (px/sec)
FAST_SPEED_THRESHOLD = 600.0      # Above this speed → acceleration mode (px/sec)
ACCELERATION_FACTOR = 1.5         # Speed multiplier in fast mode
PRECISION_FACTOR = 0.65           # Speed multiplier in slow mode (< 1 = finer control)

# ═══════════════════════════════════════════════════════════════
#  FRAME MARGINS (Normalized 0.0–1.0)
#  Defines the "active zone" within the webcam frame.
#  Avoids requiring the user to reach to the very edges.
# ═══════════════════════════════════════════════════════════════
MARGIN_LEFT = 0.12
MARGIN_RIGHT = 0.12
MARGIN_TOP = 0.10
MARGIN_BOTTOM = 0.10

# ═══════════════════════════════════════════════════════════════
#  GESTURE DETECTION
# ═══════════════════════════════════════════════════════════════
PINCH_RATIO_THRESHOLD = 0.42      # Scale-invariant pinch ratio (distance / palm length)
PINCH_THRESHOLD = 0.065           # Fallback absolute normalized distance

CLICK_COOLDOWN_MS = 250           # Minimum ms between click triggers (enables double click)
DRAG_HOLD_THRESHOLD_MS = 300      # Hold pinch this long to start drag
GESTURE_CONFIRM_FRAMES = 1        # Instant 1-frame trigger for zero input latency
SCROLL_SPEED = 4                  # Scroll lines per trigger
SCROLL_COOLDOWN_MS = 60           # Minimum ms between scroll events


# ═══════════════════════════════════════════════════════════════
#  HUD / DEBUG OVERLAY
# ═══════════════════════════════════════════════════════════════
SHOW_HUD = True                   # Show overlay by default (toggle with D key)
WINDOW_NAME = "AI Air Mouse"      # OpenCV window title
