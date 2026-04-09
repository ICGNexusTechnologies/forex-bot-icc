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
DEFAULT_ALERT_PHONE = "4015591113"
PIP_OVERRIDES = {
    "JPY": 0.01,
}
TIMEFRAME_CONFIG = {
    "D": {"granularity": "D", "count": 120},
    "H4": {"granularity": "H4", "count": 160},
    "H1": {"granularity": "H1", "count": 240},
    "M15": {"granularity": "M15", "count": 320},
}
SWING_LOOKBACK = {
    "D": 20,
    "H4": 24,
    "H1": 30,
}
MAX_SIGNAL_AGE_HOURS = 12

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
    .picker {
      position: relative;
      margin-bottom: 12px;
    }
    .picker-button {
      width: 100%;
      background: rgba(2,6,23,.9);
      color: var(--text);
      border: 1px solid rgba(255,255,255,.08);
      border-radius: 12px;
      padding: 10px 12px;
      font-size: .9rem;
      text-align: left;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .picker-panel {
      position: absolute;
      top: calc(100% + 6px);
      left: 0;
      right: 0;
      background: rgba(8,16,31,.98);
      border: 1px solid rgba(255,255,255,.08);
      border-radius: 14px;
      box-shadow: 0 18px 40px rgba(0,0,0,.3);
      padding: 10px;
      z-index: 30;
      max-height: 320px;
      overflow: hidden;
    }
    .picker-search {
      margin-bottom: 8px;
    }
    .picker-list {
      max-height: 240px;
      overflow: auto;
      display: grid;
      gap: 6px;
    }
    .picker-group-label {
      color: var(--muted);
      font-size: .72rem;
      text-transform: uppercase;
      letter-spacing: .08em;
      margin: 8px 0 4px;
    }
    .picker-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      padding: 8px 10px;
      border-radius: 10px;
      background: rgba(2,6,23,.55);
      border: 1px solid rgba(255,255,255,.05);
      cursor: pointer;
    }
    .picker-row.active {
      border-color: rgba(99,102,241,.7);
      background: rgba(99,102,241,.16);
    }
    .picker-star {
      appearance: none;
      border: none;
      background: transparent;
      cursor: pointer;
      font-size: 16px;
      line-height: 1;
      color: #fbbf24;
      padding: 0;
    }
    .picker-star.off { color: #64748b; }
    .hidden-input { display: none; }
    .is-hidden { display: none; }
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
    button:disabled {
      opacity: .55;
      cursor: not-allowed;
      filter: grayscale(.15);
    }
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

    function togglePicker() {
      const panel = document.getElementById('pair-picker-panel');
      if (!panel) return;
      panel.classList.toggle('is-hidden');
    }

    function closePicker() {
      const panel = document.getElementById('pair-picker-panel');
      if (!panel) return;
      panel.classList.add('is-hidden');
    }

    function selectPair(pair) {
      const input = document.getElementById('selected_instrument');
      const label = document.getElementById('pair-picker-label');
      if (input) input.value = pair;
      if (label) label.textContent = pair || 'Select a pair';
      document.querySelectorAll('.picker-row').forEach((row) => {
        row.classList.toggle('active', row.getAttribute('data-pair') === pair);
      });
      closePicker();
    }

    function toggleFavorite(pair, event) {
      event.stopPropagation();
      const checkbox = document.querySelector(`input[data-favorite="${pair}"]`);
      const star = document.querySelector(`button[data-star="${pair}"]`);
      if (!checkbox || !star) return;
      checkbox.checked = !checkbox.checked;
      star.textContent = checkbox.checked ? '★' : '☆';
      star.classList.toggle('off', !checkbox.checked);
    }

    function filterPairs() {
      const query = (document.getElementById('pair-search')?.value || '').toUpperCase();
      document.querySelectorAll('.picker-row').forEach((row) => {
        const pair = (row.getAttribute('data-pair') || '').toUpperCase();
        row.classList.toggle('is-hidden', !!query && !pair.includes(query));
      });
      document.querySelectorAll('.picker-group').forEach((group) => {
        const visible = group.querySelector('.picker-row:not(.is-hidden)');
        group.classList.toggle('is-hidden', !visible);
      });
    }

    window.addEventListener('click', (event) => {
      const picker = document.getElementById('pair-picker');
      if (!picker) return;
      if (!picker.contains(event.target)) closePicker();
    });
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
        "notify_enabled": True,
        "alert_phone": DEFAULT_ALERT_PHONE,
        "alert_service": "auto",
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
    value = value.replace("Z", "+00:00")
    if "." in value:
        head, tail = value.split(".", 1)
        frac = tail
        suffix = ""
        for marker in ("+", "-"):
            idx = frac.find(marker)
            if idx > 0:
                suffix = frac[idx:]
                frac = frac[:idx]
                break
        frac = frac[:6]
        value = f"{head}.{frac}{suffix}" if frac else f"{head}{suffix}"
    return datetime.fromisoformat(value)


def format_display_time(value: str | None) -> str:
    if not value:
        return "—"
    try:
        dt = parse_oanda_time(value)
        return dt.astimezone().strftime("%b %d, %Y %I:%M:%S %p")
    except Exception:
        return value


def build_signal_text(signal: dict[str, Any]) -> str:
    return (
        f"ICC signal: {signal.get('pair', 'Unknown')} {signal.get('side', '')}\n"
        f"Entry: {signal.get('entry', '—')}\n"
        f"Stop Loss: {signal.get('stop_loss', '—')}\n"
        f"Take Profit: {signal.get('take_profit', '—')}"
    )


def send_text_message(control: dict[str, Any], message: str) -> None:
    if not control.get("notify_enabled"):
        return
    alert_phone = (control.get("alert_phone") or "").strip()
    if not alert_phone:
        return
    alert_service = (control.get("alert_service") or "auto").strip() or "auto"
    subprocess.run(
        [
            "/opt/homebrew/bin/imsg",
            "send",
            "--to",
            alert_phone,
            "--text",
            message,
            "--service",
            alert_service,
        ],
        check=True,
        timeout=30,
    )


def send_signal_text(control: dict[str, Any], signal: dict[str, Any]) -> None:
    send_text_message(control, build_signal_text(signal))


def is_swing_high(candles: list[dict[str, Any]], idx: int) -> bool:
    if idx <= 0 or idx >= len(candles) - 1:
        return False
    current = candles[idx]["high"]
    return current > candles[idx - 1]["high"] and current >= candles[idx + 1]["high"]


def is_swing_low(candles: list[dict[str, Any]], idx: int) -> bool:
    if idx <= 0 or idx >= len(candles) - 1:
        return False
    current = candles[idx]["low"]
    return current < candles[idx - 1]["low"] and current <= candles[idx + 1]["low"]


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
    if len(candles) < 5:
        return None, None, None
    start = max(2, len(candles) - lookback)
    for idx in range(len(candles) - 1, start - 1, -1):
        candle = candles[idx]
        body_high = max(candle["open"], candle["close"])
        body_low = min(candle["open"], candle["close"])

        if side == "BUY":
            reference_idx = None
            for prev_idx in range(idx - 1, 1, -1):
                if is_swing_high(candles, prev_idx):
                    reference_idx = prev_idx
                    break
            if reference_idx is None:
                continue
            reference = candles[reference_idx]["high"]
            if body_high > reference:
                return idx, reference, candle["high"]
        else:
            reference_idx = None
            for prev_idx in range(idx - 1, 1, -1):
                if is_swing_low(candles, prev_idx):
                    reference_idx = prev_idx
                    break
            if reference_idx is None:
                continue
            reference = candles[reference_idx]["low"]
            if body_low < reference:
                return idx, reference, candle["low"]
    return None, None, None


def signal_is_fresh(signal_time: str) -> bool:
    try:
        detected = parse_oanda_time(signal_time)
    except Exception:
        return False
    age_hours = (datetime.now(timezone.utc) - detected.astimezone(timezone.utc)).total_seconds() / 3600
    return age_hours <= MAX_SIGNAL_AGE_HOURS


def find_m15_precontinuation_entry(
    candles: list[dict[str, Any]],
    indication_time: str,
    indication_level: float,
    side: str,
) -> tuple[str | None, str]:
    if len(candles) < 8:
        return None, "Not enough M15 candles"
    try:
        indication_dt = parse_oanda_time(indication_time)
    except Exception:
        return None, "Invalid indication time"

    post = [c for c in candles if parse_oanda_time(c["time"]) >= indication_dt]
    if len(post) < 4:
        return None, "Waiting for correction after indication"

    if side == "BUY":
        for idx in range(2, len(post)):
            candle = post[idx]
            if candle["low"] > indication_level:
                continue
            body_high = max(candle["open"], candle["close"])
            body_low = min(candle["open"], candle["close"])
            upper_wick = candle["high"] - body_high
            lower_wick = body_low - candle["low"]
            if body_high > indication_level and upper_wick >= lower_wick:
                return candle["time"], "Correction hit the level and M15 turned back up"
        return None, "Waiting for bullish turn in correction zone"

    for idx in range(2, len(post)):
        candle = post[idx]
        if candle["high"] < indication_level:
            continue
        body_high = max(candle["open"], candle["close"])
        body_low = min(candle["open"], candle["close"])
        upper_wick = candle["high"] - body_high
        lower_wick = body_low - candle["low"]
        if body_low < indication_level and lower_wick >= upper_wick:
            return candle["time"], "Correction hit the level and M15 turned back down"
    return None, "Waiting for bearish turn in correction zone"


def evaluate_icc_phases(instrument: str, candles_by_tf: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    h1 = candles_by_tf.get("H1") or []
    h4 = candles_by_tf.get("H4") or []
    daily = candles_by_tf.get("D") or []
    m15 = candles_by_tf.get("M15") or []
    result: dict[str, Any] = {
        "signal": None,
        "phase_state": {
            "side": None,
            "indication": False,
            "correction": False,
            "continuation": False,
            "entry": None,
            "take_profit": None,
            "indication_level": None,
            "note": "No valid setup yet",
        },
    }
    if len(h1) < 40 or len(h4) < 20 or len(daily) < 10 or len(m15) < 20:
        result["phase_state"]["note"] = "Not enough market data yet"
        return result

    buy_idx, buy_level, buy_extreme = find_recent_breakout(h1, "BUY", SWING_LOOKBACK["H1"])
    sell_idx, sell_level, sell_extreme = find_recent_breakout(h1, "SELL", SWING_LOOKBACK["H1"])

    candidates = [
        ("BUY", buy_idx, buy_level, buy_extreme),
        ("SELL", sell_idx, sell_level, sell_extreme),
    ]
    freshest = None
    for side, breakout_index, level, extreme in candidates:
        if breakout_index is None or level is None or extreme is None:
            continue
        breakout_candle = h1[breakout_index]
        if freshest is None or breakout_candle["time"] > freshest["time"]:
            freshest = {
                "side": side,
                "breakout_index": breakout_index,
                "level": level,
                "extreme": extreme,
                "time": breakout_candle["time"],
            }

    if freshest is None:
        return result

    side = freshest["side"]
    level = freshest["level"]
    extreme = freshest["extreme"]
    breakout_time = freshest["time"]
    continuation_time, continuation_note = find_m15_precontinuation_entry(m15, breakout_time, level, side)
    phase_state = {
        "side": side,
        "indication": True,
        "correction": "correction" in continuation_note.lower() or "zone" in continuation_note.lower(),
        "continuation": continuation_time is not None,
        "entry": format_price(instrument, level),
        "take_profit": format_price(instrument, extreme),
        "indication_level": format_price(instrument, level),
        "note": continuation_note,
    }
    result["phase_state"] = phase_state

    if continuation_time is None:
        return result

    pip = pip_size(instrument)
    stop_distance = 50 * pip
    stop_loss = level - stop_distance if side == "BUY" else level + stop_distance
    signal = {
        "pair": instrument,
        "side": side,
        "timeframe_context": "Daily / 4H / 1H / 15M",
        "detected_at": continuation_time,
        "entry": format_price(instrument, level),
        "stop_loss": format_price(instrument, stop_loss),
        "take_profit": format_price(instrument, extreme),
        "indication_level": format_price(instrument, level),
        "indication_extreme": format_price(instrument, extreme),
        "bias_notes": (
            f"Daily bias: {timeframe_bias(daily)}, 4H bias: {timeframe_bias(h4)}, "
            f"1H body break through recent {'high' if side == 'BUY' else 'low'}, "
            f"15M turn detected in correction zone"
        ),
        "continuation_note": continuation_note,
    }
    if not signal_is_fresh(signal["detected_at"]):
        return result
    result["signal"] = signal
    return result


def detect_icc_signal(instrument: str, candles_by_tf: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
    return evaluate_icc_phases(instrument, candles_by_tf).get("signal")


def build_signal_for_pair(control: dict[str, Any]) -> dict[str, Any] | None:
    api_key = control.get("api_key", "")
    instrument = control.get("selected_instrument", "")
    if not api_key or not instrument:
        return None
    candles_by_tf: dict[str, list[dict[str, Any]]] = {}
    for tf, cfg in TIMEFRAME_CONFIG.items():
        candles_by_tf[tf] = fetch_candles(api_key, instrument, control.get("account_mode", "demo"), cfg["granularity"], cfg["count"])
    return detect_icc_signal(instrument, candles_by_tf)


def build_phase_state_for_pair(control: dict[str, Any]) -> dict[str, Any]:
    api_key = control.get("api_key", "")
    instrument = control.get("selected_instrument", "")
    if not api_key or not instrument:
        return {
            "side": None,
            "indication": False,
            "correction": False,
            "continuation": False,
            "entry": None,
            "take_profit": None,
            "indication_level": None,
            "note": "Missing pair or Oanda credentials",
        }
    candles_by_tf: dict[str, list[dict[str, Any]]] = {}
    for tf, cfg in TIMEFRAME_CONFIG.items():
        candles_by_tf[tf] = fetch_candles(api_key, instrument, control.get("account_mode", "demo"), cfg["granularity"], cfg["count"])
    return evaluate_icc_phases(instrument, candles_by_tf).get("phase_state") or {
        "side": None,
        "indication": False,
        "correction": False,
        "continuation": False,
        "entry": None,
        "take_profit": None,
        "indication_level": None,
        "note": "No valid setup yet",
    }


@app.post("/submit")
def submit_controls():
    control = load_control()
    control["account_mode"] = "live" if request.form.get("account_mode") == "live" else "demo"
    selected_instrument = request.form.get("selected_instrument", "").strip()
    if selected_instrument.startswith("★ "):
        selected_instrument = selected_instrument[2:]
    if selected_instrument:
        control["selected_instrument"] = selected_instrument
    control["notify_enabled"] = request.form.get("notify_enabled") == "on"
    control["alert_phone"] = request.form.get("alert_phone", control.get("alert_phone", DEFAULT_ALERT_PHONE)).strip()
    control["alert_service"] = request.form.get("alert_service", control.get("alert_service", "auto")).strip() or "auto"
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

    if signal and pair_state.get("last_alerted_signal_time") != signal.get("detected_at"):
        try:
            send_signal_text(control, signal)
            pair_state["last_alerted_signal_time"] = signal.get("detected_at")
            state[pair] = pair_state
            save_json(STATE_FILE, state)
        except Exception as exc:
            pair_state["last_error"] = f"Text alert failed: {exc}"
            state[pair] = pair_state
            save_json(STATE_FILE, state)

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
    if not isinstance(favorites, list):
        favorites = []
    if instruments and active_pair and active_pair not in instruments:
        instruments = [active_pair] + [instrument for instrument in instruments if instrument != active_pair]
    instrument_names = instruments[:]
    favorite_names = [name for name in favorites if name in instrument_names] or favorites
    remaining_instruments = [name for name in instrument_names if name not in favorite_names]

    active_signals = [s for s in signals if s.get("pair") == active_pair]
    latest_signal = active_signals[0] if active_signals else None
    phase_state = build_phase_state_for_pair(control) if control.get("api_key") and active_pair else {
        "side": None,
        "indication": False,
        "correction": False,
        "continuation": False,
        "entry": None,
        "take_profit": None,
        "indication_level": None,
        "note": "Missing pair or Oanda credentials",
    }
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

              <div class=\"label\">Text Alerts</div>
              <label class=\"help\" style=\"display:flex; align-items:center; gap:8px; margin-bottom:8px;\">
                <input type=\"checkbox\" name=\"notify_enabled\" {% if control.notify_enabled %}checked{% endif %} style=\"width:auto; margin:0;\" />
                Text me when a signal is put out
              </label>
              <input type=\"text\" name=\"alert_phone\" value=\"{{ control.alert_phone }}\" placeholder=\"Phone number\" />
              <select name=\"alert_service\">
                <option value=\"auto\" {% if control.alert_service == 'auto' %}selected{% endif %}>Auto</option>
                <option value=\"imessage\" {% if control.alert_service == 'imessage' %}selected{% endif %}>iMessage</option>
                <option value=\"sms\" {% if control.alert_service == 'sms' %}selected{% endif %}>SMS</option>
              </select>

              <div class=\"label\">Pair</div>
              <input id=\"selected_instrument\" class=\"hidden-input\" name=\"selected_instrument\" value=\"{{ control.selected_instrument }}\" />
              {% for name in instrument_names %}
                <input class=\"hidden-input\" type=\"checkbox\" name=\"favorite_instruments\" value=\"{{ name }}\" data-favorite=\"{{ name }}\" {% if name in favorites %}checked{% endif %} />
              {% endfor %}
              <div id=\"pair-picker\" class=\"picker\">
                <button class=\"picker-button\" type=\"button\" onclick=\"togglePicker()\">
                  <span id=\"pair-picker-label\">{{ control.selected_instrument or 'Select a pair' }}</span>
                  <span>▾</span>
                </button>
                <div id=\"pair-picker-panel\" class=\"picker-panel is-hidden\">
                  <input id=\"pair-search\" class=\"picker-search\" type=\"text\" placeholder=\"Search pairs\" oninput=\"filterPairs()\" />
                  <div class=\"picker-list\">
                    {% if favorite_names %}
                    <div class=\"picker-group\">
                      <div class=\"picker-group-label\">Favorites</div>
                      {% for name in favorite_names %}
                        <div class=\"picker-row {% if name == control.selected_instrument %}active{% endif %}\" data-pair=\"{{ name }}\" onclick=\"selectPair('{{ name }}')\">
                          <span>★ {{ name }}</span>
                          <button class=\"picker-star\" type=\"button\" data-star=\"{{ name }}\" onclick=\"toggleFavorite('{{ name }}', event)\">★</button>
                        </div>
                      {% endfor %}
                    </div>
                    {% endif %}
                    {% if remaining_instruments %}
                    <div class=\"picker-group\">
                      <div class=\"picker-group-label\">All OANDA Instruments</div>
                      {% for name in remaining_instruments %}
                        <div class=\"picker-row {% if name == control.selected_instrument %}active{% endif %}\" data-pair=\"{{ name }}\" onclick=\"selectPair('{{ name }}')\">
                          <span>{{ name }}</span>
                          <button class=\"picker-star {% if name not in favorites %}off{% endif %}\" type=\"button\" data-star=\"{{ name }}\" onclick=\"toggleFavorite('{{ name }}', event)\">{{ '★' if name in favorites else '☆' }}</button>
                        </div>
                      {% endfor %}
                    </div>
                    {% endif %}
                    {% if not instrument_names %}
                      <div class=\"help\">Submit Oanda credentials to load pairs</div>
                    {% endif %}
                  </div>
                </div>
              </div>

              <div class=\"btnrow\">
                <button type=\"submit\">Submit</button>
              </div>
              {% if not instruments and not instrument_error and not control.api_key %}
                <div class=\"help\">Enter your Oanda API key and account ID, then click Submit to load available pairs.</div>
              {% endif %}

            </form>

            <div class=\"btnrow\" style=\"margin-top:12px;\">
              <form method=\"post\" action=\"{{ url_for('start_tracking') }}\"><button type=\"submit\" {% if control.status == 'tracking' %}disabled{% endif %}>Start</button></form>
              <form method=\"post\" action=\"{{ url_for('stop_tracking') }}\"><button class=\"secondary\" type=\"submit\" {% if control.status != 'tracking' %}disabled{% endif %}>Stop</button></form>
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

            <div class="card">
              <h2 class="title">Latest Signal</h2>
              <div class="signal" style="margin-bottom:14px;">
                <div class="signal-head">
                  <div>
                    <div class="signal-side {% if phase_state.side == 'BUY' %}buy{% elif phase_state.side == 'SELL' %}sell{% endif %}">{{ phase_state.side or 'WAITING' }}</div>
                    <div class="help">{{ active_pair }} · Current ICC phase</div>
                  </div>
                  <div class="help">{{ phase_state.note }}</div>
                </div>
                <div style="display:grid; gap:8px; margin-top:12px;">
                  <div class="metric" style="display:flex; justify-content:space-between; align-items:center; opacity:{{ '1' if phase_state.indication else '.45' }};">
                    <div class="k">Indication</div><div class="v">{{ '✅' if phase_state.indication else '⬜' }}</div>
                  </div>
                  <div class="metric" style="display:flex; justify-content:space-between; align-items:center; opacity:{{ '1' if phase_state.correction else '.45' }};">
                    <div class="k">Correction</div><div class="v">{{ '✅' if phase_state.correction else '⬜' }}</div>
                  </div>
                  <div class="metric" style="display:flex; justify-content:space-between; align-items:center; opacity:{{ '1' if phase_state.continuation else '.45' }};">
                    <div class="k">Continuation Ready</div><div class="v">{{ '✅' if phase_state.continuation else '⬜' }}</div>
                  </div>
                </div>
                <div class="signal-grid" style="margin-top:12px;">
                  <div class="metric"><div class="k">Planned Entry</div><div class="v">{{ phase_state.entry or '—' }}</div></div>
                  <div class="metric"><div class="k">Planned TP</div><div class="v">{{ phase_state.take_profit or '—' }}</div></div>
                  <div class="metric"><div class="k">Indication Level</div><div class="v">{{ phase_state.indication_level or '—' }}</div></div>
                </div>
              </div>
              {% if latest_signal %}
                <div class="signal">
                  <div class="signal-head">
                    <div>
                      <div class="signal-side {{ 'buy' if latest_signal.side == 'BUY' else 'sell' }}">{{ latest_signal.side }}</div>
                      <div class="help">{{ latest_signal.pair }} · {{ latest_signal.timeframe_context }}</div>
                    </div>
                    <div class="help">{{ latest_signal.detected_at }}</div>
                  </div>
                  <div class="signal-grid">
                    <div class="metric"><div class="k">Entry</div><div class="v">{{ latest_signal.entry }}</div></div>
                    <div class="metric"><div class="k">Stop Loss</div><div class="v">{{ latest_signal.stop_loss }}</div></div>
                    <div class="metric"><div class="k">Take Profit</div><div class="v">{{ latest_signal.take_profit }}</div></div>
                    <div class="metric"><div class="k">Indication Level</div><div class="v">{{ latest_signal.indication_level }}</div></div>
                  </div>
                  <div class="help" style="margin-top:10px;">{{ latest_signal.bias_notes }}</div>
                </div>
              {% else %}
                <div class="help">No signal yet for this pair. Start tracking after entering your Oanda credentials and pair.</div>
              {% endif %}
            </div>
            <div class=\"card\" style=\"margin-top:16px;\">
              <h2 class=\"title\">Tracked State</h2>
              <div class=\"signal-grid\">
                <div class=\"metric\"><div class=\"k\">Tracking</div><div class=\"v\">{{ 'Active' if pair_state.tracking else 'Stopped' }}</div></div>
                <div class=\"metric\"><div class=\"k\">Signal Status</div><div class=\"v\">{{ 'Active' if pair_state.signal_active else 'No Active Signal' }}</div></div>
                <div class=\"metric\"><div class=\"k\">Started</div><div class=\"v\">{{ started_at_display }}</div></div>
                <div class=\"metric\"><div class=\"k\">Last Scan</div><div class=\"v\">{{ last_scan_display }}</div></div>
                <div class=\"metric\"><div class=\"k\">Last Side</div><div class=\"v\">{{ pair_state.last_signal_side or '—' }}</div></div>
                <div class=\"metric\"><div class=\"k\">Last Signal Time</div><div class=\"v\">{{ last_signal_time_display }}</div></div>
                <div class=\"metric\"><div class=\"k\">Entry</div><div class=\"v\">{{ active_signal.entry if active_signal else '—' }}</div></div>
                <div class=\"metric\"><div class=\"k\">Stop Loss</div><div class=\"v\">{{ active_signal.stop_loss if active_signal else '—' }}</div></div>
                <div class=\"metric\"><div class=\"k\">Take Profit</div><div class=\"v\">{{ active_signal.take_profit if active_signal else '—' }}</div></div>
              </div>
              {% if pair_state.last_error %}
                <div class=\"flash error\" style=\"margin-top:12px;\">{{ pair_state.last_error }}</div>
              {% endif %}
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
        phase_state=phase_state,
        pair_state=(state.get(active_pair, {}) if isinstance(state.get(active_pair), dict) else {}),
        active_signal=((state.get(active_pair, {}) if isinstance(state.get(active_pair), dict) else {}).get("active_signal") or latest_signal),
        started_at_display=format_display_time((state.get(active_pair, {}) if isinstance(state.get(active_pair), dict) else {}).get("started_at")),
        last_scan_display=format_display_time((state.get(active_pair, {}) if isinstance(state.get(active_pair), dict) else {}).get("last_scan_at")),
        last_signal_time_display=format_display_time((state.get(active_pair, {}) if isinstance(state.get(active_pair), dict) else {}).get("last_signal_time")),
        flash=request.args.get("flash", ""),
        kind=request.args.get("kind", "success"),
        instrument_error=instrument_error,
        status_class=status_class,
        status_label=status_label,
        instrument_names=instrument_names,
        favorites=favorites,
        favorite_names=favorite_names,
        remaining_instruments=remaining_instruments,
    )
    return render_template_string(BASE_HTML, body=body)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8082, debug=True)
