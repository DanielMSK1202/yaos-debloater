#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${YAOS_PYTHON:-.venv/bin/python}"
"$PYTHON" -m unittest discover -s tests -q
"$PYTHON" scripts/collect_notices.py
export PYINSTALLER_CONFIG_DIR="$PWD/build/pyinstaller-cache"
"$PYTHON" -m PyInstaller --noconfirm YaOS-Debloater.spec
codesign --verify --deep --strict 'dist/YaOS Debloater.app'
env PATH=/usr/bin:/bin 'dist/YaOS Debloater.app/Contents/MacOS/YaOS Debloater' --check
bash scripts/create_dmg.sh
