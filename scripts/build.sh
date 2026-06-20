#!/bin/bash
# Build script for Clipshare
# Usage:
#   ./scripts/build.sh          # Build for current platform
#   ./scripts/build.sh macos    # Build for macOS
#   ./scripts/build.sh windows  # Build for Windows (cross-compile or native)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "=== Clipshare Build Script ==="
echo "Project: $PROJECT_DIR"

# Install dependencies
echo ""
echo "[1/3] Installing dependencies..."
pip install -e .
pip install pyinstaller

# Build
echo ""
echo "[2/3] Building with PyInstaller..."
pyinstaller --clean --noconfirm clipshare.spec

# Show result
echo ""
echo "[3/3] Build complete!"
echo ""

if [ -f "dist/clipshare" ]; then
    echo "Output: dist/clipshare"
    ls -lh dist/clipshare
elif [ -f "dist/clipshare.exe" ]; then
    echo "Output: dist/clipshare.exe"
    ls -lh dist/clipshare.exe
else
    echo "Build output:"
    ls -la dist/
fi

echo ""
echo "To run: ./dist/clipshare --help"