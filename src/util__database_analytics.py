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
)
from PyQt6.QtCharts import QChart, QChartView, QLineSeries, QDateTimeAxis, QValueAxis
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont
import math
from collections import defaultdict


# Database connection functions
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


# Helper function to compute angle between two vectors
def compute_angle(v1, v2):
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    mag1 = math.sqrt(v1[0] ** 2 + v1[1] ** 2)
    mag2 = math.sqrt(v2[0] ** 2 + v2[1] ** 2)
    if mag1 == 0 or mag2 == 0:
        return 0
    angle = math.acos(dot / (mag1 * mag2))
    return math.degrees(angle)


# Compute neck and shoulder angles from landmarks
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Posture Analytics")
        self.resize(1200, 800)

        # Fetch data
        posture_data = get_posture_scores()
        if len(posture_data) < 2:
            raise ValueError(
                "Insufficient posture score data points to create a chart."
            )
        pose_landmarks = get_pose_landmarks()

        # Process posture scores
        timestamps = [datetime.fromisoformat(row[0]) for row in posture_data]
        scores = [float(row[1]) for row in posture_data]
        t0 = min(timestamps)
        x_seconds = [(t - t0).total_seconds() for t in timestamps]

        # Compute trend line
        slope, intercept = np.polyfit(x_seconds, scores, 1)
        t_max = max(timestamps)
        x_max_seconds = (t_max - t0).total_seconds()

        # Create posture score series
        series = QLineSeries()
        series.setName("Posture Score")
        for t, score in zip(timestamps, scores):
            msecs = int(t.timestamp() * 1000)
            series.append(msecs, score)
        series.setPen(QPen(Qt.GlobalColor.cyan, 2))
        series.setPointsVisible(True)

        # Create trend line series
        trend_series = QLineSeries()
        trend_series.setName("Trend Line")
        y_start = intercept
        y_end = slope * x_max_seconds + intercept
        t0_msecs = int(t0.timestamp() * 1000)
        t_max_msecs = int(t_max.timestamp() * 1000)
        trend_series.append(t0_msecs, y_start)
        trend_series.append(t_max_msecs, y_end)
        trend_series.setPen(QPen(Qt.GlobalColor.red, 2, Qt.PenStyle.DashLine))

        # Create posture score chart
        posture_chart = QChart()
        posture_chart.setTitle("Posture Score Over Time")
        posture_chart.setTitleBrush(
            QBrush(QColor("#ffffff"))
        )  # Set title color to white
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
        axis_y.setRange(min(scores) - 5, max(scores) + 5)
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

        posture_chart_view = QChartView(posture_chart)
        posture_chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Process pose landmarks
        pose_data = defaultdict(dict)
        for row in pose_landmarks:
            timestamp, landmark_name, x, y, z, visibility = row
            pose_data[timestamp][landmark_name] = (x, y, z, visibility)

        neck_data = []
        shoulder_data = []
        for timestamp, landmarks in pose_data.items():
            if all(
                key in landmarks for key in ["NOSE", "LEFT_SHOULDER", "RIGHT_SHOULDER"]
            ):
                neck_angle, shoulder_angle = compute_angles(landmarks)
                neck_data.append((timestamp, neck_angle))
                shoulder_data.append((timestamp, shoulder_angle))

        # Sort data by timestamp
        neck_data.sort(key=lambda x: x[0])
        shoulder_data.sort(key=lambda x: x[0])

        # Create series for neck and shoulder angles
        neck_series = QLineSeries()
        neck_series.setName("Neck Angle")
        for ts, angle in neck_data:
            msecs = int(datetime.fromisoformat(ts).timestamp() * 1000)
            neck_series.append(msecs, angle)

        shoulder_series = QLineSeries()
        shoulder_series.setName("Shoulder Angle")
        for ts, angle in shoulder_data:
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

        neck_chart_view = QChartView(neck_chart)
        neck_chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)

        shoulder_chart_view = QChartView(shoulder_chart)
        shoulder_chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Compute averages
        avg_neck_angle = (
            sum(angle for _, angle in neck_data) / len(neck_data) if neck_data else 0
        )
        avg_shoulder_angle = (
            sum(angle for _, angle in shoulder_data) / len(shoulder_data)
            if shoulder_data
            else 0
        )
        avg_score = sum(scores) / len(scores) if scores else 0
        slope_per_minute = slope * 60  # Convert to points per minute
        trend_text = "Improving" if slope > 0 else "Worsening"

        # Create score card
        score_card_group = QGroupBox("Score Card")
        score_card_layout = QVBoxLayout()
        score_card_layout.setSpacing(10)

        label_font = QFont("Arial", 12)
        avg_score_label = QLabel(f"Average Posture Score: {avg_score:.2f}")
        avg_score_label.setFont(label_font)
        avg_neck_label = QLabel(f"Average Neck Angle: {avg_neck_angle:.2f}°")
        avg_neck_label.setFont(label_font)
        avg_shoulder_label = QLabel(
            f"Average Shoulder Angle: {avg_shoulder_angle:.2f}°"
        )
        avg_shoulder_label.setFont(label_font)
        trend_label = QLabel(
            f"Trend: {trend_text} by {abs(slope_per_minute):.2f} points/min"
        )
        trend_label.setFont(label_font)
        if slope > 0:
            trend_label.setStyleSheet("color: green;")
        else:
            trend_label.setStyleSheet("color: red;")

        score_card_layout.addWidget(avg_score_label)
        score_card_layout.addWidget(avg_neck_label)
        score_card_layout.addWidget(avg_shoulder_label)
        score_card_layout.addWidget(trend_label)
        score_card_group.setLayout(score_card_layout)

        # Set up main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(posture_chart_view)

        angle_charts_layout = QHBoxLayout()
        angle_charts_layout.addWidget(neck_chart_view)
        angle_charts_layout.addWidget(shoulder_chart_view)
        main_layout.addLayout(angle_charts_layout)

        main_layout.addWidget(score_card_group)

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
        """
        self.setStyleSheet(dark_stylesheet)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
