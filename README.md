# OpenCV2 Posture Corrector

A lightweight posture correction tool using OpenCV for real-time posture monitoring.

## Prerequisites

- OpenCV 4.x installed via Homebrew: `brew install opencv`
- CMake 3.10 or higher
- C++17 compatible compiler

## Building

Make sure you're in the project root directory (`opencv2-posture-corrector`), then run:

```bash
# Create and enter build directory
mkdir -p build && cd build

# Configure with CMake (specify OpenCV path for Homebrew)
cmake -DOpenCV_DIR=/opt/homebrew/opt/opencv/lib/cmake/opencv4 ..

# Build the project
make
```

## Running

After building, run the posture corrector:

```bash
./posture_corrector
```

The application will:
- Open your default webcam
- Monitor your posture in real-time
- Provide feedback via console output
- Press 'q' to quit (if running with GUI)

## Troubleshooting

If you encounter build issues:

1. **CMake can't find OpenCV**: Make sure OpenCV is installed via Homebrew and the path is correct
2. **Wrong directory error**: Ensure you're running commands from the project root, not a parent directory
3. **Webcam access**: Grant camera permissions to the terminal application

## Features

- Real-time webcam posture monitoring
- Edge detection for shoulder alignment
- Console-based feedback
- Efficient 2 FPS processing for low CPU usage