#!/bin/bash
# Double-click me on a Mac: starts the local UI and opens the browser.
cd "$(dirname "$0")"
python3 -c "import openpyxl" 2>/dev/null || pip3 install -q openpyxl
python3 -m sales_points.ui
