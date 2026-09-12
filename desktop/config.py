"""Competition-scoped retrieval and hand-control tuning constants.

Keep physical-demo tuning here so it can be changed without touching gesture,
interaction, or rendering code.
"""

COMPETITION_CLASSES = ('toy_car', 'human_heart', 'earth')

# Retrieval acceptance is intentionally conservative: a rejection is safer than
# opening an absurdly wrong object during the demonstration.
# Calibrated from the retained physical Heart/Car/Earth captures and automated
# blank, plain-circle, scribble, text, bottle, and non-competition render
# negatives. The weakest retained positive is 0.795; negatives reached 0.745.
RETRIEVAL_MIN_SCORE = .78
RETRIEVAL_MIN_MARGIN = .040
MAX_QUERY_REGIONS = 3
# Calibrated against the retained physical Heart sample and the supplied
# physical Earth camera frame. OpenCLIP remains dominant; this small edge-shape
# contribution only applies to line/edge queries against sketch references.
SKETCH_SHAPE_WEIGHT = .10

# Paper acquisition. Progress is accumulated rather than restarted after every
# slightly unstable frame, which makes handheld pages usable without allowing
# a genuinely moving/replaced page to auto-capture.
PAPER_STABLE_SECONDS = .55
PAPER_MOVEMENT_SOFT = .035
PAPER_MOVEMENT_HARD = .10
PAPER_CONTENT_SOFT = .11
PAPER_CONTENT_HARD = .22
PAPER_UNSTABLE_DECAY = .20
PAPER_QUAD_SMOOTHING_MIN = .28
PAPER_QUAD_SMOOTHING_MAX = .68

# One Euro landmark filter (normalized MediaPipe coordinates).
ONE_EURO_MIN_CUTOFF = 1.15
ONE_EURO_BETA = .32
ONE_EURO_D_CUTOFF = 1.0

PINCH_ENTER_THRESHOLD = .28
PINCH_RELEASE_THRESHOLD = .43
PINCH_CONFIRMATION_SECONDS = .080
POINT_CONFIRMATION_SECONDS = .100
HAND_LOSS_RELEASE_SECONDS = .22

TRANSLATION_SENSITIVITY = .82
TRANSLATION_DEAD_ZONE_PX = 2.5
TRANSLATION_MAX_STEP_PX = 42.
ROTATION_SENSITIVITY = .72
ROTATION_DEAD_ZONE_RADIANS = .020
ROTATION_MAX_STEP_RADIANS = .14
ORBIT_SENSITIVITY = .22
ORBIT_DEAD_ZONE_PX = 2.0
ORBIT_MAX_STEP_PX = 32.
DEPTH_SENSITIVITY = .55
DEPTH_DEAD_ZONE = .025
DEPTH_MAX_STEP = .08

EXPLODE_SENSITIVITY = 2.25
EXPLODE_DEAD_ZONE = .012
EXPLODE_FILTER_ALPHA = .20

RESET_DWELL_SECONDS = 1.20
POINT_DWELL_SECONDS = .60

# Physical isolation remains available with mouse/UI. Disabling the gesture
# prevents a stationary grab from unexpectedly changing mode during the demo.
ENABLE_GESTURE_ISOLATE = False
