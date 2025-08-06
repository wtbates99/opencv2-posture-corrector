#!/bin/bash

# Build script for OpenCV2 Posture Corrector

set -e  # Exit on any error

echo "Building OpenCV2 Posture Corrector..."

# Check if we're in the right directory
if [ ! -f "CMakeLists.txt" ]; then
    echo "Error: CMakeLists.txt not found. Please run this script from the project root directory."
    exit 1
fi

# Check if OpenCV is installed
if ! brew list opencv >/dev/null 2>&1; then
    echo "OpenCV not found. Installing via Homebrew..."
    brew install opencv
fi

# Create build directory
echo "Creating build directory..."
mkdir -p build
cd build

# Configure with CMake
echo "Configuring with CMake..."
cmake -DOpenCV_DIR=/opt/homebrew/opt/opencv/lib/cmake/opencv4 ..

# Build the project
echo "Building project..."
make -j$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)

echo "Build completed successfully!"
echo "Run './posture_corrector' to start the application." 