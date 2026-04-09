#!/bin/bash
set -e
cd "$(dirname "$0")"
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
pip install -r requirements.txt
chmod +x launch_forex_bot_icc.command stop_forex_bot_icc.command
printf '\nSetup complete. Run ./launch_forex_bot_icc.command\n'
