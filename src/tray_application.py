from datetime import datetime, timedelta
import os

import cv2
import numpy as np
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

import signal


class PostureTrackerTray(QSystemTrayIcon):
    def __init__(self):
        app = QApplication.instance()
        app.setApplicationName("Posture Corrector")
        icon_path = os.path.join(os.path.dirname(__file__), get_setting("ICON_PATH"))
        app.setWindowIcon(QIcon(icon_path))

        super().__init__()

        self.default_icon_path = os.path.join(
            os.path.dirname(__file__), get_setting("ICON_PATH")
        )

        self.setIcon(QIcon(self.default_icon_path))

        signal.signal(signal.SIGINT, self.signal_handler)

        self.frame_reader = Webcam()
        self.detector = PoseDetector()
        self.scores = ScoreHistory()
        self.notifier = NotificationManager()

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
        self.db_enabled = False

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

        self.toggle_db_action = QAction("Enable Database Logging", menu, checkable=True)
        self.toggle_db_action.setChecked(False)
        self.toggle_db_action.triggered.connect(self.toggle_database)
        menu.addAction(self.toggle_db_action)

        self.settings_action = QAction("Settings", menu)
        self.settings_action.triggered.connect(self.open_settings)
        menu.addAction(self.settings_action)

        menu.addSeparator()
        menu.addAction(
            QAction("Quit Application", menu, triggered=self.quit_application)
        )

        self.setContextMenu(menu)
        self.setVisible(True)

    def create_score_icon(self, score):
        img = np.zeros((64, 64, 4), dtype=np.uint8)
        img[:, :, 3] = 0

        center = (32, 32)
        radius = 30

        for r in range(radius + 8, radius - 1, -1):
            for y in range(64):
                for x in range(64):
                    dist = np.sqrt((x - center[0]) ** 2 + (y - center[1]) ** 2)
                    if dist <= r:
                        alpha = int(255 * (1 - dist / r) * (r - radius + 8) / (8))
                        if r == radius:
                            alpha = min(255, alpha * 1.5)
                        img[y, x, 3] = max(img[y, x, 3], alpha)

        hue = int(score * 60 / 100)
        hue = min(60, max(0, hue))
        rgb_color = cv2.cvtColor(np.uint8([[[hue, 255, 255]]]), cv2.COLOR_HSV2BGR)[0][0]
        color = (int(rgb_color[0]), int(rgb_color[1]), int(rgb_color[2]), 255)
        font = cv2.FONT_HERSHEY_DUPLEX
        text = f"{int(score)}"
        font_scale = 2.0 if len(text) == 1 else (1.5 if len(text) == 2 else 1.2)
        thickness = 3
        text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
        text_x = (64 - text_size[0]) // 2
        text_y = (64 + text_size[1]) // 2
        temp = img.copy()
        shadow_offsets = [(2, 2), (1, 1)]
        shadow_alphas = [120, 180]
        for offset, alpha in zip(shadow_offsets, shadow_alphas):
            shadow_color = (0, 0, 0, alpha)
            cv2.putText(
                temp,
                text,
                (text_x + offset[0], text_y + offset[1]),
                font,
                font_scale,
                shadow_color,
                thickness,
            )

        highlight_color = (255, 255, 255, 100)
        cv2.putText(
            temp,
            text,
            (text_x - 1, text_y - 1),
            font,
            font_scale,
            highlight_color,
            thickness,
        )

        cv2.putText(temp, text, (text_x, text_y), font, font_scale, color, thickness)

        height, width, channel = temp.shape
        bytes_per_line = 4 * width
        q_img = QImage(
            temp.data, width, height, bytes_per_line, QImage.Format.Format_RGBA8888
        )
        return QIcon(QPixmap.fromImage(q_img))

    def toggle_tracking(self):
        if not self.tracking_enabled:
            self.frame_reader.start(callback=self.detector.process_frame)
            self.tracking_enabled = True
            self.toggle_tracking_action.setText("Stop Tracking")
            self.toggle_video_action.setEnabled(True)

            self.setIcon(self.create_score_icon(0))

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

            self.setIcon(QIcon(self.default_icon_path))

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

                self.setIcon(self.create_score_icon(average_score))

                if self.db_enabled:
                    current_time = datetime.now()

                    if (
                        self.tracking_interval > 0
                        and self.last_tracking_time is not None
                        and self.last_db_save is None
                        and (current_time - self.last_tracking_time).total_seconds()
                        <= 60
                    ):
                        self._save_to_db(average_score)

                    elif self.tracking_interval == 0 and (
                        self.last_db_save is None
                        or (current_time - self.last_db_save).total_seconds() >= 60
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
            QTimer.singleShot(60000, self.stop_interval_tracking)
        except Exception as e:
            print(f"Error setting up interval timer: {e}")

    def stop_interval_tracking(self):
        """Stop tracking after interval completes"""
        try:
            if self.tracking_enabled and self.tracking_interval > 0:
                self.toggle_tracking()
        except Exception as e:
            print(f"Error stopping interval tracking: {e}")

    def toggle_database(self, checked):
        self.db_enabled = checked
        if checked:
            self.last_db_save = None

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

        if was_tracking:
            self.toggle_tracking()
