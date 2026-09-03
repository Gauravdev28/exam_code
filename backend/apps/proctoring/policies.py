"""
Versioned Proctoring Inference, Audio, and Risk Calculation Policies for CODEGUARD.
"""
from decimal import Decimal

# ==============================================================================
# 1. Versioned AI Inference Policy Contract
# ==============================================================================

PROCTORING_INFERENCE_POLICY_V1 = {
    "policy_version": "CG-INFERENCE-POL-V1",
    "model_name": "YOLOv8n-MediaPipeFaceMesh",
    "model_version": "CG-MODELS-2026.1",
    "threshold_version": "CG-THRESHOLDS-V1",
    "phone_confidence_threshold": 0.65,
    "multiple_face_confidence_threshold": 0.60,
    "face_missing_duration_seconds": 5.0,
    "required_persistent_frames": 2,
    "persistence_window_seconds": 4.0,
    "head_turn_yaw_threshold_degrees": 30.0,
    "head_tilt_pitch_threshold_degrees": 25.0,
    "gaze_deviation_duration_seconds": 4.0,
    "target_frame_sampling_rate_fps": 0.5,
    "decay_lambda_parameter": 0.001155,       # Half-life = 600 seconds (10 minutes)
    "decay_evaluation_window_seconds": 3600,  # 1 hour active evaluation window
    "correlation_window_seconds": 60,         # Multi-signal correlation window
    "minimum_independent_families": 2,        # Minimum distinct active signal families
    "correlation_bonus": Decimal('15.00'),    # Correlation bonus for qualifying condition
    "correlation_cooldown_seconds": 60,       # Cooldown preventing repeated bonus spam
    "maximum_correlation_contribution": Decimal('30.00'),  # Maximum correlation contribution ceiling
}

# ==============================================================================
# 2. Versioned Audio Policy Contract
# ==============================================================================

PROCTORING_AUDIO_POLICY_V1 = {
    "audio_policy_version": "CG-AUDIO-POL-V1",
    "client_trigger_threshold_db": 65.0,      # Client activity hint threshold only
    "clip_duration_seconds": 2.0,             # Bounded Opus snippet duration
    "maximum_clip_size_bytes": 102400,        # 100 KB max Opus WebM
    "vad_model_version": "WebRTC-VAD-V1",
    "vad_speech_confidence_threshold": 0.70,  # Server-side VAD validation gate
    "audio_cooldown_seconds": 30,
    "audio_rate_limit_per_minute": 6,
}

# ==============================================================================
# 3. Event Family Classifications & Caps
# ==============================================================================

EVENT_FAMILY_MAP = {
    'WINDOW_BLUR': 'FOCUS_LOSS',
    'TAB_SWITCH': 'FOCUS_LOSS',
    'FULLSCREEN_EXIT': 'FOCUS_LOSS',
    'PAGE_VISIBILITY_CHANGE': 'FOCUS_LOSS',
    'FACE_MISSING': 'FACE_PRESENCE',
    'FACE_PARTIALLY_OCCLUDED': 'FACE_PRESENCE',
    'HEAD_TURN_LEFT': 'HEAD_POSE',
    'HEAD_TURN_RIGHT': 'HEAD_POSE',
    'HEAD_TURN_PROLONGED': 'HEAD_POSE',
    'HEAD_TILT_DOWN': 'HEAD_POSE',
    'HEAD_TILT_UP': 'HEAD_POSE',
    'GAZE_DEVIATION': 'HEAD_POSE',
    'AUDIO_ACTIVITY': 'AUDIO',
    'MULTIPLE_FACES': 'MULTIPLE_PEOPLE',
    'MULTIPLE_VOICE_ACTIVITY': 'MULTIPLE_PEOPLE',
    'PHONE_DETECTED': 'UNAUTHORIZED_DEVICE',
    'BOOK_NOTES_DETECTED': 'UNAUTHORIZED_DEVICE',
    'PROCTORING_DEGRADED': 'SYSTEM_INFRA',
    'CAMERA_UNAVAILABLE': 'SYSTEM_INFRA',
    'MICROPHONE_UNAVAILABLE': 'SYSTEM_INFRA',
    'AI_INFERENCE_FAILURE': 'SYSTEM_INFRA',
    'PROCTORING_SYSTEM_ERROR': 'SYSTEM_INFRA',
}

EVENT_FAMILY_CAPS = {
    'FOCUS_LOSS': Decimal('40.00'),
    'FACE_PRESENCE': Decimal('32.00'),
    'HEAD_POSE': Decimal('20.00'),
    'AUDIO': Decimal('36.00'),
    'MULTIPLE_PEOPLE': Decimal('50.00'),
    'UNAUTHORIZED_DEVICE': Decimal('80.00'),
    'SYSTEM_INFRA': Decimal('0.00'),
}

EVENT_BASE_DELTAS = {
    'WINDOW_BLUR': Decimal('4.00'),
    'TAB_SWITCH': Decimal('8.00'),
    'FULLSCREEN_EXIT': Decimal('10.00'),
    'PAGE_VISIBILITY_CHANGE': Decimal('8.00'),
    'FACE_MISSING': Decimal('8.00'),
    'FACE_PARTIALLY_OCCLUDED': Decimal('4.00'),
    'HEAD_TURN_PROLONGED': Decimal('5.00'),
    'HEAD_TURN_LEFT': Decimal('5.00'),
    'HEAD_TURN_RIGHT': Decimal('5.00'),
    'HEAD_TILT_DOWN': Decimal('5.00'),
    'HEAD_TILT_UP': Decimal('5.00'),
    'GAZE_DEVIATION': Decimal('5.00'),
    'AUDIO_ACTIVITY': Decimal('12.00'),
    'MULTIPLE_FACES': Decimal('25.00'),
    'MULTIPLE_VOICE_ACTIVITY': Decimal('15.00'),
    'PHONE_DETECTED': Decimal('40.00'),
    'BOOK_NOTES_DETECTED': Decimal('20.00'),
    'PROCTORING_DEGRADED': Decimal('0.00'),
    'CAMERA_UNAVAILABLE': Decimal('0.00'),
    'MICROPHONE_UNAVAILABLE': Decimal('0.00'),
    'AI_INFERENCE_FAILURE': Decimal('0.00'),
    'PROCTORING_SYSTEM_ERROR': Decimal('0.00'),
}

EVENT_COOLDOWNS_SECONDS = {
    'WINDOW_BLUR': 10,
    'TAB_SWITCH': 15,
    'FULLSCREEN_EXIT': 15,
    'PAGE_VISIBILITY_CHANGE': 15,
    'FACE_MISSING': 20,
    'FACE_PARTIALLY_OCCLUDED': 20,
    'HEAD_TURN_PROLONGED': 20,
    'HEAD_TURN_LEFT': 20,
    'HEAD_TURN_RIGHT': 20,
    'GAZE_DEVIATION': 20,
    'AUDIO_ACTIVITY': 30,
    'MULTIPLE_FACES': 30,
    'MULTIPLE_VOICE_ACTIVITY': 30,
    'PHONE_DETECTED': 30,
    'BOOK_NOTES_DETECTED': 30,
    'PROCTORING_DEGRADED': 0,
    'CAMERA_UNAVAILABLE': 0,
    'MICROPHONE_UNAVAILABLE': 0,
    'AI_INFERENCE_FAILURE': 0,
    'PROCTORING_SYSTEM_ERROR': 0,
}
