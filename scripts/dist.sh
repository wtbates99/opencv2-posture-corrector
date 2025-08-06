#!/bin/bash

# Distribution script for OpenCV2 Posture Corrector

set -e  # Exit on any error

echo "Creating distribution package..."

# Check if we're in the right directory
if [ ! -f "CMakeLists.txt" ]; then
    echo "Error: CMakeLists.txt not found. Please run this script from the project root directory."
    exit 1
fi

# Build the project first
echo "Building project..."
./scripts/build.sh

# Create distribution directory
echo "Creating distribution package..."
mkdir -p dist
cp build/posture_corrector dist/

# Bundle libraries if dynamic linking (macOS example)
echo "Bundling dependencies..."
otool -L dist/posture_corrector | grep /opt/homebrew | awk '{print $1}' | xargs -I {} cp {} dist/ 2>/dev/null || echo "No dynamic libraries to bundle"

# Create archives
echo "Creating distribution archives..."
tar -czf posture-corrector-mac.tar.gz -C dist .
zip -r posture-corrector-mac.zip dist

echo "Distribution packages created:"
echo "- posture-corrector-mac.tar.gz"
echo "- posture-corrector-mac.zip"