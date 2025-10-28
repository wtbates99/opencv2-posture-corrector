import json
import os
import sys
from dataclasses import dataclass, field, fields
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Tuple,
    Type,
    get_args,
    get_origin,
)

import mediapipe as mp
from PyQt6.QtCore import QSettings

# Path where legacy user settings were stored. Retained for migration only.
USER_SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "user_settings.json")

SETTINGS_SCHEMA_VERSION = "1.1.0"
SETTINGS_ORGANIZATION = "PostureCorrector"
SETTINGS_APPLICATION = "PostureApp"
ENV_PREFIX = "POSTURE"


class SettingsValidationError(ValueError):
    """Raised when attempting to set an invalid value on the settings store."""


# Helper function to get the correct path for bundled resources
def get_resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        # Running in development mode
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def _default_tracking_intervals() -> Dict[str, int]:
    return {
        "Every 15 minutes": 15,
        "Every 30 minutes": 30,
        "Every hour": 60,
    }


def _default_posture_thresholds() -> Dict[str, float]:
    return {
        "head_tilt": 1.2,
        "neck_angle": 45.0,
        "shoulder_level": 5.0,
        "shoulder_roll": 2.0,
        "spine_angle": 45.0,
    }


def _default_posture_weights() -> List[float]:
    return [0.2, 0.2, 0.15, 0.15, 0.15, 0.1, 0.05]


@dataclass(frozen=True)
class ResourceSettings:
    icon_path: str = field(
        default_factory=lambda: get_resource_path("src/static/icon.png")
    )
    default_db_name: str = field(
        default_factory=lambda: os.path.join(
            os.path.dirname(__file__), "posture_data.db"
        )
    )


@dataclass
class RuntimeSettings:
    default_camera_id: int = 0
    default_fps: int = 30
    frame_width: int = 1280
    frame_height: int = 720
    notification_cooldown: int = 300
    poor_posture_threshold: int = 60
    default_posture_message: str = "Please sit up straight!"
    tracking_intervals: Dict[str, int] = field(
        default_factory=_default_tracking_intervals
    )
    tracking_duration_minutes: int = 1
    enable_database_logging: bool = False
    db_write_interval_seconds: int = 900
    notifications_enabled: bool = True
    focus_mode_enabled: bool = False


@dataclass
class MLTuningSettings:
    model_complexity: int = 1
    min_detection_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    posture_weights: List[float] = field(default_factory=_default_posture_weights)
    posture_thresholds: Dict[str, float] = field(
        default_factory=_default_posture_thresholds
    )
    score_buffer_size: int = 1000
    score_window_size: int = 5
    score_threshold: int = 65


@dataclass
class UserProfileSettings:
    has_completed_onboarding: bool = False
    baseline_posture_score: float = 75.0
    baseline_neck_angle: float = 10.0
    baseline_shoulder_level: float = 2.0
    preferred_theme: str = "system"
    language_code: str = "en_US"


POSTURE_LANDMARKS = [
    mp.solutions.pose.PoseLandmark.NOSE,
    mp.solutions.pose.PoseLandmark.LEFT_EYE_INNER,
    mp.solutions.pose.PoseLandmark.LEFT_EYE,
    mp.solutions.pose.PoseLandmark.LEFT_EYE_OUTER,
    mp.solutions.pose.PoseLandmark.RIGHT_EYE_INNER,
    mp.solutions.pose.PoseLandmark.RIGHT_EYE,
    mp.solutions.pose.PoseLandmark.RIGHT_EYE_OUTER,
    mp.solutions.pose.PoseLandmark.LEFT_EAR,
    mp.solutions.pose.PoseLandmark.RIGHT_EAR,
    mp.solutions.pose.PoseLandmark.MOUTH_LEFT,
    mp.solutions.pose.PoseLandmark.MOUTH_RIGHT,
    mp.solutions.pose.PoseLandmark.LEFT_SHOULDER,
    mp.solutions.pose.PoseLandmark.RIGHT_SHOULDER,
    mp.solutions.pose.PoseLandmark.LEFT_ELBOW,
    mp.solutions.pose.PoseLandmark.RIGHT_ELBOW,
    mp.solutions.pose.PoseLandmark.LEFT_WRIST,
    mp.solutions.pose.PoseLandmark.RIGHT_WRIST,
    mp.solutions.pose.PoseLandmark.LEFT_HIP,
    mp.solutions.pose.PoseLandmark.RIGHT_HIP,
]


def _serialize_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value)
    return value


def _coerce_primitive(expected_type: Type[Any], value: Any) -> Any:
    if expected_type is bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        raise SettingsValidationError(f"Cannot coerce {value!r} to bool")
    if expected_type is int:
        return int(value)
    if expected_type is float:
        return float(value)
    if expected_type is str:
        return str(value)
    return value


def _deserialize_value(expected_type: Type[Any], raw_value: Any, fallback: Any) -> Any:
    if raw_value is None:
        return fallback

    origin = get_origin(expected_type)
    if origin is None:
        expected = expected_type
        if expected in (Any, type(fallback)):
            return raw_value
        return _coerce_primitive(expected, raw_value)

    args = get_args(expected_type)
    if origin in (dict, Dict, MutableMapping, Mapping):
        if isinstance(raw_value, str):
            try:
                raw_value = json.loads(raw_value)
            except json.JSONDecodeError as exc:
                raise SettingsValidationError(
                    "Invalid JSON for mapping setting"
                ) from exc
        if not isinstance(raw_value, Mapping):
            raise SettingsValidationError(
                f"Expected mapping for {expected_type}, got {type(raw_value)}"
            )
        key_type, value_type = args or (Any, Any)
        return {
            _deserialize_value(key_type, key, key): _deserialize_value(
                value_type, val, val
            )
            for key, val in raw_value.items()
        }

    if origin in (list, List, tuple, Tuple, Iterable):
        if isinstance(raw_value, str):
            try:
                raw_value = json.loads(raw_value)
            except json.JSONDecodeError:
                raw_value = [
                    part.strip() for part in raw_value.split(",") if part.strip()
                ]
        if not isinstance(raw_value, Iterable) or isinstance(raw_value, (str, bytes)):
            raise SettingsValidationError(
                f"Expected iterable for {expected_type}, got {type(raw_value)}"
            )
        item_type = args[0] if args else Any
        coerced = [_deserialize_value(item_type, item, item) for item in raw_value]
        return coerced if origin in (list, List, Iterable) else tuple(coerced)

    return raw_value


class SettingsStore:
    def __init__(self) -> None:
        self.resources = ResourceSettings()
        self.runtime = RuntimeSettings()
        self.ml = MLTuningSettings()
        self.profile = UserProfileSettings()
        self._settings = QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)
        self._ensure_schema_version()
        self._maybe_migrate_legacy_json()
        self._load_group("runtime", self.runtime)
        self._load_group("ml", self.ml)
        self._load_group("profile", self.profile)
        self._apply_env_overrides()

    def _ensure_schema_version(self) -> None:
        stored_version = self._settings.value("metadata/schema_version", type=str)
        if stored_version != SETTINGS_SCHEMA_VERSION:
            self._settings.setValue("metadata/schema_version", SETTINGS_SCHEMA_VERSION)
            self._settings.sync()

    def _maybe_migrate_legacy_json(self) -> None:
        if not os.path.exists(USER_SETTINGS_FILE):
            return
        try:
            with open(USER_SETTINGS_FILE, "r", encoding="utf-8") as legacy_file:
                legacy_payload = json.load(legacy_file)
        except (OSError, json.JSONDecodeError):
            return

        for key, value in legacy_payload.items():
            if key not in KEY_TO_SECTION_FIELD:
                continue
            section_name, field_name = KEY_TO_SECTION_FIELD[key]
            self._set_field(section_name, field_name, value, persist=False)

        self.save_runtime()
        self.save_ml()
        backup_path = USER_SETTINGS_FILE + ".legacy"
        try:
            os.replace(USER_SETTINGS_FILE, backup_path)
        except OSError:
            pass

    def _apply_env_overrides(self) -> None:
        overrides = {
            "runtime": self.runtime,
            "ml": self.ml,
            "profile": self.profile,
        }
        for section_name, section_obj in overrides.items():
            for field_info in fields(section_obj):
                env_key = (
                    f"{ENV_PREFIX}_{section_name.upper()}_{field_info.name.upper()}"
                )
                if env_key not in os.environ:
                    continue
                raw_value = os.environ[env_key]
                coerced = _deserialize_value(
                    field_info.type, raw_value, getattr(section_obj, field_info.name)
                )
                setattr(section_obj, field_info.name, coerced)

    def _load_group(self, group_name: str, section_obj: Any) -> None:
        self._settings.beginGroup(group_name)
        try:
            for field_info in fields(section_obj):
                default = getattr(section_obj, field_info.name)
                raw_value = self._settings.value(field_info.name, None)
                value = _deserialize_value(field_info.type, raw_value, default)
                setattr(section_obj, field_info.name, value)
        finally:
            self._settings.endGroup()

    def _save_group(self, group_name: str, section_obj: Any) -> None:
        self._settings.beginGroup(group_name)
        try:
            for field_info in fields(section_obj):
                value = getattr(section_obj, field_info.name)
                self._settings.setValue(field_info.name, _serialize_value(value))
        finally:
            self._settings.endGroup()
        self._settings.sync()

    def save_runtime(self) -> None:
        self._save_group("runtime", self.runtime)

    def save_ml(self) -> None:
        self._save_group("ml", self.ml)

    def save_profile(self) -> None:
        self._save_group("profile", self.profile)

    def _set_field(
        self, section_name: str, field_name: str, value: Any, persist: bool = True
    ) -> None:
        section = getattr(self, section_name, None)
        if section is None:
            raise KeyError(f"Unknown settings section: {section_name}")

        for field_info in fields(section):
            if field_info.name != field_name:
                continue
            coerced = _deserialize_value(
                field_info.type, value, getattr(section, field_name)
            )
            setattr(section, field_name, coerced)
            if persist:
                if section_name == "runtime":
                    self.save_runtime()
                elif section_name == "ml":
                    self.save_ml()
                elif section_name == "profile":
                    self.save_profile()
            return

        raise KeyError(f"Unknown field {field_name} in section {section_name}")

    def get(self, key: str) -> Any:
        section_name, field_name = KEY_TO_SECTION_FIELD[key]
        section = getattr(self, section_name)
        return getattr(section, field_name)

    def update(self, key: str, value: Any) -> None:
        if key not in KEY_TO_SECTION_FIELD:
            raise KeyError(f"Unknown setting: {key}")
        section_name, field_name = KEY_TO_SECTION_FIELD[key]
        self._set_field(section_name, field_name, value)

    def update_runtime(self, **overrides: Any) -> None:
        for field_name, value in overrides.items():
            self._set_field("runtime", field_name, value, persist=False)
        self.save_runtime()

    def update_ml(self, **overrides: Any) -> None:
        for field_name, value in overrides.items():
            self._set_field("ml", field_name, value, persist=False)
        self.save_ml()

    def update_profile(self, **overrides: Any) -> None:
        for field_name, value in overrides.items():
            self._set_field("profile", field_name, value, persist=False)
        self.save_profile()


KEY_TO_SECTION_FIELD: Dict[str, Tuple[str, str]] = {
    "ICON_PATH": ("resources", "icon_path"),
    "DEFAULT_DB_NAME": ("resources", "default_db_name"),
    "POSTURE_WEIGHTS": ("ml", "posture_weights"),
    "POSTURE_THRESHOLDS": ("ml", "posture_thresholds"),
    "MIN_DETECTION_CONFIDENCE": ("ml", "min_detection_confidence"),
    "MIN_TRACKING_CONFIDENCE": ("ml", "min_tracking_confidence"),
    "SCORE_BUFFER_SIZE": ("ml", "score_buffer_size"),
    "SCORE_WINDOW_SIZE": ("ml", "score_window_size"),
    "SCORE_THRESHOLD": ("ml", "score_threshold"),
    "MODEL_COMPLEXITY": ("ml", "model_complexity"),
    "DEFAULT_CAMERA_ID": ("runtime", "default_camera_id"),
    "DEFAULT_FPS": ("runtime", "default_fps"),
    "FRAME_WIDTH": ("runtime", "frame_width"),
    "FRAME_HEIGHT": ("runtime", "frame_height"),
    "NOTIFICATION_COOLDOWN": ("runtime", "notification_cooldown"),
    "POOR_POSTURE_THRESHOLD": ("runtime", "poor_posture_threshold"),
    "DEFAULT_POSTURE_MESSAGE": ("runtime", "default_posture_message"),
    "TRACKING_INTERVALS": ("runtime", "tracking_intervals"),
    "TRACKING_DURATION_MINUTES": ("runtime", "tracking_duration_minutes"),
    "ENABLE_DATABASE_LOGGING": ("runtime", "enable_database_logging"),
    "DB_WRITE_INTERVAL_SECONDS": ("runtime", "db_write_interval_seconds"),
    "NOTIFICATIONS_ENABLED": ("runtime", "notifications_enabled"),
    "FOCUS_MODE_ENABLED": ("runtime", "focus_mode_enabled"),
    "HAS_COMPLETED_ONBOARDING": ("profile", "has_completed_onboarding"),
    "BASELINE_POSTURE_SCORE": ("profile", "baseline_posture_score"),
    "BASELINE_NECK_ANGLE": ("profile", "baseline_neck_angle"),
    "BASELINE_SHOULDER_LEVEL": ("profile", "baseline_shoulder_level"),
    "PREFERRED_THEME": ("profile", "preferred_theme"),
    "LANGUAGE_CODE": ("profile", "language_code"),
}


settings_store = SettingsStore()


def get_resource_settings() -> ResourceSettings:
    return settings_store.resources


def get_runtime_settings() -> RuntimeSettings:
    return settings_store.runtime


def get_ml_settings() -> MLTuningSettings:
    return settings_store.ml


def get_profile_settings() -> UserProfileSettings:
    return settings_store.profile


def get_setting(key: str) -> Any:
    if key not in KEY_TO_SECTION_FIELD:
        raise KeyError(f"Unknown setting: {key}")
    return settings_store.get(key)


def update_setting(key: str, value: Any) -> None:
    if key in {"ICON_PATH", "DEFAULT_DB_NAME"}:
        raise KeyError(f"Cannot modify immutable setting: {key}")
    settings_store.update(key, value)


def save_user_settings() -> None:
    settings_store.save_runtime()
    settings_store.save_ml()
    settings_store.save_profile()


def update_runtime_settings(**overrides: Any) -> None:
    settings_store.update_runtime(**overrides)


def update_ml_settings(**overrides: Any) -> None:
    settings_store.update_ml(**overrides)


def update_profile_settings(**overrides: Any) -> None:
    settings_store.update_profile(**overrides)
