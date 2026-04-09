# forex-bot-icc

Separate ICC signal dashboard project.

## Scope
- Uses the same stack style as the existing forex-bot: Python, Flask, requests, pydantic, python-dotenv
- Does not place trades
- Does not modify the original Desktop forex-bot
- Lets you choose an Oanda pair, submit it, and start tracking it in the dashboard
- Dashboard is intended to show BUY/SELL, entry, stop loss, and take profit for ICC setups

## Current status
This now includes:
- dashboard
- first-pass ICC scan logic
- continuous rescanning while tracking is enabled
- setup, launch, and stop scripts

## First-time setup
```bash
./setup_forex_bot_icc.command
```

## Launch
```bash
./launch_forex_bot_icc.command
```

## Stop
```bash
./stop_forex_bot_icc.command
```

Or run manually:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Then open:
- http://127.0.0.1:8082/dashboard
