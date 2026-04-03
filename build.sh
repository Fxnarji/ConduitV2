#!/usr/bin/env bash

set -e # optional: exit on error (you can remove if you want manual error handling)

echo "========================================"
echo "  Conduit | PyInstaller Build"
echo "========================================"
echo

# ------------------------------------------------------------------
# Activate virtual environment
# ------------------------------------------------------------------
if [ -f "venv/bin/activate" ]; then
  echo "[1/3] Activating virtual environment..."
  # shellcheck disable=SC1091
  source venv/bin/activate
else
  echo "[WARN] No venv/ found — using system Python."
  echo "       Run: python3 -m venv venv && venv/bin/pip install -e .[dev]"
  echo
fi

# ------------------------------------------------------------------
# Clean previous build artefacts
# ------------------------------------------------------------------
echo "[2/3] Cleaning previous build..."
[ -f "dist/Conduit" ] && rm -f "dist/Conduit"
[ -d "build/Conduit" ] && rm -rf "build/Conduit"

# ------------------------------------------------------------------
# Build
# ------------------------------------------------------------------
echo "[3/3] Running PyInstaller..."
echo

pyinstaller \
  --onefile \
  --windowed \
  --name "Conduit" \
  --add-data "resources/templates:resources/templates" \
  --add-data "src/conduit/ui/icons:conduit/ui/icons" \
  --add-data "src/conduit/ui/stylesheet.qss:conduit/ui" \
  src/conduit/__main__.py

echo

# ------------------------------------------------------------------
# Result handling
# ------------------------------------------------------------------
if [ $? -eq 0 ]; then
  echo "========================================"
  echo "  Build successful!"
  echo "  Output: dist/Conduit"
  echo "========================================"
else
  echo "========================================"
  echo "  Build FAILED (exit code $?)"
  echo "========================================"
fi

read -p "Press Enter to continue..."
