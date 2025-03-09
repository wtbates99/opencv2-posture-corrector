import sqlite3
import os
import sys
from datetime import datetime
import numpy as np
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QLabel,
    QGroupBox,
    QPushButton,
)
from PyQt6.QtCharts import QChart, QChartView, QLineSeries, QDateTimeAxis, QValueAxis
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont
import math
from collections import defaultdict


def get_posture_scores():
    db_path = os.path.join(os.path.dirname(__file__), "posture_data.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM posture_scores")
    data = cursor.fetchall()
    conn.close()
    return data


def get_pose_landmarks():
    db_path = os.path.join(os.path.dirname(__file__), "posture_data.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pose_landmarks")
    data = cursor.fetchall()
    conn.close()
    return data


def compute_angle(v1, v2):
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    mag1 = math.sqrt(v1[0] ** 2 + v1[1] ** 2)
    mag2 = math.sqrt(v2[0] ** 2 + v2[1] ** 2)
    if mag1 == 0 or mag2 == 0:
        return 0
    angle = math.acos(dot / (mag1 * mag2))
    return math.degrees(angle)


def compute_angles(landmarks):
    left_shoulder = landmarks["LEFT_SHOULDER"]
    right_shoulder = landmarks["RIGHT_SHOULDER"]
    nose = landmarks["NOSE"]
    shoulder_midpoint = (
        (left_shoulder[0] + right_shoulder[0]) / 2,
        (left_shoulder[1] + right_shoulder[1]) / 2,
    )
    neck_vector = (nose[0] - shoulder_midpoint[0], nose[1] - shoulder_midpoint[1])
    vertical = (0, -1)  # y increases downward
    neck_angle = compute_angle(neck_vector, vertical)
    shoulder_vector = (
        right_shoulder[0] - left_shoulder[0],
        right_shoulder[1] - left_shoulder[1],
    )
    horizontal = (1, 0)
    shoulder_angle = compute_angle(shoulder_vector, horizontal)
    return neck_angle, shoulder_angle


# Function to create a chart with a single series
def create_chart(series, title, y_label, y_min, y_max, series_color):
    chart = QChart()
    chart.setTitle(title)
    chart.setTitleBrush(QBrush(QColor("#ffffff")))  # Set title color to white
    chart.addSeries(series)
    series.setPen(QPen(series_color, 2))
    series.setPointsVisible(True)

    axis_x = QDateTimeAxis()
    axis_x.setFormat("hh:mm")
    axis_x.setTitleText("Time")
    chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)

    axis_y = QValueAxis()
    axis_y.setTitleText(y_label)
    axis_y.setRange(y_min, y_max)
    chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)

    series.attachAxis(axis_x)
    series.attachAxis(axis_y)

    # Customize appearance
    chart.setBackgroundBrush(QBrush(QColor("#3c3c3c")))
    chart.setPlotAreaBackgroundBrush(QBrush(QColor("#2b2b2b")))
    chart.setPlotAreaBackgroundVisible(True)
    axis_x.setLabelsColor(QColor("#ffffff"))
    axis_y.setLabelsColor(QColor("#ffffff"))
    axis_x.setTitleBrush(QBrush(QColor("#ffffff")))
    axis_y.setTitleBrush(QBrush(QColor("#ffffff")))
    axis_x.setGridLineVisible(True)
    axis_y.setGridLineVisible(True)
    axis_x.setGridLinePen(QPen(QColor("#555555"), 0.5))
    axis_y.setGridLinePen(QPen(QColor("#555555"), 0.5))

    # Set fonts
    title_font = QFont("Arial", 14, QFont.Weight.Bold)
    chart.setTitleFont(title_font)
    axis_font = QFont("Arial", 12)
    axis_x.setTitleFont(axis_font)
    axis_y.setTitleFont(axis_font)
    legend = chart.legend()
    legend.setFont(QFont("Arial", 10))
    legend.setLabelColor(QColor("#ffffff"))

    return chart


class PostureAnalytics(QMainWindow):
    def __init__(self, db_path: str):
        super().__init__()
        self.setWindowTitle("Posture Analytics")
        self.resize(1200, 800)
        self.db_path = db_path

        # Create UI elements
        self.setup_ui()

        # Initial data load
        self.update_data()

    def setup_ui(self):
        # Create chart views
        self.posture_chart_view = QChartView()
        self.posture_chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)

        self.neck_chart_view = QChartView()
        self.neck_chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)

        self.shoulder_chart_view = QChartView()
        self.shoulder_chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Create score card
        self.score_card_group = QGroupBox("Score Card")
        score_card_layout = QVBoxLayout()
        score_card_layout.setSpacing(10)

        label_font = QFont("Arial", 12)
        self.avg_score_label = QLabel()
        self.avg_score_label.setFont(label_font)
        self.avg_neck_label = QLabel()
        self.avg_neck_label.setFont(label_font)
        self.avg_shoulder_label = QLabel()
        self.avg_shoulder_label.setFont(label_font)
        self.trend_label = QLabel()
        self.trend_label.setFont(label_font)

        score_card_layout.addWidget(self.avg_score_label)
        score_card_layout.addWidget(self.avg_neck_label)
        score_card_layout.addWidget(self.avg_shoulder_label)
        score_card_layout.addWidget(self.trend_label)
        self.score_card_group.setLayout(score_card_layout)

        # Create close button with larger size and more visible styling
        self.close_button = QPushButton("Close")
        self.close_button.setFixedSize(120, 50)
        self.close_button.setStyleSheet(
            """
            background-color: #d32f2f;
            color: white;
            font-weight: bold;
            font-size: 14px;
            border-radius: 5px;
        """
        )
        self.close_button.clicked.connect(self.close)

        # Set up main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.posture_chart_view)

        angle_charts_layout = QHBoxLayout()
        angle_charts_layout.addWidget(self.neck_chart_view)
        angle_charts_layout.addWidget(self.shoulder_chart_view)
        main_layout.addLayout(angle_charts_layout)

        main_layout.addWidget(self.score_card_group)

        # Add close button in a horizontal layout to position it
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        main_layout.addLayout(button_layout)

        # Add some spacing after the button
        main_layout.addSpacing(20)

        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Apply dark theme with font
        dark_stylesheet = """
        QWidget {
            background-color: #2b2b2b;
            color: #ffffff;
            font-family: Arial;
            font-size: 12px;
        }
        QChartView {
            background-color: #3c3c3c;
        }
        QGroupBox {
            border: 1px solid #555555;
            margin-top: 15px;
            padding: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 3px 0 3px;
            color: #ffffff;
            font-size: 14px;
            font-weight: bold;
        }
        QLabel {
            padding: 5px;
        }
        QPushButton {
            background-color: #4a4a4a;
            border: 1px solid #666666;
            border-radius: 4px;
            padding: 6px 12px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #5a5a5a;
        }
        QPushButton:pressed {
            background-color: #3a3a3a;
        }
        """
        self.setStyleSheet(dark_stylesheet)

    def update_data(self):
        # Fetch data
        posture_data = get_posture_scores()
        pose_landmarks = get_pose_landmarks()

        if not posture_data:
            # Handle empty data case
            self.display_no_data_message()
            return

        if len(posture_data) < 2:
            # We need at least 2 points for trend analysis
            self.display_limited_data(posture_data, pose_landmarks)
            return

        # Update charts and score card
        self.update_posture_chart(posture_data)
        self.update_angle_charts(pose_landmarks)
        self.update_score_card()

    def display_no_data_message(self):
        # Create empty charts with messages
        empty_chart = QChart()
        empty_chart.setTitle("No Posture Data Available")
        empty_chart.setTitleBrush(QBrush(QColor("#ffffff")))
        empty_chart.setBackgroundBrush(QBrush(QColor("#3c3c3c")))

        self.posture_chart_view.setChart(empty_chart)
        self.neck_chart_view.setChart(QChart(empty_chart))
        self.shoulder_chart_view.setChart(QChart(empty_chart))

        # Update labels with default values
        self.avg_score_label.setText("Average Posture Score: N/A")
        self.avg_neck_label.setText("Average Neck Angle: N/A")
        self.avg_shoulder_label.setText("Average Shoulder Angle: N/A")
        self.trend_label.setText("Trend: No data available")
        self.trend_label.setStyleSheet("color: white;")

        # Initialize data attributes to prevent errors elsewhere
        self.scores = []
        self.neck_data = []
        self.shoulder_data = []
        self.slope = 0
        self.intercept = 0
        self.avg_score = 0
        self.avg_neck_angle = 0
        self.avg_shoulder_angle = 0

    def display_limited_data(self, posture_data, pose_landmarks):
        # Handle case with only one data point (can't calculate trend)
        self.scores = [float(row[1]) for row in posture_data]
        self.avg_score = sum(self.scores) / len(self.scores) if self.scores else 0

        # Create a simple chart with the available point(s)
        series = QLineSeries()
        series.setName("Posture Score")
        for row in posture_data:
            timestamp = datetime.fromisoformat(row[0])
            score = float(row[1])
            msecs = int(timestamp.timestamp() * 1000)
            series.append(msecs, score)

        chart = QChart()
        chart.setTitle("Posture Score (Limited Data)")
        chart.setTitleBrush(QBrush(QColor("#ffffff")))
        chart.addSeries(series)
        chart.setBackgroundBrush(QBrush(QColor("#3c3c3c")))
        chart.setPlotAreaBackgroundBrush(QBrush(QColor("#2b2b2b")))
        chart.setPlotAreaBackgroundVisible(True)

        # Set up axes even with limited data
        axis_x = QDateTimeAxis()
        axis_x.setFormat("hh:mm")
        axis_x.setTitleText("Time")
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)

        axis_y = QValueAxis()
        axis_y.setTitleText("Posture Score")
        min_score = min(self.scores) - 5 if self.scores else 0
        max_score = max(self.scores) + 5 if self.scores else 100
        axis_y.setRange(min_score, max_score)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)

        series.attachAxis(axis_x)
        series.attachAxis(axis_y)

        self.posture_chart_view.setChart(chart)

        # Process pose landmarks if available
        self.process_pose_landmarks(pose_landmarks)

        # Set default values for trend analysis
        self.slope = 0
        self.intercept = 0

        # Update score card with limited data
        self.update_score_card_limited()

    def process_pose_landmarks(self, pose_landmarks):
        # Process pose landmarks similar to update_angle_charts but handle limited data
        pose_data = defaultdict(dict)
        for row in pose_landmarks:
            timestamp, landmark_name, x, y, z, visibility = row
            pose_data[timestamp][landmark_name] = (x, y, z, visibility)

        self.neck_data = []
        self.shoulder_data = []
        for timestamp, landmarks in pose_data.items():
            if all(
                key in landmarks for key in ["NOSE", "LEFT_SHOULDER", "RIGHT_SHOULDER"]
            ):
                neck_angle, shoulder_angle = compute_angles(landmarks)
                self.neck_data.append((timestamp, neck_angle))
                self.shoulder_data.append((timestamp, shoulder_angle))

        # Sort data by timestamp
        self.neck_data.sort(key=lambda x: x[0])
        self.shoulder_data.sort(key=lambda x: x[0])

        # Create simple charts for neck and shoulder angles
        if self.neck_data:
            neck_series = QLineSeries()
            neck_series.setName("Neck Angle")
            for ts, angle in self.neck_data:
                msecs = int(datetime.fromisoformat(ts).timestamp() * 1000)
                neck_series.append(msecs, angle)

            neck_chart = create_chart(
                neck_series,
                "Neck Angle (Limited Data)",
                "Neck Angle (°)",
                0,
                180,
                Qt.GlobalColor.green,
            )
            self.neck_chart_view.setChart(neck_chart)
        else:
            empty_chart = QChart()
            empty_chart.setTitle("No Neck Angle Data")
            empty_chart.setTitleBrush(QBrush(QColor("#ffffff")))
            empty_chart.setBackgroundBrush(QBrush(QColor("#3c3c3c")))
            self.neck_chart_view.setChart(empty_chart)

        if self.shoulder_data:
            shoulder_series = QLineSeries()
            shoulder_series.setName("Shoulder Angle")
            for ts, angle in self.shoulder_data:
                msecs = int(datetime.fromisoformat(ts).timestamp() * 1000)
                shoulder_series.append(msecs, angle)

            shoulder_chart = create_chart(
                shoulder_series,
                "Shoulder Angle (Limited Data)",
                "Shoulder Angle (°)",
                0,
                180,
                Qt.GlobalColor.magenta,
            )
            self.shoulder_chart_view.setChart(shoulder_chart)
        else:
            empty_chart = QChart()
            empty_chart.setTitle("No Shoulder Angle Data")
            empty_chart.setTitleBrush(QBrush(QColor("#ffffff")))
            empty_chart.setBackgroundBrush(QBrush(QColor("#3c3c3c")))
            self.shoulder_chart_view.setChart(empty_chart)

    def update_score_card_limited(self):
        # Compute averages with limited data
        self.avg_neck_angle = (
            sum(angle for _, angle in self.neck_data) / len(self.neck_data)
            if self.neck_data
            else 0
        )
        self.avg_shoulder_angle = (
            sum(angle for _, angle in self.shoulder_data) / len(self.shoulder_data)
            if self.shoulder_data
            else 0
        )

        # Update labels
        self.avg_score_label.setText(f"Average Posture Score: {self.avg_score:.2f}")
        self.avg_neck_label.setText(
            f"Average Neck Angle: {self.avg_neck_angle:.2f}°"
            if self.neck_data
            else "Average Neck Angle: N/A"
        )
        self.avg_shoulder_label.setText(
            f"Average Shoulder Angle: {self.avg_shoulder_angle:.2f}°"
            if self.shoulder_data
            else "Average Shoulder Angle: N/A"
        )
        self.trend_label.setText("Trend: Insufficient data for trend analysis")
        self.trend_label.setStyleSheet("color: yellow;")

    def update_posture_chart(self, posture_data):
        # Process posture scores
        timestamps = [datetime.fromisoformat(row[0]) for row in posture_data]
        self.scores = [float(row[1]) for row in posture_data]
        t0 = min(timestamps)
        x_seconds = [(t - t0).total_seconds() for t in timestamps]

        # Compute trend line
        self.slope, self.intercept = np.polyfit(x_seconds, self.scores, 1)
        t_max = max(timestamps)
        x_max_seconds = (t_max - t0).total_seconds()

        # Create posture score series
        series = QLineSeries()
        series.setName("Posture Score")
        for t, score in zip(timestamps, self.scores):
            msecs = int(t.timestamp() * 1000)
            series.append(msecs, score)
        series.setPen(QPen(Qt.GlobalColor.cyan, 2))
        series.setPointsVisible(True)

        # Create trend line series
        trend_series = QLineSeries()
        trend_series.setName("Trend Line")
        y_start = self.intercept
        y_end = self.slope * x_max_seconds + self.intercept
        t0_msecs = int(t0.timestamp() * 1000)
        t_max_msecs = int(t_max.timestamp() * 1000)
        trend_series.append(t0_msecs, y_start)
        trend_series.append(t_max_msecs, y_end)
        trend_series.setPen(QPen(Qt.GlobalColor.red, 2, Qt.PenStyle.DashLine))

        # Create posture score chart
        posture_chart = QChart()
        posture_chart.setTitle("Posture Score Over Time")
        posture_chart.setTitleBrush(QBrush(QColor("#ffffff")))
        posture_chart.addSeries(series)
        posture_chart.addSeries(trend_series)
        posture_chart.legend().setVisible(True)
        posture_chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)

        axis_x = QDateTimeAxis()
        axis_x.setFormat("hh:mm")
        axis_x.setTitleText("Time")
        posture_chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)

        axis_y = QValueAxis()
        axis_y.setTitleText("Posture Score")
        axis_y.setRange(min(self.scores) - 5, max(self.scores) + 5)
        posture_chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)

        series.attachAxis(axis_x)
        series.attachAxis(axis_y)
        trend_series.attachAxis(axis_x)
        trend_series.attachAxis(axis_y)

        # Customize posture chart appearance
        posture_chart.setBackgroundBrush(QBrush(QColor("#3c3c3c")))
        posture_chart.setPlotAreaBackgroundBrush(QBrush(QColor("#2b2b2b")))
        posture_chart.setPlotAreaBackgroundVisible(True)
        axis_x.setLabelsColor(QColor("#ffffff"))
        axis_y.setLabelsColor(QColor("#ffffff"))
        axis_x.setTitleBrush(QBrush(QColor("#ffffff")))
        axis_y.setTitleBrush(QBrush(QColor("#ffffff")))
        axis_x.setGridLineVisible(True)
        axis_y.setGridLineVisible(True)
        axis_x.setGridLinePen(QPen(QColor("#555555"), 0.5))
        axis_y.setGridLinePen(QPen(QColor("#555555"), 0.5))

        # Set fonts for posture chart
        title_font = QFont("Arial", 14, QFont.Weight.Bold)
        posture_chart.setTitleFont(title_font)
        axis_font = QFont("Arial", 12)
        axis_x.setTitleFont(axis_font)
        axis_y.setTitleFont(axis_font)
        legend = posture_chart.legend()
        legend.setFont(QFont("Arial", 10))
        legend.setLabelColor(QColor("#ffffff"))

        self.posture_chart_view.setChart(posture_chart)

    def update_angle_charts(self, pose_landmarks):
        # Process pose landmarks
        pose_data = defaultdict(dict)
        for row in pose_landmarks:
            timestamp, landmark_name, x, y, z, visibility = row
            pose_data[timestamp][landmark_name] = (x, y, z, visibility)

        self.neck_data = []
        self.shoulder_data = []
        for timestamp, landmarks in pose_data.items():
            if all(
                key in landmarks for key in ["NOSE", "LEFT_SHOULDER", "RIGHT_SHOULDER"]
            ):
                neck_angle, shoulder_angle = compute_angles(landmarks)
                self.neck_data.append((timestamp, neck_angle))
                self.shoulder_data.append((timestamp, shoulder_angle))

        # Sort data by timestamp
        self.neck_data.sort(key=lambda x: x[0])
        self.shoulder_data.sort(key=lambda x: x[0])

        # Create series for neck and shoulder angles
        neck_series = QLineSeries()
        neck_series.setName("Neck Angle")
        for ts, angle in self.neck_data:
            msecs = int(datetime.fromisoformat(ts).timestamp() * 1000)
            neck_series.append(msecs, angle)

        shoulder_series = QLineSeries()
        shoulder_series.setName("Shoulder Angle")
        for ts, angle in self.shoulder_data:
            msecs = int(datetime.fromisoformat(ts).timestamp() * 1000)
            shoulder_series.append(msecs, angle)

        # Create charts for neck and shoulder angles
        neck_chart = create_chart(
            neck_series,
            "Neck Angle Over Time",
            "Neck Angle (°)",
            0,
            180,
            Qt.GlobalColor.green,
        )
        shoulder_chart = create_chart(
            shoulder_series,
            "Shoulder Angle Over Time",
            "Shoulder Angle (°)",
            0,
            180,
            Qt.GlobalColor.magenta,
        )

        self.neck_chart_view.setChart(neck_chart)
        self.shoulder_chart_view.setChart(shoulder_chart)

    def update_score_card(self):
        # Compute averages
        self.avg_neck_angle = (
            sum(angle for _, angle in self.neck_data) / len(self.neck_data)
            if self.neck_data
            else 0
        )
        self.avg_shoulder_angle = (
            sum(angle for _, angle in self.shoulder_data) / len(self.shoulder_data)
            if self.shoulder_data
            else 0
        )
        self.avg_score = sum(self.scores) / len(self.scores) if self.scores else 0
        slope_per_minute = self.slope * 60  # Convert to points per minute
        trend_text = "Improving" if self.slope > 0 else "Worsening"

        # Update labels
        self.avg_score_label.setText(f"Average Posture Score: {self.avg_score:.2f}")
        self.avg_neck_label.setText(f"Average Neck Angle: {self.avg_neck_angle:.2f}°")
        self.avg_shoulder_label.setText(
            f"Average Shoulder Angle: {self.avg_shoulder_angle:.2f}°"
        )
        self.trend_label.setText(
            f"Trend: {trend_text} by {abs(slope_per_minute):.2f} points/min"
        )

        if self.slope > 0:
            self.trend_label.setStyleSheet("color: green;")
        else:
            self.trend_label.setStyleSheet("color: red;")

    def refresh_data(self):
        """Method to refresh data from the database and update the UI"""
        try:
            self.update_data()
        except Exception as e:
            print(f"Error refreshing data: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    db_path = os.path.join(os.path.dirname(__file__), "posture_data.db")
    window = PostureAnalytics(db_path)
    window.show()
    sys.exit(app.exec())
