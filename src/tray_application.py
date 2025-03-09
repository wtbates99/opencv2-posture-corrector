from datetime import datetime, timedelta

import cv2
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QActionGroup, QIcon, QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QMenu,
    QSystemTrayIcon,
    QVBoxLayout,
)

from db_manager import DBManager
from notifications import NotificationManager
from pose_detector import PoseDetector
from score_history import ScoreHistory
from webcam import Webcam
from settings import get_setting
from settings_dialog import SettingsDialog
import utils.create_score_icon

import signal


class PostureTrackerTray(QSystemTrayIcon):
    def __init__(self):
        app = QApplication.instance()
        app.setApplicationName("Posture Corrector")
        self.icon_path = get_setting("ICON_PATH")
        app.setWindowIcon(QIcon(self.icon_path))

        super().__init__()

        self.setIcon(QIcon(self.icon_path))

        signal.signal(signal.SIGINT, self.signal_handler)

        self.frame_reader = Webcam()
        self.detector = PoseDetector()
        self.scores = ScoreHistory()
        self.notifier = NotificationManager(icon_path=self.icon_path)

        self.tracking_enabled = False
        self.video_window = None
        self.current_score = 0
        self.tracking_interval = 0
        self.last_tracking_time = None
        self.interval_timer = QTimer()
        self.interval_timer.timeout.connect(self.check_interval)
        self.interval_timer.start(1000)

        self.db = DBManager(get_setting("DEFAULT_DB_NAME"))
        self.last_db_save = None
        self.db_enabled = get_setting("ENABLE_DATABASE_LOGGING")

        self.setup_tray()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_tracking)
        self.timer.start(100)

    def setup_tray(self):
        menu = QMenu()

        self.toggle_tracking_action = QAction("Start Tracking")
        self.toggle_tracking_action.triggered.connect(self.toggle_tracking)

        self.toggle_video_action = QAction("Show Video")
        self.toggle_video_action.triggered.connect(self.toggle_video)
        self.toggle_video_action.setEnabled(False)

        interval_menu = QMenu("Tracking Interval", menu)
        interval_group = QActionGroup(interval_menu)
        interval_group.setExclusive(True)

        tracking_intervals = get_setting("TRACKING_INTERVALS")
        for label, minutes in tracking_intervals.items():
            action = QAction(label, interval_menu, checkable=True)
            action.setData(minutes)
            action.triggered.connect(lambda checked, m=minutes: self.set_interval(m))
            interval_menu.addAction(action)
            interval_group.addAction(action)
            if minutes == 0:
                action.setChecked(True)

        menu.addMenu(interval_menu)
        menu.addAction(self.toggle_tracking_action)
        menu.addAction(self.toggle_video_action)

        self.settings_action = QAction("Settings", menu)
        self.settings_action.triggered.connect(self.open_settings)
        menu.addAction(self.settings_action)

        menu.addSeparator()
        menu.addAction(
            QAction("Quit Application", menu, triggered=self.quit_application)
        )

        self.setContextMenu(menu)
        self.setVisible(True)

    def toggle_tracking(self):
        if not self.tracking_enabled:
            self.frame_reader.start(callback=self.detector.process_frame)
            self.tracking_enabled = True
            self.toggle_tracking_action.setText("Stop Tracking")
            self.toggle_video_action.setEnabled(True)

            self.setIcon(utils.create_score_icon(0))

            if self.tracking_interval > 0:
                self.notifier.set_interval_message(
                    f"Checking posture every {self.tracking_interval} minutes"
                )
        else:
            self.frame_reader.stop()
            self.tracking_enabled = False
            self.toggle_tracking_action.setText("Start Tracking")
            self.toggle_video_action.setEnabled(False)
            self.toggle_video_action.setText("Show Video")

            if self.video_window:
                cv2.destroyWindow("Posture Detection")
                self.video_window = None

            self.setIcon(QIcon(self.icon_path))

    def toggle_video(self):
        if self.video_window:
            self.video_window.close()
            self.video_window = None
            self.toggle_video_action.setText("Show Video")
        else:
            self.toggle_video_action.setText("Hide Video")

            self.video_window = QDialog()
            self.video_window.setWindowTitle("Posture Detection")
            self.video_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

            self.video_label = QLabel("Waiting for first frame...")
            self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            layout = QVBoxLayout()
            layout.addWidget(self.video_label)
            self.video_window.setLayout(layout)

            self.video_window.destroyed.connect(self.on_video_window_closed)
            self.video_window.resize(640, 480)
            self.video_window.show()

    def update_tracking(self):
        if self.tracking_enabled:
            frame, score = self.frame_reader.get_latest_frame()
            if frame is not None:
                self.scores.add_score(score)
                average_score = self.scores.get_average_score()

                self.setIcon(utils.create_score_icon(average_score))

                if self.db_enabled:
                    current_time = datetime.now()
                    db_interval_seconds = get_setting(
                        "DB_WRITE_INTERVAL_SECONDS", 900
                    )  # Default to 15 minutes if not set

                    if (
                        self.tracking_interval > 0
                        and self.last_tracking_time is not None
                        and self.last_db_save is None
                        and (current_time - self.last_tracking_time).total_seconds()
                        <= db_interval_seconds
                    ):
                        self._save_to_db(average_score)

                    elif self.tracking_interval == 0 and (
                        self.last_db_save is None
                        or (current_time - self.last_db_save).total_seconds()
                        >= db_interval_seconds
                    ):
                        self._save_to_db(average_score)

                self.notifier.check_and_notify(average_score)

                if self.video_window:
                    self.show_video_in_pyqt(frame)

    def _save_to_db(self, average_score):
        """Helper method to save pose data to database"""
        results = self.frame_reader.get_latest_pose_results()
        if results and results.pose_landmarks:
            self.db.save_pose_data(results.pose_landmarks, average_score)
            self.last_db_save = datetime.now()

    def quit_application(self):
        """Clean up application resources and quit"""
        try:
            if self.tracking_enabled:
                self.toggle_tracking()

            if self.video_window:
                cv2.destroyAllWindows()
                self.video_window = None

            if hasattr(self, "db"):
                self.db.close()

            if hasattr(self, "timer"):
                self.timer.stop()
            if hasattr(self, "interval_timer"):
                self.interval_timer.stop()

            self.hide()

            QApplication.instance().quit()
        except Exception as e:
            print(f"Error during cleanup: {e}")
            import sys

            sys.exit(1)

    def set_interval(self, minutes):
        self.tracking_interval = minutes
        if minutes == 0:
            if not self.tracking_enabled:
                self.toggle_tracking()
        else:
            self.last_tracking_time = None
            if self.tracking_enabled:
                self.toggle_tracking()

    def check_interval(self):
        if self.tracking_interval <= 0:
            return

        current_time = datetime.now()

        if self.last_tracking_time is None:
            self.last_tracking_time = current_time
            self.start_interval_tracking()
            return

        if current_time - self.last_tracking_time >= timedelta(
            minutes=self.tracking_interval
        ):
            self.start_interval_tracking()

    def start_interval_tracking(self):
        """Start tracking posture for a fixed interval"""
        self.last_tracking_time = datetime.now()
        self.last_db_save = None

        if not self.tracking_enabled:
            self.toggle_tracking()

        try:
            QTimer.singleShot(900000, self.stop_interval_tracking)
        except Exception as e:
            print(f"Error setting up interval timer: {e}")

    def stop_interval_tracking(self):
        """Stop tracking after interval completes"""
        try:
            if self.tracking_enabled and self.tracking_interval > 0:
                self.toggle_tracking()
        except Exception as e:
            print(f"Error stopping interval tracking: {e}")

    def signal_handler(self, signum, frame):
        self.quit_application()

    def show_video_in_pyqt(self, frame):
        if not self.video_window or not isinstance(self.video_window, QDialog):
            self.video_window = QDialog()
            self.video_window.setWindowTitle("Posture Detection")
            self.video_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

            self.video_label = QLabel()
            self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            layout = QVBoxLayout()
            layout.addWidget(self.video_label)
            self.video_window.setLayout(layout)

            self.video_window.destroyed.connect(self.on_video_window_closed)
            self.video_window.show()

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        q_img = QImage(
            rgb_frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888
        )

        pixmap = QPixmap.fromImage(q_img)
        self.video_label.setPixmap(pixmap)

    def on_video_window_closed(self, *_):
        self.video_window = None
        self.toggle_video_action.setText("Show Video")

    def _create_pyqt_video_dialog(self):
        if not self.video_window:
            self.video_window = QDialog()
            self.video_window.setWindowTitle("Posture Detection")
            self.video_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

            self.video_label = QLabel()
            self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            layout = QVBoxLayout()
            layout.addWidget(self.video_label)
            self.video_window.setLayout(layout)

            self.video_window.destroyed.connect(self.on_video_window_closed)
            self.video_window.resize(640, 480)
            self.video_window.show()

    def open_settings(self):
        dialog = SettingsDialog()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.reload_settings()

    def reload_settings(self):
        was_tracking = self.tracking_enabled
        if was_tracking:
            self.toggle_tracking()

        self.frame_reader = Webcam()

        self.setup_tray()

        self.db_enabled = get_setting("ENABLE_DATABASE_LOGGING")
        if self.db_enabled:
            self.last_db_save = None

        if was_tracking:
            self.toggle_tracking()
