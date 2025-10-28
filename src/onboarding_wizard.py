from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from typing import Dict, Optional

import cv2
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal, pyqtSlot, QObject
from PyQt6.QtGui import QFont, QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWizard,
    QWizardPage,
    QWidget,
    QMessageBox,
    QDialog,
)

from pose_detector import PoseDetector
from util__settings import (
    get_profile_settings,
    get_runtime_settings,
    save_user_settings,
    update_profile_settings,
)


@dataclass
class CalibrationResult:
    posture_score: float
    neck_angle: float
    shoulder_delta: float


class CameraPreviewWidget(QLabel):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setText(self.tr("Camera preview will appear here"))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._camera_id = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_frame)
        self._capture: Optional[cv2.VideoCapture] = None

    def start(self, camera_id: int) -> None:
        self.stop()
        self._camera_id = camera_id
        self._capture = cv2.VideoCapture(self._camera_id)
        if not self._capture.isOpened():
            self.setText(self.tr("Unable to open camera"))
            return
        self._timer.start(40)

    def stop(self) -> None:
        if self._timer.isActive():
            self._timer.stop()
        if self._capture:
            self._capture.release()
            self._capture = None
        self.clear()

    def _update_frame(self) -> None:
        if not self._capture:
            return
        ret, frame = self._capture.read()
        if not ret:
            self.setText(self.tr("Camera feed unavailable"))
            return
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = frame.shape
        image = QImage(frame.data, w, h, ch * w, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(image).scaled(
            self.width(),
            self.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(pixmap)

    def resizeEvent(self, event):  # noqa: N802 - Qt override
        super().resizeEvent(event)
        if self.pixmap():
            self.setPixmap(
                self.pixmap().scaled(
                    self.width(),
                    self.height(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )


class CalibrationWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, camera_id: int, duration_seconds: int = 6) -> None:
        super().__init__()
        self.camera_id = camera_id
        self.duration_seconds = duration_seconds
        self._stop = False

    def cancel(self) -> None:
        self._stop = True

    @pyqtSlot()
    def run(self) -> None:
        capture = None
        try:
            if sys.platform == "darwin":
                capture = cv2.VideoCapture(self.camera_id, cv2.CAP_AVFOUNDATION)
                if not capture.isOpened():
                    capture.release()
                    capture = cv2.VideoCapture(self.camera_id)
            else:
                capture = cv2.VideoCapture(self.camera_id)

            if not capture or not capture.isOpened():
                self.failed.emit(
                    QApplication.translate(
                        "CalibrationWorker", "Unable to access camera"
                    )
                )
                return

            detector = PoseDetector()
            start_time = time.time()
            collected: Dict[str, list] = {
                "posture_score": [],
                "neck_angle": [],
                "shoulder_delta": [],
            }

            while not self._stop and time.time() - start_time < self.duration_seconds:
                ret, frame = capture.read()
                if not ret:
                    time.sleep(0.05)
                    continue
                _, score, result_bundle = detector.process_frame(frame)
                if not result_bundle:
                    time.sleep(0.05)
                    continue
                metrics = (
                    result_bundle.metrics if hasattr(result_bundle, "metrics") else {}
                )
                collected["posture_score"].append(metrics.get("posture_score", score))
                collected["neck_angle"].append(metrics.get("neck_angle", 0.0))
                collected["shoulder_delta"].append(
                    metrics.get("shoulder_vertical_delta", 0.0)
                )
                time.sleep(0.05)

        except Exception as exc:  # noqa: BLE001 - surface worker issues to UI
            self.failed.emit(str(exc))
            return
        finally:
            if capture:
                capture.release()

        if self._stop:
            self.failed.emit(
                QApplication.translate("CalibrationWorker", "Calibration cancelled")
            )
            return

        if not collected["posture_score"]:
            self.failed.emit(
                QApplication.translate("CalibrationWorker", "No posture data captured")
            )
            return

        result = CalibrationResult(
            posture_score=float(
                sum(collected["posture_score"]) / len(collected["posture_score"])
            ),
            neck_angle=float(
                sum(collected["neck_angle"]) / len(collected["neck_angle"])
            ),
            shoulder_delta=float(
                sum(collected["shoulder_delta"]) / len(collected["shoulder_delta"])
            ),
        )
        self.finished.emit(result)


class WelcomePage(QWizardPage):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setTitle(self.tr("Welcome to Posture Coach"))
        self.setSubTitle(
            self.tr("We will calibrate your experience in three quick steps.")
        )

        hero = QLabel(
            self.tr(
                "Great posture starts with awareness. We'll help you dial in camera framing, learn posture cues, and capture your personal baseline so reminders feel tailored."
            )
        )
        hero.setWordWrap(True)
        hero_font = QFont()
        hero_font.setPointSize(hero_font.pointSize() + 2)
        hero_font.setBold(True)
        hero.setFont(hero_font)

        tips = QLabel(
            self.tr(
                "- Find a well-lit space\n"
                "- Position your camera at eye level\n"
                "- Sit naturally - no need to pose!"
            )
        )
        tips.setWordWrap(True)

        layout = QVBoxLayout()
        layout.addWidget(hero)
        layout.addSpacing(12)
        layout.addWidget(tips)
        layout.addStretch(1)
        self.setLayout(layout)


class CameraSetupPage(QWizardPage):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setTitle(self.tr("Align your camera"))
        self.setSubTitle(
            self.tr("Center yourself and ensure your upper body is in frame.")
        )

        runtime = get_runtime_settings()
        self.preview = CameraPreviewWidget()
        self.preview.setMinimumHeight(240)

        guidance = QLabel(
            self.tr(
                "Adjust your seating so your head and shoulders are visible. Use natural lighting when possible."
            )
        )
        guidance.setWordWrap(True)

        layout = QVBoxLayout()
        layout.addWidget(self.preview)
        layout.addSpacing(8)
        layout.addWidget(guidance)
        layout.addStretch(1)
        self.setLayout(layout)

        self._camera_id = runtime.default_camera_id

    def initializePage(self) -> None:  # noqa: N802 - Qt override
        self.preview.start(self._camera_id)

    def cleanupPage(self) -> None:  # noqa: N802 - Qt override
        self.preview.stop()


class CalibrationPage(QWizardPage):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setTitle(self.tr("Capture your baseline"))
        self.setSubTitle(
            self.tr(
                "We'll measure a short sample so posture insights match your neutral stance."
            )
        )

        self.status_label = QLabel(
            self.tr(
                'When you\'re ready, sit comfortably and press "Start calibration".'
            )
        )
        self.status_label.setWordWrap(True)

        self.results_label = QLabel("")
        self.results_label.setWordWrap(True)

        self.start_button = QPushButton(self.tr("Start calibration"))
        self.start_button.clicked.connect(self._begin_calibration)

        layout = QVBoxLayout()
        layout.addWidget(self.status_label)
        layout.addSpacing(12)
        layout.addWidget(self.start_button)
        layout.addSpacing(12)
        layout.addWidget(self.results_label)
        layout.addStretch(1)
        self.setLayout(layout)

        self._thread: Optional[QThread] = None
        self._worker: Optional[CalibrationWorker] = None
        self._metrics: Optional[CalibrationResult] = None
        self._timeout: Optional[QTimer] = None

    def _begin_calibration(self) -> None:
        if self._thread and self._thread.isRunning():
            return
        self.start_button.setEnabled(False)
        self.status_label.setText(
            self.tr("Collecting data... Keep still for six seconds.")
        )

        runtime = get_runtime_settings()
        worker = CalibrationWorker(runtime.default_camera_id)
        thread = QThread(self)
        worker.moveToThread(thread)

        worker.finished.connect(self._handle_success)
        worker.failed.connect(self._handle_failure)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.started.connect(worker.run)

        self._worker = worker
        self._thread = thread
        thread.start()

        if not self._timeout:
            self._timeout = QTimer(self)
            self._timeout.setSingleShot(True)
            self._timeout.timeout.connect(self._handle_timeout)
        self._timeout.start((worker.duration_seconds + 2) * 1000)

    def _handle_success(self, result: CalibrationResult) -> None:
        self._metrics = result
        self.start_button.setEnabled(True)
        self.status_label.setText(self.tr("Baseline captured."))
        self.results_label.setText(
            self.tr(
                "- Average posture score: {score:.1f}%\n"
                "- Neck angle: {neck:.1f} deg\n"
                "- Shoulder balance delta: {delta:.3f}"
            ).format(
                score=result.posture_score,
                neck=result.neck_angle,
                delta=result.shoulder_delta,
            )
        )
        self._cleanup_worker()
        self.completeChanged.emit()

    def _handle_failure(self, message: str) -> None:
        self.start_button.setEnabled(True)
        self.status_label.setText(self.tr("Calibration failed"))
        QMessageBox.warning(self, self.tr("Calibration"), message)
        self._cleanup_worker()

    def _handle_timeout(self) -> None:
        if self._thread and self._thread.isRunning() and self._worker:
            self._worker.cancel()
        else:
            self._cleanup_worker()

    def _cleanup_worker(self) -> None:
        if self._timeout and self._timeout.isActive():
            self._timeout.stop()
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(2000)
        self._thread = None
        self._worker = None

    def isComplete(self) -> bool:  # noqa: N802 - Qt override
        return self._metrics is not None

    def metrics(self) -> Optional[CalibrationResult]:
        return self._metrics


class OnboardingWizard(QWizard):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Posture Coach Setup"))
        self.setOption(QWizard.WizardOption.IndependentPages, False)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setMinimumWidth(500)

        self.welcome_page = WelcomePage()
        self.camera_page = CameraSetupPage()
        self.calibration_page = CalibrationPage()

        self.addPage(self.welcome_page)
        self.addPage(self.camera_page)
        self.addPage(self.calibration_page)

        self._metrics: Optional[CalibrationResult] = None

    def accept(self) -> None:
        metrics = self.calibration_page.metrics()
        if metrics:
            update_profile_settings(
                has_completed_onboarding=True,
                baseline_posture_score=metrics.posture_score,
                baseline_neck_angle=metrics.neck_angle,
                baseline_shoulder_level=metrics.shoulder_delta,
            )
            save_user_settings()
            self._metrics = metrics
        super().accept()

    def collected_metrics(self) -> Optional[CalibrationResult]:
        return self._metrics


def run_onboarding_if_needed(parent: Optional[QWidget] = None) -> bool:
    profile = get_profile_settings()
    if profile.has_completed_onboarding:
        return False
    wizard = OnboardingWizard(parent)
    return wizard.exec() == QDialog.DialogCode.Accepted
