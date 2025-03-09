# OpenCV2 Posture Corrector

**Smart Posture Monitoring for Remote Workers**

OpenCV2 Posture Corrector helps remote workers maintain better posture throughout the workday. Using computer vision through your webcam, it provides real-time feedback on your sitting position, helping prevent the back and neck strain that comes with long hours at the desk.

---

## ✨ Features

- **Posture Scoring**: Simple 0-100 scale shows how you're doing
- **System Tray Integration**: Runs quietly in the background
- **Visual Indicators**: Color-coded feedback for quick assessment
- **Flexible Monitoring**: Set tracking intervals that work for you
- **Optional Video Feed**: See the tracking in action
- **Timely Notifications**: Get alerts when posture correction is needed
- **Cross-Platform**: Works on Windows, Mac, and Linux
- **Privacy-Focused**: All processing happens locally on your device

---

## 🚀 Getting Started

### **Windows Installation**

1. Requires Python 3.10
2. Install dependencies:
   ```bash
   py -3.10 -m pip install -r requirements.txt
   ```
3. Visual C++ Redistributable required
4. Troubleshooting:
   ```bash
   py -3.10 -m pip install msvc-runtime
   ```

### **Linux Installation**

1. Required packages:
   ```bash
   sudo apt install -y \
       libxcb1 \
       libxcb-xinerama0 \
       libxcb-cursor0 \
       libxkbcommon-x11-0 \
       libxcb-render0 \
       libxcb-render-util0
   ```
2. Optional packages:
   ```bash
   sudo apt install -y \
       qt6-base-dev \
       qt6-wayland \
       libqt5x11extras5
   ```

### **General Installation**

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Launch:
   ```bash
   python src/main.py
   ```

### 🎯 Basic Usage

- **Start Monitoring**: Access via system tray icon
- **View Feedback**: Optional video window shows posture analysis
- **Adjust Settings**: Set monitoring frequency to suit your workflow
- **Check Score**: System tray icon displays current posture rating
- **Respond to Alerts**: Straighten up when notifications appear

---

## 🔒 Privacy

All video processing occurs locally on your device. No data is stored, shared, or transmitted over the internet.

---

## 📈 Future Development

- **Posture History**: Track improvements over time
- **Usage Analytics**: Understand your posture patterns
- **Custom Notifications**: Tailor alerts to your preferences
- **Calendar Integration**: Smart monitoring based on your schedule

---

## 🤝 Contributing

Contributions welcome. See Contribution Guidelines for details.
