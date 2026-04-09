from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from app import CONTROL_FILE, SIGNALS_FILE, STATE_FILE, build_signal_for_pair, load_control, load_json, save_json

SCAN_INTERVAL_SECONDS = 60


def main() -> None:
    while True:
        control = load_control()
        if control.get("status") != "tracking":
            time.sleep(SCAN_INTERVAL_SECONDS)
            continue

        pair = control.get("selected_instrument")
        if not pair or not control.get("api_key") or not control.get("account_id"):
            time.sleep(SCAN_INTERVAL_SECONDS)
            continue

        state = load_json(STATE_FILE, {})
        signal_store = load_json(SIGNALS_FILE, {"signals": []})

        try:
            signal = build_signal_for_pair(control)
            pair_state = state.get(pair, {}) if isinstance(state.get(pair), dict) else {}
            pair_state.update(
                {
                    "tracking": True,
                    "last_scan_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "last_signal_side": signal.get("side") if signal else None,
                    "last_signal_time": signal.get("detected_at") if signal else None,
                    "signal_active": bool(signal),
                }
            )
            if signal:
                pair_state["active_signal"] = signal
            else:
                pair_state.pop("active_signal", None)
            pair_state.pop("last_error", None)
            state[pair] = pair_state

            signal_store["signals"] = [s for s in signal_store.get("signals", []) if s.get("pair") != pair]
            if signal:
                signal_store["signals"].insert(0, signal)

            save_json(STATE_FILE, state)
            save_json(SIGNALS_FILE, signal_store)
        except Exception as exc:
            pair_state = state.get(pair, {}) if isinstance(state.get(pair), dict) else {}
            pair_state.update(
                {
                    "tracking": True,
                    "last_scan_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "last_error": str(exc),
                }
            )
            state[pair] = pair_state
            save_json(STATE_FILE, state)

        time.sleep(SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
