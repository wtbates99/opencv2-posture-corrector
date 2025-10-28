from collections import deque
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import cv2
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import (
    QAction,
    QActionGroup,
    QIcon,
    QImage,
    QPalette,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QColor,
)
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QMenu,
    QSystemTrayIcon,
    QVBoxLayout,
    QStyle,
    QSizePolicy,
    QFrame,
    QWidget,
)
from database import Database
from notifications import Notifications
from onboarding_wizard import run_onboarding_if_needed
from pose_detector import PoseDetector, PoseDetectionResult
from util__scores import Scores
from webcam import Webcam
from util__settings import (
    get_resource_settings,
    get_runtime_settings,
    get_profile_settings,
    save_user_settings,
    update_runtime_settings,
)
from settings_interface import SettingsInterface
from util__create_score_icon import create_score_icon
import signal


class SparklineWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.values: List[float] = []
        self.line_color = QColor("#2e7dff")
        self.fill_color = QColor(46, 125, 255, 80)
        self.background_color = QColor("#ffffff")
        self.setMinimumHeight(80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_colors(self, line: QColor, fill: QColor, background: QColor) -> None:
        self.line_color = line
        self.fill_color = fill
        self.background_color = background
        self.update()

    def update_values(self, values: List[float]) -> None:
        self.values = list(values)
        self.update()

    def paintEvent(self, event):  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(4, 4, -4, -4)
        painter.fillRect(rect, self.background_color)

        if len(self.values) < 2:
            painter.setPen(QPen(self.line_color, 2.0))
            painter.drawLine(
                rect.left(), rect.center().y(), rect.right(), rect.center().y()
            )
            return

        min_val = min(self.values)
        max_val = max(self.values)
        if abs(max_val - min_val) < 1e-5:
            min_val -= 1.0
            max_val += 1.0

        path = QPainterPath()
        for index, value in enumerate(self.values):
            x = rect.left() + (index / (len(self.values) - 1)) * rect.width()
            normalized = (value - min_val) / (max_val - min_val)
            y = rect.bottom() - normalized * rect.height()
            if index == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        fill_path = QPainterPath(path)
        fill_path.lineTo(rect.right(), rect.bottom())
        fill_path.lineTo(rect.left(), rect.bottom())
        fill_path.closeSubpath()

        painter.fillPath(fill_path, self.fill_color)
        painter.setPen(QPen(self.line_color, 2.0))
        painter.drawPath(path)


class PostureDashboard(QDialog):
    def __init__(
        self,
        baseline_score: float,
        preferred_theme: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.recent_scores: deque[float] = deque(maxlen=120)
        self.baseline_score = baseline_score

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        self.card = QFrame()
        self.card.setObjectName("dashboardCard")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        self.video_label = QLabel(self.tr("Waiting for frames..."))
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumSize(560, 320)
        self.video_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self.sparkline = SparklineWidget()

        self.coaching_label = QLabel(
            self.tr("Settle into a neutral posture while we gather readings.")
        )
        self.coaching_label.setWordWrap(True)

        card_layout.addWidget(self.video_label)
        card_layout.addWidget(self.sparkline)
        card_layout.addWidget(self.coaching_label)

        outer_layout.addWidget(self.card)
        self._apply_theme(preferred_theme)

    def _apply_theme(self, preference: str) -> None:
        palette = QApplication.instance().palette()
        if preference == "dark":
            is_dark = True
        elif preference == "light":
            is_dark = False
        else:
            window_color = palette.color(QPalette.ColorRole.Window)
            luminance = (
                0.299 * window_color.red()
                + 0.587 * window_color.green()
                + 0.114 * window_color.blue()
            )
            is_dark = luminance < 128

        if is_dark:
            background = QColor("#202124")
            foreground = QColor("#f1f3f4")
            accent = QColor("#8ab4f8")
            fill = QColor(138, 180, 248, 90)
        else:
            background = QColor("#ffffff")
            foreground = QColor("#1a1c23")
            accent = QColor("#2e7dff")
            fill = QColor(46, 125, 255, 80)

        self.card.setStyleSheet(
            "QFrame#dashboardCard {"
            f"background-color: {background.name()};"
            "border-radius: 16px;"
            "border: 1px solid rgba(0,0,0,30);"
            "}"
            f"QLabel {{ color: {foreground.name()}; }}"
        )
        self.coaching_label.setStyleSheet(
            f"color: {foreground.name()}; font-weight: 600;"
        )
        self.sparkline.set_colors(accent, fill, background)

    def update_frame(self, frame) -> None:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        image = QImage(rgb_frame.data, w, h, ch * w, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(image)
        ratio = self.devicePixelRatioF()
        pixmap.setDevicePixelRatio(ratio)
        scaled = pixmap.scaled(
            int(self.video_label.width() * ratio),
            int(self.video_label.height() * ratio),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.video_label.setPixmap(scaled)

    def update_score(
        self, score: float, metrics: Optional[Dict[str, float]] = None
    ) -> None:
        self.recent_scores.append(score)
        self.sparkline.update_values(list(self.recent_scores))
        self._update_coaching_text(score, metrics)

    def _update_coaching_text(
        self, score: float, metrics: Optional[Dict[str, float]]
    ) -> None:
        if score >= max(self.baseline_score - 5, 70):
            message = self.tr(
                "Nice alignment! Keep a relaxed breath and soft shoulders."
            )
        else:
            cues: List[str] = []
            if metrics:
                if metrics.get("neck_angle", 0.0) > 15.0:
                    cues.append(
                        self.tr("Gently draw your head back over your shoulders.")
                    )
                if metrics.get("shoulder_vertical_delta", 0.0) > 0.05:
                    cues.append(self.tr("Level your shoulders to center your posture."))
                if metrics.get("spine_angle", 0.0) > 10.0:
                    cues.append(self.tr("Lengthen through your spine and sit tall."))
            if not cues:
                cues.append(
                    self.tr(
                        "Reset by rolling your shoulders back and opening your chest."
                    )
                )
            message = " ".join(cues[:2])
        self.coaching_label.setText(message)


class PostureTrackerTray(QSystemTrayIcon):
    def __init__(self):
        """Initialize the PostureTrackerTray system tray application."""
        super().__init__()
        self._initialize_application()
        self._initialize_components()
        self._run_onboarding_if_needed()
        self._setup_tray_menu()
        self._setup_timers()
        self._setup_signal_handling()

    def _initialize_application(self):
        """Set up the QApplication instance and basic properties."""
        app = QApplication.instance()
        app.setApplicationName("Posture Corrector")
        resource_settings = get_resource_settings()
        self.icon_path = resource_settings.icon_path
        app.setWindowIcon(QIcon(self.icon_path))
        self.setIcon(QIcon(self.icon_path))

    def _initialize_components(self):
        """Initialize core components like webcam, detector, and managers."""
        self.frame_reader = Webcam()
        self.detector = PoseDetector()
        self.scores = Scores()
        self.notifier = Notifications(icon_path=self.icon_path)
        resource_settings = get_resource_settings()
        runtime_settings = get_runtime_settings()
        self.db = Database(resource_settings.default_db_name)
        self.db_enabled = runtime_settings.enable_database_logging

        self.tracking_enabled = False
        self.video_window = None
        self.current_score = 0
        self.tracking_interval = 0
        self.last_tracking_time = None
        self.last_db_save = None

    def _run_onboarding_if_needed(self) -> None:
        if run_onboarding_if_needed() is True:
            self.reload_settings()

    def _setup_tray_menu(self):
        """Configure the system tray context menu."""
        menu = QMenu()
        style = QApplication.style()

        self.toggle_tracking_action = QAction(
            style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay),
            "Start Tracking",
            self,
        )
        self.toggle_tracking_action.setShortcut("Ctrl+Shift+T")
        self.toggle_tracking_action.triggered.connect(self.toggle_tracking)
        self.toggle_tracking_action.setShortcutVisibleInContextMenu(True)

        self.toggle_video_action = QAction(
            style.standardIcon(QStyle.StandardPixmap.SP_DesktopIcon),
            "Show Dashboard",
            self,
        )
        self.toggle_video_action.setShortcut("Ctrl+Shift+D")
        self.toggle_video_action.setShortcutVisibleInContextMenu(True)
        self.toggle_video_action.triggered.connect(self.toggle_video)
        self.toggle_video_action.setEnabled(False)

        menu.addSection("Session")
        menu.addAction(self.toggle_tracking_action)
        menu.addAction(self.toggle_video_action)

        # Store the interval menu and its action as instance variables
        self.interval_menu = self._create_interval_menu(menu)
        self.interval_menu.setIcon(
            style.standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        )
        self.interval_menu_action = menu.addMenu(self.interval_menu)

        menu.addSection("Quick toggles")
        runtime = get_runtime_settings()
        self.notifications_toggle_action = QAction(
            style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation),
            "Notifications",
            self,
            checkable=True,
        )
        self.notifications_toggle_action.setChecked(runtime.notifications_enabled)
        self.notifications_toggle_action.triggered.connect(self._toggle_notifications)
        self._set_notification_action_label(runtime.notifications_enabled)

        self.logging_toggle_action = QAction(
            style.standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon),
            "Database Logging",
            self,
            checkable=True,
        )
        self.logging_toggle_action.setChecked(runtime.enable_database_logging)
        self.logging_toggle_action.triggered.connect(self._toggle_logging)
        self._set_logging_action_label(runtime.enable_database_logging)

        self.focus_mode_action = QAction(
            style.standardIcon(QStyle.StandardPixmap.SP_DialogNoButton),
            "Focus Mode",
            self,
            checkable=True,
        )
        self.focus_mode_action.setChecked(runtime.focus_mode_enabled)
        self.focus_mode_action.triggered.connect(self._toggle_focus_mode)
        self._set_focus_action_label(runtime.focus_mode_enabled)

        menu.addAction(self.notifications_toggle_action)
        menu.addAction(self.logging_toggle_action)
        menu.addAction(self.focus_mode_action)

        menu.addSeparator()

        self.settings_action = QAction(
            style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView),
            "Settings",
            menu,
        )
        self.settings_action.setShortcut("Ctrl+,")
        self.settings_action.setShortcutVisibleInContextMenu(True)
        self.settings_action.triggered.connect(self.open_settings)
        menu.addAction(self.settings_action)

        menu.addSeparator()
        quit_action = QAction(
            style.standardIcon(QStyle.StandardPixmap.SP_TitleBarCloseButton),
            "Quit",
            menu,
            triggered=self.quit_application,
        )
        quit_action.setShortcut("Ctrl+Q")
        quit_action.setShortcutVisibleInContextMenu(True)
        menu.addAction(quit_action)

        self.setContextMenu(menu)
        self.setVisible(True)

    def _create_interval_menu(self, parent_menu):
        """Create the tracking interval submenu."""
        interval_menu = QMenu("Tracking Interval", parent_menu)
        interval_group = QActionGroup(interval_menu)
        interval_group.setExclusive(True)

        tracking_intervals = get_runtime_settings().tracking_intervals
        for label, minutes in tracking_intervals.items():
            action = QAction(label, interval_menu, checkable=True)
            action.setData(minutes)
            action.triggered.connect(lambda checked, m=minutes: self.set_interval(m))
            interval_menu.addAction(action)
            interval_group.addAction(action)
            if minutes == 0:
                action.setChecked(True)

        return interval_menu

    def _setup_timers(self):
        """Initialize timers for tracking updates and interval checks."""
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_tracking)
        self.timer.start(100)

        self.interval_timer = QTimer()
        self.interval_timer.timeout.connect(self.check_interval)
        self.interval_timer.start(1000)

    def _setup_signal_handling(self):
        """Configure signal handling for graceful shutdown."""
        signal.signal(signal.SIGINT, self.signal_handler)

    def toggle_tracking(self):
        """Toggle posture tracking on or off."""
        if not self.tracking_enabled:
            self._start_tracking()
        else:
            self._stop_tracking()

    def _start_tracking(self):
        """Begin tracking posture."""
        self.frame_reader.start(callback=self.detector.process_frame)
        self.tracking_enabled = True
        self.toggle_tracking_action.setText("Stop Tracking")
        self.toggle_video_action.setEnabled(True)
        self.setIcon(create_score_icon(0))

    def _stop_tracking(self):
        """Stop tracking posture."""
        self.frame_reader.stop()
        self.tracking_enabled = False
        self.toggle_tracking_action.setText("Start Tracking")
        self.toggle_video_action.setEnabled(False)
        self.toggle_video_action.setText("Show Dashboard")

        if self.video_window:
            self.video_window.close()
            self.video_window = None

        self.setIcon(QIcon(self.icon_path))

    def toggle_video(self):
        """Show or hide the video display window."""
        if self.video_window:
            self.video_window.close()
            self.video_window = None
            self.toggle_video_action.setText("Show Dashboard")
        else:
            self._create_video_window()
            self.toggle_video_action.setText("Hide Dashboard")

    def _create_video_window(self):
        """Create and display the video window."""
        profile = get_profile_settings()
        self.video_window = PostureDashboard(
            baseline_score=profile.baseline_posture_score,
            preferred_theme=profile.preferred_theme,
        )
        self.video_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.video_window.setWindowTitle(self.tr("Posture Dashboard"))
        self.video_window.destroyed.connect(self.on_video_window_closed)
        self.video_window.resize(720, 520)
        self.video_window.show()

    def update_tracking(self):
        """Process the latest frame and update tracking state."""
        if not self.tracking_enabled:
            return

        latest_frame = self.frame_reader.get_latest_frame()
        if not latest_frame or not latest_frame[0] is not None:
            return

        frame, score = latest_frame
        self.scores.add_score(score)
        average_score = self.scores.get_average_score()
        self.setIcon(create_score_icon(average_score))

        results_bundle = self.frame_reader.get_latest_pose_results()
        metrics: Optional[Dict[str, float]] = None
        if isinstance(results_bundle, PoseDetectionResult):
            metrics = results_bundle.metrics

        if self.db_enabled:
            self._save_to_db(average_score, results_bundle)

        self.notifier.check_and_notify(average_score)

        if isinstance(self.video_window, PostureDashboard):
            self.video_window.update_frame(frame)
            self.video_window.update_score(average_score, metrics)

    def _toggle_notifications(self, checked: bool) -> None:
        update_runtime_settings(notifications_enabled=checked)
        save_user_settings()
        self._set_notification_action_label(checked)

    def _toggle_logging(self, checked: bool) -> None:
        update_runtime_settings(enable_database_logging=checked)
        save_user_settings()
        self.db_enabled = checked
        self._set_logging_action_label(checked)

    def _toggle_focus_mode(self, checked: bool) -> None:
        update_runtime_settings(focus_mode_enabled=checked)
        save_user_settings()
        self._set_focus_action_label(checked)

    def _set_notification_action_label(self, enabled: bool) -> None:
        if hasattr(self, "notifications_toggle_action"):
            label = "Notifications (On)" if enabled else "Notifications (Off)"
            self.notifications_toggle_action.setText(label)

    def _set_logging_action_label(self, enabled: bool) -> None:
        if hasattr(self, "logging_toggle_action"):
            label = "Database Logging (On)" if enabled else "Database Logging (Off)"
            self.logging_toggle_action.setText(label)

    def _set_focus_action_label(self, enabled: bool) -> None:
        if hasattr(self, "focus_mode_action"):
            label = "Focus Mode (On)" if enabled else "Focus Mode (Off)"
            self.focus_mode_action.setText(label)

    def _save_to_db(
        self,
        average_score: float,
        results_bundle: Optional[PoseDetectionResult] = None,
    ) -> None:
        """Save pose data to the database if conditions are met."""
        current_time = datetime.now()
        db_interval_seconds = get_runtime_settings().db_write_interval_seconds

        should_save = (
            self.tracking_interval > 0
            and self.last_tracking_time
            and self.last_db_save is None
            and (current_time - self.last_tracking_time).total_seconds()
            <= db_interval_seconds
        ) or (
            self.tracking_interval == 0
            and (
                self.last_db_save is None
                or (current_time - self.last_db_save).total_seconds()
                >= db_interval_seconds
            )
        )

        if results_bundle is None:
            results_bundle = self.frame_reader.get_latest_pose_results()
        if not should_save or not results_bundle:
            return
        results = (
            results_bundle.results
            if hasattr(results_bundle, "results")
            else results_bundle
        )
        if results and getattr(results, "pose_landmarks", None):
            self.db.save_pose_data(results.pose_landmarks, average_score)
            self.last_db_save = current_time

    def set_interval(self, minutes):
        """Set the tracking interval in minutes."""
        self.tracking_interval = minutes
        if minutes > 0:
            self.notifier.set_interval_message(
                f"Checking posture every {minutes} minutes"
            )
        self.last_tracking_time = None if minutes > 0 else self.last_tracking_time
        if minutes == 0 and not self.tracking_enabled:
            self.toggle_tracking()
        elif minutes > 0 and self.tracking_enabled:
            self.toggle_tracking()

    def check_interval(self):
        """Check if it's time to start a new tracking interval."""
        if self.tracking_interval <= 0:
            return

        current_time = datetime.now()
        if not self.last_tracking_time:
            self.last_tracking_time = current_time
            self.start_interval_tracking()
        elif current_time - self.last_tracking_time >= timedelta(
            minutes=self.tracking_interval
        ):
            self.start_interval_tracking()

    def start_interval_tracking(self):
        self.last_tracking_time = datetime.now()
        self.last_db_save = None
        if not self.tracking_enabled:
            self.toggle_tracking()
        tracking_duration_minutes = get_runtime_settings().tracking_duration_minutes
        QTimer.singleShot(
            tracking_duration_minutes * 60 * 1000, self.stop_interval_tracking
        )

    def stop_interval_tracking(self):
        """Stop tracking after the interval ends."""
        if self.tracking_enabled and self.tracking_interval > 0:
            self.toggle_tracking()

    def open_settings(self):
        """Open the settings dialog and reload settings if accepted."""
        if SettingsInterface().exec() == QDialog.DialogCode.Accepted:
            self.reload_settings()

    def reload_settings(self):
        """Reload settings and reinitialize components."""
        was_tracking = self.tracking_enabled
        previous_interval = self.tracking_interval

        if was_tracking:
            self.toggle_tracking()

        self.frame_reader = Webcam()
        self.detector = PoseDetector()
        self.scores = Scores()
        runtime = get_runtime_settings()
        self.db_enabled = runtime.enable_database_logging
        if hasattr(self, "notifications_toggle_action"):
            self.notifications_toggle_action.setChecked(runtime.notifications_enabled)
            self._set_notification_action_label(runtime.notifications_enabled)
        if hasattr(self, "logging_toggle_action"):
            self.logging_toggle_action.setChecked(runtime.enable_database_logging)
            self._set_logging_action_label(runtime.enable_database_logging)
        if hasattr(self, "focus_mode_action"):
            self.focus_mode_action.setChecked(runtime.focus_mode_enabled)
            self._set_focus_action_label(runtime.focus_mode_enabled)
        self.last_db_save = None if self.db_enabled else self.last_db_save

        menu = self.contextMenu()
        if menu:
            menu.removeAction(self.interval_menu_action)
            self.interval_menu = self._create_interval_menu(menu)
            self.interval_menu_action = menu.insertMenu(
                self.toggle_tracking_action, self.interval_menu
            )

        if was_tracking:
            self.toggle_tracking()

        if (
            was_tracking
            and previous_interval != self.tracking_interval
            and self.tracking_interval > 0
        ):
            self.notifier.set_interval_message(
                f"Checking posture every {self.tracking_interval} minutes"
            )

    def on_video_window_closed(self):
        """Handle video window closure."""
        self.video_window = None
        self.toggle_video_action.setText("Show Dashboard")

    def quit_application(self):
        """Clean up resources and exit the application."""
        if self.tracking_enabled:
            self.toggle_tracking()

        if self.video_window:
            self.video_window.close()
            self.video_window = None

        self.timer.stop()
        self.interval_timer.stop()
        if hasattr(self, "db"):
            self.db.close()

        self.hide()
        QApplication.instance().quit()

    def signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        self.quit_application()
