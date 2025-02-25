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
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
)
import cv2

from settings import CUSTOMIZABLE_SETTINGS, save_user_settings


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Customizable Settings")
        self.resize(800, 600)
        self.setMinimumSize(600, 400)
        self.tabs = QTabWidget()

        # Create tabs
        self.camera_tab = QWidget()
        self.general_tab = QWidget()
        self.tracking_tab = QWidget()

        self.init_camera_tab()
        self.init_general_tab()
        self.init_tracking_tab()

        self.tabs.addTab(self.camera_tab, "Camera")
        self.tabs.addTab(self.general_tab, "General")
        self.tabs.addTab(self.tracking_tab, "Tracking")

        # Dialog buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.tabs)
        main_layout.addWidget(self.button_box)
        self.setLayout(main_layout)

    def init_camera_tab(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()
        
        # Add spacing
        form_layout.setSpacing(10)
        form_layout.setContentsMargins(20, 20, 20, 20)
        
        # Make input fields wider
        self.camera_combo = QComboBox()
        self.camera_combo.setMinimumWidth(200)
        cameras = self.get_available_cameras()
        if cameras:
            for cam_id, cam_name in cameras:
                self.camera_combo.addItem(cam_name, cam_id)
            current_cam = CUSTOMIZABLE_SETTINGS.get("DEFAULT_CAMERA_ID", 0)
            index = self.camera_combo.findData(current_cam)
            if index != -1:
                self.camera_combo.setCurrentIndex(index)
        else:
            self.camera_combo.addItem("No Camera Found", -1)
            self.camera_combo.setEnabled(False)
        form_layout.addRow("Default Camera:", self.camera_combo)

        # Increase spinbox widths and ranges
        self.fps_spinbox = QSpinBox()
        self.fps_spinbox.setMinimumWidth(200)
        self.fps_spinbox.setRange(1, 120)
        self.fps_spinbox.setValue(CUSTOMIZABLE_SETTINGS.get("DEFAULT_FPS", 30))
        form_layout.addRow("Frames Per Second:", self.fps_spinbox)

        self.width_spinbox = QSpinBox()
        self.width_spinbox.setMinimumWidth(200)
        self.width_spinbox.setRange(100, 10000)
        self.width_spinbox.setValue(CUSTOMIZABLE_SETTINGS.get("FRAME_WIDTH", 1280))
        form_layout.addRow("Frame Width:", self.width_spinbox)

        self.height_spinbox = QSpinBox()
        self.height_spinbox.setMinimumWidth(200)
        self.height_spinbox.setRange(100, 10000)
        self.height_spinbox.setValue(CUSTOMIZABLE_SETTINGS.get("FRAME_HEIGHT", 720))
        form_layout.addRow("Frame Height:", self.height_spinbox)

        self.model_complexity_spinbox = QSpinBox()
        self.model_complexity_spinbox.setMinimumWidth(200)
        self.model_complexity_spinbox.setRange(0, 2)
        self.model_complexity_spinbox.setValue(
            CUSTOMIZABLE_SETTINGS.get("MODEL_COMPLEXITY", 1)
        )
        form_layout.addRow("Model Complexity:", self.model_complexity_spinbox)

        layout.addLayout(form_layout)
        layout.addStretch()
        self.camera_tab.setLayout(layout)

    def init_general_tab(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()
        
        # Add spacing
        form_layout.setSpacing(10)
        form_layout.setContentsMargins(20, 20, 20, 20)

        # Make input fields wider
        self.cooldown_spinbox = QSpinBox()
        self.cooldown_spinbox.setMinimumWidth(200)
        self.cooldown_spinbox.setRange(1, 3600)
        self.cooldown_spinbox.setValue(
            CUSTOMIZABLE_SETTINGS.get("NOTIFICATION_COOLDOWN", 300)
        )
        form_layout.addRow("Notification Cooldown (sec):", self.cooldown_spinbox)

        self.poor_posture_spinbox = QSpinBox()
        self.poor_posture_spinbox.setMinimumWidth(200)
        self.poor_posture_spinbox.setRange(1, 100)
        self.poor_posture_spinbox.setValue(
            CUSTOMIZABLE_SETTINGS.get("POOR_POSTURE_THRESHOLD", 60)
        )
        form_layout.addRow("Poor Posture Threshold:", self.poor_posture_spinbox)

        self.posture_message_lineedit = QLineEdit()
        self.posture_message_lineedit.setMinimumWidth(300)
        self.posture_message_lineedit.setText(
            CUSTOMIZABLE_SETTINGS.get(
                "DEFAULT_POSTURE_MESSAGE", "Please sit up straight!"
            )
        )
        form_layout.addRow("Posture Message:", self.posture_message_lineedit)

        layout.addLayout(form_layout)
        layout.addStretch()
        self.general_tab.setLayout(layout)

    def init_tracking_tab(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Improve table appearance
        self.tracking_table = QTableWidget()
        self.tracking_table.setColumnCount(2)
        self.tracking_table.setHorizontalHeaderLabels(["Label", "Minutes"])
        self.tracking_table.horizontalHeader().setStretchLastSection(True)
        self.tracking_table.setMinimumHeight(200)
        self.tracking_table.setAlternatingRowColors(True)
        self.tracking_table.verticalHeader().setVisible(False)
        
        # Populate the table with existing intervals
        self.populate_tracking_table()
        
        # Add controls with better spacing
        add_layout = QHBoxLayout()
        add_layout.setSpacing(10)
        
        self.new_interval_label_edit = QLineEdit()
        self.new_interval_label_edit.setMinimumWidth(200)
        self.new_interval_label_edit.setPlaceholderText("Interval Label")
        
        self.new_interval_spinbox = QSpinBox()
        self.new_interval_spinbox.setMinimumWidth(100)
        self.new_interval_spinbox.setRange(0, 1440)
        self.new_interval_spinbox.setValue(15)

        self.add_interval_button = QPushButton("Add Interval")
        self.add_interval_button.setMinimumWidth(100)
        self.add_interval_button.clicked.connect(self.add_tracking_interval)

        # Layout improvements
        main_layout.addWidget(QLabel("Tracking Intervals (Label : Minutes):"))
        main_layout.addWidget(self.tracking_table)
        
        add_layout.addWidget(self.new_interval_label_edit)
        add_layout.addWidget(self.new_interval_spinbox)
        add_layout.addWidget(self.add_interval_button)
        add_layout.addStretch()
        
        main_layout.addLayout(add_layout)
        
        self.remove_interval_button = QPushButton("Remove Selected Interval")
        self.remove_interval_button.setMinimumWidth(150)
        self.remove_interval_button.clicked.connect(self.remove_tracking_interval)
        main_layout.addWidget(self.remove_interval_button)
        main_layout.addStretch()
        
        self.tracking_tab.setLayout(main_layout)

    def populate_tracking_table(self):
        intervals = CUSTOMIZABLE_SETTINGS.get("TRACKING_INTERVALS", {})
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
                # Try to get camera name/description
                name = "Unknown Camera"
                try:
                    # Get camera backend
                    backend = cap.getBackendName()
                    # Get camera properties
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    name = f"{backend} Camera ({width}x{height})"
                except:
                    name = f"Camera {i}"
                    
                available.append((i, name))
            cap.release()
        return available

    def accept(self):
        # Update Camera settings.
        cam_id = self.camera_combo.currentData()
        if cam_id is None or cam_id == -1:
            cam_id = CUSTOMIZABLE_SETTINGS.get("DEFAULT_CAMERA_ID", 0)
        CUSTOMIZABLE_SETTINGS["DEFAULT_CAMERA_ID"] = cam_id
        CUSTOMIZABLE_SETTINGS["DEFAULT_FPS"] = self.fps_spinbox.value()
        CUSTOMIZABLE_SETTINGS["FRAME_WIDTH"] = self.width_spinbox.value()
        CUSTOMIZABLE_SETTINGS["FRAME_HEIGHT"] = self.height_spinbox.value()
        CUSTOMIZABLE_SETTINGS[
            "MODEL_COMPLEXITY"
        ] = self.model_complexity_spinbox.value()

        # Update General settings.
        CUSTOMIZABLE_SETTINGS["NOTIFICATION_COOLDOWN"] = self.cooldown_spinbox.value()
        CUSTOMIZABLE_SETTINGS[
            "POOR_POSTURE_THRESHOLD"
        ] = self.poor_posture_spinbox.value()
        CUSTOMIZABLE_SETTINGS[
            "DEFAULT_POSTURE_MESSAGE"
        ] = self.posture_message_lineedit.text()

        # Update Tracking Intervals from table.
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
                    minutes = 1
                intervals[label] = minutes
        CUSTOMIZABLE_SETTINGS["TRACKING_INTERVALS"] = intervals

        save_user_settings()
        super().accept()
