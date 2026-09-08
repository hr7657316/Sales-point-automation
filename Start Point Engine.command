#!/bin/bash
# Double-click this file in Finder (don't paste its contents into Terminal).
# It starts the local point engine UI and opens your browser.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
cd "$HERE" || exit 1
python3 -c "import openpyxl" 2>/dev/null || pip3 install -q openpyxl
echo "Starting the point engine UI from: $HERE"
python3 -m sales_points.ui
