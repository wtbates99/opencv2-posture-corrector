from typing import Dict, List

from PyQt6.QtWidgets import (
    QDialog,
    QTabWidget,
    QWidget,
    QFormLayout,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QDialogButtonBox,
    QLabel,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QCheckBox,
    QGroupBox,
)
import cv2

from util__settings import (
    get_ml_settings,
    get_runtime_settings,
    save_user_settings,
    update_ml_settings,
    update_runtime_settings,
)


class SettingsInterface(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Customizable Settings")
        self.resize(500, 400)
        self.tabs = QTabWidget()

        # Create tabs
        self.camera_tab = QWidget()
        self.general_tab = QWidget()
        self.tracking_tab = QWidget()
        self.advanced_tab = QWidget()

        self.init_camera_tab()
        self.init_general_tab()
        self.init_tracking_tab()
        self.init_advanced_tab()

        self.tabs.addTab(self.camera_tab, "Camera")
        self.tabs.addTab(self.general_tab, "General")
        self.tabs.addTab(self.tracking_tab, "Tracking")

        self.show_advanced_checkbox = QCheckBox("Show advanced options")
        self.show_advanced_checkbox.setChecked(False)
        self.show_advanced_checkbox.toggled.connect(self.toggle_advanced_tab)

        # Dialog buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.tabs)
        advanced_toggle_row = QHBoxLayout()
        advanced_toggle_row.addStretch(1)
        advanced_toggle_row.addWidget(self.show_advanced_checkbox)
        main_layout.addLayout(advanced_toggle_row)
        main_layout.addWidget(self.button_box)
        self.setLayout(main_layout)

    def init_camera_tab(self):
        layout = QFormLayout()
        # Default Camera selection using QComboBox with available cameras.
        self.camera_combo = QComboBox()
        cameras = self.get_available_cameras()
        runtime_settings = get_runtime_settings()
        if cameras:
            for cam_id, cam_name in cameras:
                self.camera_combo.addItem(cam_name, cam_id)
            current_cam = runtime_settings.default_camera_id
            index = self.camera_combo.findData(current_cam)
            if index != -1:
                self.camera_combo.setCurrentIndex(index)
        else:
            self.camera_combo.addItem("No Camera Found", -1)
            self.camera_combo.setEnabled(False)
        layout.addRow("Default Camera:", self.camera_combo)

        # Frames Per Second setting
        self.fps_spinbox = QSpinBox()
        self.fps_spinbox.setRange(1, 120)
        self.fps_spinbox.setValue(runtime_settings.default_fps)
        layout.addRow("Frames Per Second:", self.fps_spinbox)

        # Frame width setting
        self.width_spinbox = QSpinBox()
        self.width_spinbox.setRange(100, 10000)
        self.width_spinbox.setValue(runtime_settings.frame_width)
        layout.addRow("Frame Width:", self.width_spinbox)

        # Frame height setting
        self.height_spinbox = QSpinBox()
        self.height_spinbox.setRange(100, 10000)
        self.height_spinbox.setValue(runtime_settings.frame_height)
        layout.addRow("Frame Height:", self.height_spinbox)

        self.camera_tab.setLayout(layout)

    def init_general_tab(self):
        layout = QFormLayout()
        runtime_settings = get_runtime_settings()

        # Notification Cooldown setting
        self.cooldown_spinbox = QSpinBox()
        self.cooldown_spinbox.setRange(1, 3600)
        self.cooldown_spinbox.setValue(runtime_settings.notification_cooldown)
        layout.addRow("Notification Cooldown (sec):", self.cooldown_spinbox)

        # Poor Posture Threshold setting
        self.poor_posture_spinbox = QSpinBox()
        self.poor_posture_spinbox.setRange(1, 100)
        self.poor_posture_spinbox.setValue(runtime_settings.poor_posture_threshold)
        layout.addRow("Poor Posture Threshold:", self.poor_posture_spinbox)

        # Default Posture Message setting
        self.posture_message_lineedit = QLineEdit()
        self.posture_message_lineedit.setText(runtime_settings.default_posture_message)
        layout.addRow("Posture Message:", self.posture_message_lineedit)

        # Add this block:
        self.db_logging_checkbox = QCheckBox()
        self.db_logging_checkbox.setChecked(runtime_settings.enable_database_logging)
        layout.addRow("Enable Database Logging", self.db_logging_checkbox)

        # Database write interval setting
        self.db_write_interval_spinbox = QSpinBox()
        self.db_write_interval_spinbox.setRange(1, 3600)
        self.db_write_interval_spinbox.setValue(
            runtime_settings.db_write_interval_seconds
        )
        layout.addRow("Database Write Interval (sec):", self.db_write_interval_spinbox)

        self.general_tab.setLayout(layout)

    def init_tracking_tab(self):
        main_layout = QVBoxLayout()

        # Table to display/edit tracking intervals
        self.tracking_table = QTableWidget()
        self.tracking_table.setColumnCount(2)
        self.tracking_table.setHorizontalHeaderLabels(["Label", "Minutes"])
        self.tracking_table.horizontalHeader().setStretchLastSection(True)
        self.populate_tracking_table()

        main_layout.addWidget(QLabel("Tracking Intervals (Label : Minutes):"))
        main_layout.addWidget(self.tracking_table)

        # Add tracking duration setting
        duration_layout = QHBoxLayout()
        duration_label = QLabel("Tracking Duration (minutes):")
        self.tracking_duration_spinbox = QSpinBox()
        self.tracking_duration_spinbox.setRange(1, 60)  # 1 to 60 minutes
        self.tracking_duration_spinbox.setValue(
            get_runtime_settings().tracking_duration_minutes
        )
        duration_layout.addWidget(duration_label)
        duration_layout.addWidget(self.tracking_duration_spinbox)
        main_layout.addLayout(duration_layout)

        # Controls to add a new tracking interval
        add_layout = QHBoxLayout()
        self.new_interval_label_edit = QLineEdit()
        self.new_interval_label_edit.setPlaceholderText("Interval Label")
        self.new_interval_spinbox = QSpinBox()
        self.new_interval_spinbox.setRange(0, 1440)
        self.new_interval_spinbox.setValue(15)
        self.add_interval_button = QPushButton("Add Interval")
        self.add_interval_button.clicked.connect(self.add_tracking_interval)
        add_layout.addWidget(self.new_interval_label_edit)
        add_layout.addWidget(self.new_interval_spinbox)
        add_layout.addWidget(self.add_interval_button)
        main_layout.addLayout(add_layout)

        # Button to remove the selected tracking interval
        self.remove_interval_button = QPushButton("Remove Selected Interval")
        self.remove_interval_button.clicked.connect(self.remove_tracking_interval)
        main_layout.addWidget(self.remove_interval_button)

        self.tracking_tab.setLayout(main_layout)

    def init_advanced_tab(self):
        layout = QVBoxLayout()
        ml_settings = get_ml_settings()

        core_form = QFormLayout()
        self.model_complexity_spinbox = QSpinBox()
        self.model_complexity_spinbox.setRange(0, 2)
        self.model_complexity_spinbox.setValue(ml_settings.model_complexity)
        core_form.addRow("Model Complexity:", self.model_complexity_spinbox)

        self.detection_confidence_spinbox = QDoubleSpinBox()
        self.detection_confidence_spinbox.setRange(0.0, 1.0)
        self.detection_confidence_spinbox.setSingleStep(0.05)
        self.detection_confidence_spinbox.setDecimals(2)
        self.detection_confidence_spinbox.setValue(ml_settings.min_detection_confidence)
        core_form.addRow("Min Detection Confidence:", self.detection_confidence_spinbox)

        self.tracking_confidence_spinbox = QDoubleSpinBox()
        self.tracking_confidence_spinbox.setRange(0.0, 1.0)
        self.tracking_confidence_spinbox.setSingleStep(0.05)
        self.tracking_confidence_spinbox.setDecimals(2)
        self.tracking_confidence_spinbox.setValue(ml_settings.min_tracking_confidence)
        core_form.addRow("Min Tracking Confidence:", self.tracking_confidence_spinbox)

        self.score_buffer_spinbox = QSpinBox()
        self.score_buffer_spinbox.setRange(10, 10000)
        self.score_buffer_spinbox.setValue(ml_settings.score_buffer_size)
        core_form.addRow("Score Buffer Size:", self.score_buffer_spinbox)

        self.score_window_spinbox = QSpinBox()
        self.score_window_spinbox.setRange(1, 100)
        self.score_window_spinbox.setValue(ml_settings.score_window_size)
        core_form.addRow("Score Window Size:", self.score_window_spinbox)

        self.score_threshold_spinbox = QSpinBox()
        self.score_threshold_spinbox.setRange(0, 100)
        self.score_threshold_spinbox.setValue(ml_settings.score_threshold)
        core_form.addRow("Score Threshold:", self.score_threshold_spinbox)

        layout.addLayout(core_form)

        threshold_group = QGroupBox("Posture Thresholds")
        threshold_layout = QFormLayout()
        self.threshold_spinboxes: Dict[str, QDoubleSpinBox] = {}
        for key, value in ml_settings.posture_thresholds.items():
            spinbox = QDoubleSpinBox()
            spinbox.setDecimals(2)
            spinbox.setRange(0.0, 180.0)
            spinbox.setSingleStep(0.5)
            spinbox.setValue(float(value))
            label = key.replace("_", " ").title()
            threshold_layout.addRow(f"{label}:", spinbox)
            self.threshold_spinboxes[key] = spinbox
        threshold_group.setLayout(threshold_layout)
        layout.addWidget(threshold_group)

        weights_group = QGroupBox("Posture Weights")
        weights_layout = QFormLayout()
        self.weight_spinboxes: List[QDoubleSpinBox] = []
        for index, weight in enumerate(ml_settings.posture_weights, start=1):
            spinbox = QDoubleSpinBox()
            spinbox.setDecimals(3)
            spinbox.setRange(0.0, 1.0)
            spinbox.setSingleStep(0.05)
            spinbox.setValue(float(weight))
            weights_layout.addRow(f"Weight {index}:", spinbox)
            self.weight_spinboxes.append(spinbox)
        weights_group.setLayout(weights_layout)
        layout.addWidget(weights_group)

        layout.addStretch(1)
        self.advanced_tab.setLayout(layout)

    def toggle_advanced_tab(self, checked):
        current_index = self.tabs.indexOf(self.advanced_tab)
        if checked and current_index == -1:
            self.tabs.addTab(self.advanced_tab, "Advanced")
            self.tabs.setCurrentWidget(self.advanced_tab)
        elif not checked and current_index != -1:
            self.tabs.removeTab(current_index)

    def populate_tracking_table(self):
        intervals = get_runtime_settings().tracking_intervals
        self.tracking_table.setRowCount(0)
        for label, minutes in intervals.items():
            row_position = self.tracking_table.rowCount()
            self.tracking_table.insertRow(row_position)
            self.tracking_table.setItem(row_position, 0, QTableWidgetItem(label))
            self.tracking_table.setItem(row_position, 1, QTableWidgetItem(str(minutes)))

    def add_tracking_interval(self):
        label = self.new_interval_label_edit.text().strip()
        if not label:
            return  # Optionally, you might show a warning message.
        minutes = self.new_interval_spinbox.value()
        row_position = self.tracking_table.rowCount()
        self.tracking_table.insertRow(row_position)
        self.tracking_table.setItem(row_position, 0, QTableWidgetItem(label))
        self.tracking_table.setItem(row_position, 1, QTableWidgetItem(str(minutes)))
        self.new_interval_label_edit.clear()

    def remove_tracking_interval(self):
        selected_rows = set()
        for item in self.tracking_table.selectedItems():
            selected_rows.add(item.row())
        for row in sorted(selected_rows, reverse=True):
            self.tracking_table.removeRow(row)

    def get_available_cameras(self, max_index=5):
        available = []
        for i in range(max_index):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available.append((i, f"Camera {i}"))
            cap.release()
        return available

    def accept(self):
        runtime_updates = {}

        cam_id = self.camera_combo.currentData()
        if cam_id is None or cam_id == -1:
            cam_id = get_runtime_settings().default_camera_id
        runtime_updates["default_camera_id"] = cam_id
        runtime_updates["default_fps"] = self.fps_spinbox.value()
        runtime_updates["frame_width"] = self.width_spinbox.value()
        runtime_updates["frame_height"] = self.height_spinbox.value()

        runtime_updates["notification_cooldown"] = self.cooldown_spinbox.value()
        runtime_updates["poor_posture_threshold"] = self.poor_posture_spinbox.value()
        runtime_updates[
            "default_posture_message"
        ] = self.posture_message_lineedit.text()
        runtime_updates[
            "enable_database_logging"
        ] = self.db_logging_checkbox.isChecked()
        runtime_updates[
            "db_write_interval_seconds"
        ] = self.db_write_interval_spinbox.value()

        # Update Tracking Intervals from table
        intervals = {}
        row_count = self.tracking_table.rowCount()
        for row in range(row_count):
            label_item = self.tracking_table.item(row, 0)
            minutes_item = self.tracking_table.item(row, 1)
            if label_item and minutes_item:
                label = label_item.text().strip()
                try:
                    minutes = int(minutes_item.text())
                except ValueError:
                    minutes = 0
                intervals[label] = minutes
        runtime_updates["tracking_intervals"] = intervals
        runtime_updates[
            "tracking_duration_minutes"
        ] = self.tracking_duration_spinbox.value()

        ml_updates = {
            "model_complexity": self.model_complexity_spinbox.value(),
            "min_detection_confidence": self.detection_confidence_spinbox.value(),
            "min_tracking_confidence": self.tracking_confidence_spinbox.value(),
            "score_buffer_size": self.score_buffer_spinbox.value(),
            "score_window_size": self.score_window_spinbox.value(),
            "score_threshold": self.score_threshold_spinbox.value(),
            "posture_thresholds": {
                key: spinbox.value()
                for key, spinbox in self.threshold_spinboxes.items()
            },
            "posture_weights": [spinbox.value() for spinbox in self.weight_spinboxes],
        }

        update_runtime_settings(**runtime_updates)
        update_ml_settings(**ml_updates)
        save_user_settings()
        super().accept()
