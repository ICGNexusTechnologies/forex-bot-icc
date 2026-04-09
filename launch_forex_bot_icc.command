#!/bin/bash
set -e
cd "$(dirname "$0")"
source .venv/bin/activate
pkill -f "forex-bot-icc/app.py" >/dev/null 2>&1 || true
open "http://127.0.0.1:8082/dashboard"
python3 app.py
