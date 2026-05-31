#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=================================================================
DELTA COMPARE MODULE
=================================================================
Reads the most recent prior scan for a ticker from DB1
and computes the deltas for:
  - GEX ($M change + direction label)
  - Spot price ($change + % change)
  - Whale Bull% change

Returns a list of Discord embed fields (inline=False):
  {"name": "Since Last Scan", "value": "...", "inline": False}

Fails silently — never blocks the main sweep.
=================================================================
"""
import datetime
import requests

# ── ORDS Config ──────────────────────────────────────────────
_ORDS_BASE = "https://g275356d1414552-trishulapicks.adb.us-ashburn-1.oraclecloudapps.com/ords/admin"
_ORDS_USER = "ADMIN"
_ORDS_PASS = "C1iffyHu5tl3!!!"
_TABLE     = "qmatrix_snapshots"


def _auth():
    return (_ORDS_USER, _ORDS_PASS)


def fetch_last_snapshot(ticker: str) -> dict | None:
    """
    Fetch the most recent snapshot for this ticker that is NOT from the current run
    (i.e., from a different scan_time or a previous scan_date).

    Returns the snapshot dict or None.
    """
    try:
        url    = f"{_ORDS_BASE}/{_TABLE}/"
        params = {
            "q":       f'{{\"ticker\":\"{ticker.upper()}\"}}',
            "limit":   5,
            "orderby": "scan_ts desc",
        }
        r = requests.get(url, auth=_auth(), params=params, timeout=10)
        if r.status_code != 200:
            return None

        items = r.json().get("items", [])
        if not items:
            return None

        # Grab the second-most-recent snapshot if it exists (skip the just-posted one)
        # If only 1 exists, use it (first scan delta from itself = 0, handled gracefully)
        now_ts = datetime.datetime.now()
        # Return the first item that is > 30 minutes old (not the current run)
        for item in items:
            ts_raw = item.get("scan_ts") or item.get("SCAN_TS", "")
            if not ts_raw:
                return item  # fallback
            try:
                # Oracle ORDS returns ISO format like "2026-05-31T12:00:00Z"
                ts_raw_clean = ts_raw.rstrip("Z").split(".")[0]
                item_ts = datetime.datetime.fromisoformat(ts_raw_clean)
                if (now_ts - item_ts).total_seconds() > 1800:  # >30 min = previous scan
                    return item
            except Exception:
                return item  # can't parse — just use it

        return items[-1]  # use oldest if all are recent
    except Exception as e:
        print(f"  [DELTA] fetch_last_snapshot error: {str(e)[:80]}")
        return None


def compute_delta_fields(
    ticker: str,
    current_spot: float,
    current_gex_m: float,
    current_gex_zero: float | None,
    current_whale_bull_pct: float | None,
) -> list[dict]:
    """
    Compare current metrics against last DB1 snapshot.

    Returns a list of Discord embed field dicts.
    Returns empty list if no prior snapshot or delta is trivial.
    """
    try:
        prev = fetch_last_snapshot(ticker)
        if prev is None:
            return []

        def _get(d, *keys):
            """Try multiple key variants (Oracle returns uppercase sometimes)."""
            for k in keys:
                v = d.get(k) or d.get(k.upper()) or d.get(k.lower())
                if v is not None:
                    return v
            return None

        prev_spot          = _get(prev, "spot",            "SPOT")
        prev_gex_m         = _get(prev, "net_gex_m",       "NET_GEX_M")
        prev_whale_bull    = _get(prev, "whale_bull_pct",   "WHALE_BULL_PCT")
        prev_gex_zero      = _get(prev, "gex_zero",         "GEX_ZERO")
        prev_scan_time     = _get(prev, "scan_time",        "SCAN_TIME") or "?"
        prev_scan_date     = _get(prev, "scan_date",        "SCAN_DATE") or "?"

        lines = []

        # ── Spot delta ──
        if prev_spot is not None:
            try:
                ps    = float(prev_spot)
                cs    = float(current_spot)
                delta_price = cs - ps
                delta_pct   = (delta_price / ps * 100) if ps else 0
                sign        = "+" if delta_price >= 0 else ""
                color_emoji = "🟢" if delta_price >= 0 else "🔴"
                lines.append(
                    f"{color_emoji} **Spot:** `{sign}${delta_price:.2f}` (`{sign}{delta_pct:.2f}%`)"
                )
            except Exception:
                pass

        # ── GEX delta ──
        if prev_gex_m is not None:
            try:
                pg      = float(prev_gex_m)
                cg      = float(current_gex_m)
                delta_g = cg - pg
                sign    = "+" if delta_g >= 0 else ""
                # Use gex_zero level if available; fall back to current spot
                lvl     = current_gex_zero or prev_gex_zero or current_spot
                lvl_str = f"${float(lvl):.0f}" if lvl else "N/A"
                direction = "building 🔼" if delta_g >= 0 else "fading 🔽"
                lines.append(
                    f"📊 **GEX:** `{sign}{delta_g:.2f}M` @ {lvl_str} ({direction})"
                )
            except Exception:
                pass

        # ── Whale Bull% delta ──
        if prev_whale_bull is not None and current_whale_bull_pct is not None:
            try:
                pw   = float(prev_whale_bull)
                cw   = float(current_whale_bull_pct)
                dw   = cw - pw
                sign = "+" if dw >= 0 else ""
                direction = "more bullish 🐂" if dw >= 0 else "more bearish 🐻"
                lines.append(
                    f"🐋 **Whale Bull%:** `{sign}{dw:.1f}%` {direction}"
                )
            except Exception:
                pass

        if not lines:
            return []

        return [{
            "name":   f"📈 Since Last Scan ({prev_scan_date} {prev_scan_time})",
            "value":  "\n".join(lines),
            "inline": False,
        }]

    except Exception as e:
        print(f"  [DELTA] compute_delta_fields error: {str(e)[:80]}")
        return []


# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("[DELTA] Testing delta compare for SPY...")
    fields = compute_delta_fields(
        ticker="SPY",
        current_spot=535.00,
        current_gex_m=12.5,
        current_gex_zero=532.0,
        current_whale_bull_pct=58.3,
    )
    for f in fields:
        print(f"  {f['name']}: {f['value']}")
