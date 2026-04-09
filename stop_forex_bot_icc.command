#!/bin/bash
cd "$(dirname "$0")"
pkill -f "forex-bot-icc/app.py" >/dev/null 2>&1 || true
pkill -f "forex-bot-icc/live_bot.py" >/dev/null 2>&1 || true
printf 'Forex Bot ICC stopped.\n'
