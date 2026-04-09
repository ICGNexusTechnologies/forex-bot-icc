from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import subprocess
import sys

from flask import Flask, redirect, render_template_string, request, url_for

BOT_ROOT = Path(__file__).resolve().parent
CONTROL_FILE = BOT_ROOT / "dashboard_control.json"
SIGNALS_FILE = BOT_ROOT / "signals.json"
STATE_FILE = BOT_ROOT / "state.json"
CREDS_FILE = BOT_ROOT / ".oanda_env"
PIP_OVERRIDES = {
    "JPY": 0.01,
}
TIMEFRAME_CONFIG = {
    "D": {"granularity": "D", "count": 120},
    "H4": {"granularity": "H4", "count": 160},
    "H1": {"granularity": "H1", "count": 240},
}
SWING_LOOKBACK = {
    "D": 20,
    "H4": 24,
    "H1": 30,
}
MAX_SIGNAL_AGE_HOURS = 48

app = Flask(__name__)

BASE_HTML = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Forex Bot ICC</title>
  <style>
    :root {
      --bg: #07111f;
      --panel: #0f1b31;
      --panel-2: #13213b;
      --border: rgba(255,255,255,.08);
      --text: #edf2ff;
      --muted: #9fb0d0;
      --green: #22c55e;
      --red: #ef4444;
      --amber: #f59e0b;
      --blue: #6366f1;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif;
      background: linear-gradient(180deg, #040915 0%, #07111f 100%);
      color: var(--text);
    }
    .wrap { max-width: 1100px; margin: 0 auto; padding: 24px 16px 40px; min-height: 100vh; }
    .hero, .card {
      background: linear-gradient(180deg, rgba(15,27,49,.96), rgba(11,21,39,.96));
      border: 1px solid var(--border);
      border-radius: 20px;
      box-shadow: 0 18px 40px rgba(0,0,0,.25);
    }
    .hero { padding: 22px; margin-bottom: 16px; }
    .hero h1 { margin: 0 0 8px; font-size: 1.4rem; }
    .hero p { margin: 0; color: var(--muted); line-height: 1.5; }
    .grid { display: grid; grid-template-columns: 360px 1fr; gap: 16px; }
    .card { padding: 18px; }
    .title { margin: 0 0 14px; font-size: .95rem; font-weight: 800; }
    .label { font-size: .74rem; color: var(--muted); margin-bottom: 6px; text-transform: uppercase; letter-spacing: .08em; }
    .help { color: var(--muted); font-size: .8rem; line-height: 1.45; }
    select, input {
      width: 100%;
      background: #08101f;
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 10px 12px;
      font-size: .9rem;
      margin-bottom: 12px;
    }
    .select {
      width: 100%; background: rgba(2,6,23,.9); color: var(--text); border: 1px solid rgba(255,255,255,.08);
      border-radius: 12px; padding: 10px 12px; font-size: .9rem; margin-bottom: 12px;
    }
    .btnrow { display: flex; gap: 10px; flex-wrap: wrap; }
    .favorites {
      margin-top: 14px;
      border-top: 1px solid var(--border);
      padding-top: 14px;
    }
    .favorites-list {
      display: grid;
      gap: 8px;
      max-height: 220px;
      overflow: auto;
      margin-top: 10px;
    }
    .favorite-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding: 10px 12px;
      border-radius: 10px;
      background: rgba(19,33,59,.55);
      border: 1px solid var(--border);
      font-size: .86rem;
    }
    .favorite-row input[type='checkbox'] {
      width: 16px;
      height: 16px;
      margin: 0;
    }
    button {
      border: none;
      border-radius: 12px;
      padding: 10px 14px;
      font-weight: 800;
      color: white;
      cursor: pointer;
      background: linear-gradient(135deg, #6366f1, #8b5cf6);
    }
    button.secondary { background: #1e293b; border: 1px solid var(--border); }
    .pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border-radius: 999px;
      padding: 8px 12px;
      background: rgba(99,102,241,.14);
      border: 1px solid var(--border);
      font-size: .8rem;
      font-weight: 700;
    }
    .dot { width: 8px; height: 8px; border-radius: 999px; background: var(--amber); }
    .green { color: #bbf7d0; }
    .green .dot { background: var(--green); }
    .red { color: #fecaca; }
    .red .dot { background: var(--red); }
    .amber { color: #fde68a; }
    .stats { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 12px; margin-bottom: 14px; }
    .stat {
      background: rgba(8,16,31,.72);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 12px;
    }
    .stat .k { color: var(--muted); font-size: .72rem; text-transform: uppercase; letter-spacing: .08em; margin-bottom: 8px; }
    .stat .v { font-size: 1.05rem; font-weight: 800; }
    .signal {
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 14px;
      background: rgba(8,16,31,.72);
      margin-bottom: 12px;
    }
    .signal:last-child { margin-bottom: 0; }
    .signal-head { display: flex; justify-content: space-between; gap: 10px; align-items: center; margin-bottom: 12px; }
    .signal-side { font-size: 1rem; font-weight: 900; }
    .buy { color: var(--green); }
    .sell { color: var(--red); }
    .signal-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 10px; }
    .metric {
      border-radius: 12px;
      background: rgba(19,33,59,.75);
      padding: 10px;
    }
    .metric .k { color: var(--muted); font-size: .7rem; margin-bottom: 6px; text-transform: uppercase; letter-spacing: .08em; }
    .metric .v { font-size: .95rem; font-weight: 800; }
    .flash {
      margin-top: 8px;
      border-radius: 12px;
      padding: 10px 12px;
      font-size: .82rem;
      font-weight: 700;
      border: 1px solid var(--border);
    }
    .flash.success { background: rgba(34,197,94,.12); color: #bbf7d0; }
    .flash.error { background: rgba(239,68,68,.12); color: #fecaca; }
    @media (max-width: 900px) {
      .grid { grid-template-columns: 1fr; }
      .stats, .signal-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class=\"wrap\">{{ body|safe }}</div>
  <script>
    setTimeout(() => {
      window.location.reload();
    }, 60000);
  </script>
</body>
</html>
"""


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2))


def default_control() -> dict[str, Any]:
    return {
        "account_mode": "demo",
        "selected_instrument": "",
        "favorites": [],
        "api_key": "",
        "account_id": "",
        "status": "idle",
    }


def load_control() -> dict[str, Any]:
    return {**default_control(), **load_json(CONTROL_FILE, {})}


def save_control(control: dict[str, Any]) -> None:
    save_json(CONTROL_FILE, control)


def write_creds_file(api_key: str, account_id: str, mode: str) -> None:
    base = "https://api-fxtrade.oanda.com/v3" if mode == "live" else "https://api-fxpractice.oanda.com/v3"
    CREDS_FILE.write_text(
        f"export OANDA_API_BASE='{base}'\nexport OANDA_API_KEY='{api_key}'\nexport OANDA_ACCOUNT_ID='{account_id}'\n"
    )


def get_api_base(mode: str) -> str:
    return "https://api-fxtrade.oanda.com/v3" if mode == "live" else "https://api-fxpractice.oanda.com/v3"


def fetch_instruments(api_key: str, account_id: str, mode: str) -> list[str]:
    if not api_key or not account_id:
        return []
    resp = requests.get(
        f"{get_api_base(mode)}/accounts/{account_id}/instruments",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=20,
    )
    resp.raise_for_status()
    payload = resp.json()
    return sorted(item["name"] for item in payload.get("instruments", []) if item.get("name"))


def fetch_candles(api_key: str, instrument: str, mode: str, granularity: str, count: int) -> list[dict[str, Any]]:
    resp = requests.get(
        f"{get_api_base(mode)}/instruments/{instrument}/candles",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        params={"price": "M", "granularity": granularity, "count": count},
        timeout=20,
    )
    resp.raise_for_status()
    payload = resp.json()
    candles: list[dict[str, Any]] = []
    for candle in payload.get("candles", []):
        mid = candle.get("mid") or {}
        if not candle.get("complete", False):
            continue
        candles.append(
            {
                "time": candle.get("time"),
                "open": float(mid.get("o", 0.0)),
                "high": float(mid.get("h", 0.0)),
                "low": float(mid.get("l", 0.0)),
                "close": float(mid.get("c", 0.0)),
            }
        )
    return candles


def pip_size(instrument: str) -> float:
    quote = instrument.split("_")[-1] if "_" in instrument else instrument[-3:]
    return PIP_OVERRIDES.get(quote, 0.0001)


def format_price(instrument: str, price: float) -> str:
    decimals = 3 if pip_size(instrument) == 0.01 else 5
    return f"{price:.{decimals}f}"


def parse_oanda_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def find_origin_level(candles: list[dict[str, Any]], breakout_index: int, side: str) -> float | None:
    if breakout_index <= 0:
        return None
    start = max(0, breakout_index - SWING_LOOKBACK["H1"])
    window = candles[start:breakout_index]
    if not window:
        return None
    if side == "BUY":
        return max(c["high"] for c in window)
    return min(c["low"] for c in window)


def timeframe_bias(candles: list[dict[str, Any]]) -> str:
    if len(candles) < 3:
        return "neutral"
    recent = candles[-3:]
    if recent[-1]["close"] > recent[0]["close"]:
        return "bullish"
    if recent[-1]["close"] < recent[0]["close"]:
        return "bearish"
    return "neutral"


def find_recent_breakout(candles: list[dict[str, Any]], side: str, lookback: int) -> tuple[int | None, float | None, float | None]:
    if len(candles) < lookback + 2:
        return None, None, None
    start = max(lookback, len(candles) - lookback)
    for idx in range(len(candles) - 1, start - 1, -1):
        candle = candles[idx]
        previous = candles[max(0, idx - lookback):idx]
        if not previous:
            continue
        if side == "BUY":
            reference = max(c["high"] for c in previous)
            if candle["high"] > reference:
                return idx, reference, candle["high"]
        else:
            reference = min(c["low"] for c in previous)
            if candle["low"] < reference:
                return idx, reference, candle["low"]
    return None, None, None


def signal_is_fresh(signal_time: str) -> bool:
    try:
        detected = parse_oanda_time(signal_time)
    except Exception:
        return False
    age_hours = (datetime.now(timezone.utc) - detected.astimezone(timezone.utc)).total_seconds() / 3600
    return age_hours <= MAX_SIGNAL_AGE_HOURS


def detect_icc_signal(instrument: str, candles_by_tf: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
    h1 = candles_by_tf.get("H1") or []
    h4 = candles_by_tf.get("H4") or []
    daily = candles_by_tf.get("D") or []
    if len(h1) < 40 or len(h4) < 20 or len(daily) < 10:
        return None

    buy_idx, buy_level, buy_extreme = find_recent_breakout(h1, "BUY", SWING_LOOKBACK["H1"])
    sell_idx, sell_level, sell_extreme = find_recent_breakout(h1, "SELL", SWING_LOOKBACK["H1"])

    candidates: list[dict[str, Any]] = []
    for side, breakout_index, level, extreme in (
        ("BUY", buy_idx, buy_level, buy_extreme),
        ("SELL", sell_idx, sell_level, sell_extreme),
    ):
        if breakout_index is None or level is None or extreme is None:
            continue
        breakout_candle = h1[breakout_index]
        origin_level = find_origin_level(h1, breakout_index, side)
        if origin_level is None:
            origin_level = level
        pip = pip_size(instrument)
        stop_distance = 50 * pip
        stop_loss = origin_level - stop_distance if side == "BUY" else origin_level + stop_distance
        candidates.append(
            {
                "pair": instrument,
                "side": side,
                "timeframe_context": "Daily / 4H / 1H",
                "detected_at": breakout_candle["time"],
                "entry": format_price(instrument, origin_level),
                "stop_loss": format_price(instrument, stop_loss),
                "take_profit": format_price(instrument, extreme),
                "indication_level": format_price(instrument, level),
                "indication_extreme": format_price(instrument, extreme),
                "bias_notes": (
                    f"Daily bias: {timeframe_bias(daily)}, 4H bias: {timeframe_bias(h4)}, "
                    f"1H breakout from recent {'high' if side == 'BUY' else 'low'}"
                ),
                "breakout_index": breakout_index,
            }
        )

    if not candidates:
        return None

    candidates.sort(key=lambda item: item["breakout_index"], reverse=True)
    signal = candidates[0]
    if not signal_is_fresh(signal["detected_at"]):
        return None
    signal.pop("breakout_index", None)
    return signal


def build_signal_for_pair(control: dict[str, Any]) -> dict[str, Any] | None:
    api_key = control.get("api_key", "")
    instrument = control.get("selected_instrument", "")
    if not api_key or not instrument:
        return None
    candles_by_tf: dict[str, list[dict[str, Any]]] = {}
    for tf, cfg in TIMEFRAME_CONFIG.items():
        candles_by_tf[tf] = fetch_candles(api_key, instrument, control.get("account_mode", "demo"), cfg["granularity"], cfg["count"])
    return detect_icc_signal(instrument, candles_by_tf)


@app.post("/submit")
def submit_controls():
    control = load_control()
    control["account_mode"] = "live" if request.form.get("account_mode") == "live" else "demo"
    selected_instrument = request.form.get("selected_instrument", "").strip()
    favorite_instruments = request.form.getlist("favorite_instruments")
    control["favorites"] = favorite_instruments
    if selected_instrument:
        control["selected_instrument"] = selected_instrument
    elif favorite_instruments and not control.get("selected_instrument"):
        control["selected_instrument"] = favorite_instruments[0]
    api_key = request.form.get("api_key", "").strip().strip("'\"")
    account_id = request.form.get("account_id", "").strip().strip("'\"")
    if api_key:
        control["api_key"] = api_key
    if account_id:
        control["account_id"] = account_id
    save_control(control)
    if control["api_key"] and control["account_id"]:
        write_creds_file(control["api_key"], control["account_id"], control["account_mode"])
    return redirect(url_for("dashboard", flash="Settings saved", kind="success"))


@app.post("/start")
def start_tracking():
    control = load_control()
    if not control.get("selected_instrument"):
        return redirect(url_for("dashboard", flash="Pick a pair first", kind="error"))
    if not control.get("api_key") or not control.get("account_id"):
        return redirect(url_for("dashboard", flash="Add Oanda API key and account ID first", kind="error"))

    control["status"] = "tracking"
    save_control(control)
    state = load_json(STATE_FILE, {})

    signal = None
    try:
        signal = build_signal_for_pair(control)
    except Exception as exc:
        state[control["selected_instrument"]] = {
            "tracking": True,
            "started_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "last_error": str(exc),
        }
        save_json(STATE_FILE, state)
        return redirect(url_for("dashboard", flash=f"Tracking started, but scan failed: {exc}", kind="error"))

    pair = control["selected_instrument"]
    state = {pair: state.get(pair, {}) if isinstance(state.get(pair), dict) else {}}
    pair_state = state.get(pair, {}) if isinstance(state.get(pair), dict) else {}
    pair_state.update(
        {
            "tracking": True,
            "started_at": pair_state.get("started_at") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "last_scan_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "last_signal_side": signal.get("side") if signal else None,
            "last_signal_time": signal.get("detected_at") if signal else None,
            "signal_active": bool(signal),
        }
    )
    if signal:
        pair_state["active_signal"] = signal
        pair_state.pop("last_error", None)
    else:
        pair_state.pop("active_signal", None)
    state[pair] = pair_state
    save_json(STATE_FILE, state)

    signal_store = load_json(SIGNALS_FILE, {"signals": []})
    signal_store["signals"] = [s for s in signal_store.get("signals", []) if s.get("pair") != pair]
    if signal:
        signal_store["signals"].insert(0, signal)
    save_json(SIGNALS_FILE, signal_store)

    live_bot_running = subprocess.run(["pgrep", "-f", "forex-bot-icc/live_bot.py"], capture_output=True, text=True)
    if live_bot_running.returncode != 0:
        subprocess.Popen([sys.executable, str(BOT_ROOT / "live_bot.py")], cwd=BOT_ROOT)

    if signal:
        return redirect(url_for("dashboard", flash=f"Tracking {pair}, signal updated", kind="success"))
    return redirect(url_for("dashboard", flash=f"Tracking {pair}, no fresh ICC indication found", kind="success"))


@app.post("/stop")
def stop_tracking():
    control = load_control()
    control["status"] = "idle"
    save_control(control)
    subprocess.run(["pkill", "-f", "forex-bot-icc/live_bot.py"], capture_output=True)
    return redirect(url_for("dashboard", flash="Tracking stopped", kind="success"))


@app.route("/")
@app.route("/dashboard")
def dashboard():
    control = load_control()
    signals = load_json(SIGNALS_FILE, {"signals": []}).get("signals", [])
    state = load_json(STATE_FILE, {})
    instruments: list[str] = []
    instrument_error = ""
    if control.get("api_key") and control.get("account_id"):
        try:
            instruments = fetch_instruments(control["api_key"], control["account_id"], control["account_mode"])
        except Exception as exc:
            instrument_error = str(exc)
    active_pair = control.get("selected_instrument", "")
    favorites = control.get("favorites", [])
    if instruments and active_pair and active_pair not in instruments:
        instruments = [active_pair] + [instrument for instrument in instruments if instrument != active_pair]
    favorite_names = [name for name in favorites if name in instruments]
    remaining_instruments = [name for name in instruments if name not in favorite_names]

    active_signals = [s for s in signals if s.get("pair") == active_pair]
    latest_signal = active_signals[0] if active_signals else None
    status_class = "green" if control.get("status") == "tracking" else "amber"
    status_label = "TRACKING" if control.get("status") == "tracking" else "IDLE"

    body = render_template_string(
        """
        <div class=\"hero\">
          <h1>Forex Bot ICC Dashboard</h1>
          <p>Signals only, no trade placement. Watches for ICC indication moves and displays projected entry, stop loss, and take profit for the selected Oanda pair.</p>
        </div>

        <div class=\"grid\">
          <div class=\"card\">
            <h2 class=\"title\">Controls</h2>
            <div style=\"margin-bottom:12px;\">
              <span class=\"pill {{ status_class }}\"><span class=\"dot\"></span>{{ status_label }}</span>
            </div>
            <form method=\"post\" action=\"{{ url_for('submit_controls') }}\">
              <div class=\"label\">Account Mode</div>
              <select name=\"account_mode\">
                <option value=\"demo\" {% if control.account_mode == 'demo' %}selected{% endif %}>Demo</option>
                <option value=\"live\" {% if control.account_mode == 'live' %}selected{% endif %}>Live</option>
              </select>

              <div class=\"label\">Oanda API Key</div>
              <input type=\"password\" name=\"api_key\" value=\"{{ control.api_key }}\" placeholder=\"API key\" />

              <div class=\"label\">Oanda Account ID</div>
              <input type=\"password\" name=\"account_id\" value=\"{{ control.account_id }}\" placeholder=\"Account ID\" />

              <div class=\"label\">Pair</div>
              <select class=\"select\" name=\"selected_instrument\">
                {% if instruments %}
                  <option value=\"\">Select a pair</option>
                  {% if favorite_names %}
                    <optgroup label=\"Favorites\">
                      {% for instrument in favorite_names %}
                        <option value=\"{{ instrument }}\" {% if instrument == active_pair %}selected{% endif %}>★ {{ instrument }}</option>
                      {% endfor %}
                    </optgroup>
                  {% endif %}
                  {% if remaining_instruments %}
                    <optgroup label=\"All Oanda Pairs\">
                      {% for instrument in remaining_instruments %}
                        <option value=\"{{ instrument }}\" {% if instrument == active_pair %}selected{% endif %}>{{ instrument }}</option>
                      {% endfor %}
                    </optgroup>
                  {% endif %}
                {% else %}
                  <option value=\"\" selected>Submit Oanda credentials to load pairs</option>
                {% endif %}
              </select>

              <div class=\"btnrow\">
                <button type=\"submit\">Submit</button>
              </div>
              {% if not instruments and not instrument_error and not control.api_key %}
                <div class=\"help\">Enter your Oanda API key and account ID, then click Submit to load available pairs.</div>
              {% endif %}

              {% if instruments %}
              <div class=\"favorites\">
                <div class=\"label\">Favorites</div>
                <div class=\"help\">Save your most-used pairs so they stay pinned at the top like your other bot.</div>
                <div class=\"favorites-list\">
                  {% for instrument in instruments %}
                    <label class=\"favorite-row\">
                      <span>{{ instrument }}</span>
                      <input type=\"checkbox\" name=\"favorite_instruments\" value=\"{{ instrument }}\" {% if instrument in favorites %}checked{% endif %} />
                    </label>
                  {% endfor %}
                </div>
              </div>
              {% endif %}

              <input type=\"hidden\" name=\"persist_favorites\" value=\"1\" />
            </form>

            <div class=\"btnrow\" style=\"margin-top:12px;\">
              <form method=\"post\" action=\"{{ url_for('start_tracking') }}\"><button type=\"submit\">Start Tracking</button></form>
              <form method=\"post\" action=\"{{ url_for('stop_tracking') }}\"><button class=\"secondary\" type=\"submit\">Stop</button></form>
            </div>

            <div class=\"help\" style=\"margin-top:12px;\">
              Uses Daily, 4H, and 1H structure. Signal fires from the indication move, then shows the projected return-to-level entry, 50 pip stop, and take profit at the indication extreme.
            </div>

            {% if flash %}
              <div class=\"flash {{ kind }}\">{{ flash }}</div>
            {% endif %}
            {% if instrument_error %}
              <div class=\"flash error\">Could not load Oanda instruments: {{ instrument_error }}</div>
            {% endif %}
          </div>

          <div>
            <div class=\"stats\">
              <div class=\"stat\"><div class=\"k\">Selected Pair</div><div class=\"v\">{{ active_pair }}</div></div>
              <div class=\"stat\"><div class=\"k\">Tracked Pairs</div><div class=\"v\">{{ tracked_count }}</div></div>
              <div class=\"stat\"><div class=\"k\">Signals on Dashboard</div><div class=\"v\">{{ signal_count }}</div></div>
            </div>

            <div class=\"card\">
              <h2 class=\"title\">Latest Signal</h2>
              {% if latest_signal %}
                <div class=\"signal\">
                  <div class=\"signal-head\">
                    <div>
                      <div class=\"signal-side {{ 'buy' if latest_signal.side == 'BUY' else 'sell' }}\">{{ latest_signal.side }}</div>
                      <div class=\"help\">{{ latest_signal.pair }} · {{ latest_signal.timeframe_context }}</div>
                    </div>
                    <div class=\"help\">{{ latest_signal.detected_at }}</div>
                  </div>
                  <div class=\"signal-grid\">
                    <div class=\"metric\"><div class=\"k\">Entry</div><div class=\"v\">{{ latest_signal.entry }}</div></div>
                    <div class=\"metric\"><div class=\"k\">Stop Loss</div><div class=\"v\">{{ latest_signal.stop_loss }}</div></div>
                    <div class=\"metric\"><div class=\"k\">Take Profit</div><div class=\"v\">{{ latest_signal.take_profit }}</div></div>
                    <div class=\"metric\"><div class=\"k\">Indication Level</div><div class=\"v\">{{ latest_signal.indication_level }}</div></div>
                  </div>
                  <div class=\"help\" style=\"margin-top:10px;\">{{ latest_signal.bias_notes }}</div>
                </div>
              {% else %}
                <div class=\"help\">No signal yet for this pair. Start tracking after entering your Oanda credentials and pair.</div>
              {% endif %}
            </div>

            <div class=\"card\" style=\"margin-top:16px;\">
              <h2 class=\"title\">Tracked State</h2>
              <div class=\"help\" style=\"white-space:pre-wrap;\">{{ tracked_state }}</div>
            </div>
          </div>
        </div>
        """,
        control=control,
        instruments=instruments,
        active_pair=active_pair,
        tracked_count=(1 if active_pair and isinstance(state.get(active_pair), dict) and state.get(active_pair, {}).get("tracking") else 0),
        signal_count=len(active_signals),
        latest_signal=latest_signal,
        tracked_state=json.dumps(state.get(active_pair, {}), indent=2) if state.get(active_pair) else "No tracking state saved yet.",
        flash=request.args.get("flash", ""),
        kind=request.args.get("kind", "success"),
        instrument_error=instrument_error,
        status_class=status_class,
        status_label=status_label,
        favorites=favorites,
        favorite_names=favorite_names,
        remaining_instruments=remaining_instruments,
    )
    return render_template_string(BASE_HTML, body=body)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8082, debug=True)
