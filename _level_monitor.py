#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=================================================================
LEVEL MONITOR — Real-Time GEX Zero + Max Pain Break Alerts
=================================================================
Polls spot price every 60 seconds for all active tickers.

Alerts triggered when:
  1. Spot crosses the GEX zero level (sign flip)
  2. Spot crosses Max Pain ± 0.5%

Discord alert color:
  - Bullish cross → GREEN  (0x3fb950)
  - Bearish cross → RED    (0xf85149)

Throttle: 1 alert per level per ticker per hour.

Designed to run as a background thread inside sovereign_watchdog.py.
Can also run standalone: python _level_monitor.py

=================================================================
"""
import time
import json
import threading
import datetime
import requests

# ── Import scanner config (webhooks) ─────────────────────────
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from sovereign_options_scanner import get_webhook, TICKERS as _DEFAULT_TICKERS
    _SCANNER_AVAILABLE = True
except Exception:
    _SCANNER_AVAILABLE = False
    _DEFAULT_TICKERS = ["SPY", "QQQ", "IWM", "TSLA", "NVDA", "AMZN", "AAPL", "MSFT"]

# Fallback webhook — macro channel
_FALLBACK_WEBHOOK = "https://discord.com/api/webhooks/1508273976558882906/Scvp9yK6mmfrEJ7hMu38fJn24Fa7TljEeSs4tL0xHwfOIs_0P26mhrbaFuzwoxEgy5F5"

POLL_INTERVAL_SECS = 60      # seconds between spot polls
THROTTLE_SECS      = 3600    # 1 alert per level per ticker per hour
MAX_PAIN_TOL_PCT   = 0.005   # ±0.5% for Max Pain cross

# ── ORDS — pull latest snapshot levels ───────────────────────
_ORDS_BASE = "https://g275356d1414552-trishulapicks.adb.us-ashburn-1.oraclecloudapps.com/ords/admin"
_ORDS_AUTH = ("ADMIN", "C1iffyHu5tl3!!!")
_TABLE     = "qmatrix_snapshots"


def _fetch_levels(ticker: str) -> dict | None:
    """
    Pull the most recent snapshot from DB1 for this ticker.
    Returns dict with keys: spot, gex_zero, max_pain, net_gex_m  — or None.
    """
    try:
        url    = f"{_ORDS_BASE}/{_TABLE}/"
        params = {
            "q":       f'{{"ticker":"{ticker.upper()}"}}',
            "limit":   1,
            "orderby": "scan_ts desc",
        }
        r = requests.get(url, auth=_ORDS_AUTH, params=params, timeout=8)
        if r.status_code != 200:
            return None
        items = r.json().get("items", [])
        if not items:
            return None
        item = items[0]
        def _get(d, *keys):
            for k in keys:
                v = d.get(k) or d.get(k.upper()) or d.get(k.lower())
                if v is not None:
                    return v
            return None
        return {
            "gex_zero":  _get(item, "gex_zero",  "GEX_ZERO"),
            "max_pain":  _get(item, "max_pain",   "MAX_PAIN"),
            "net_gex_m": _get(item, "net_gex_m",  "NET_GEX_M"),
            "spot":      _get(item, "spot",        "SPOT"),
        }
    except Exception:
        return None


def _get_spot(ticker: str) -> float | None:
    """Fetch current spot price via yfinance fast_info."""
    try:
        import yfinance as yf
        tk   = yf.Ticker(ticker)
        return float(tk.fast_info.last_price)
    except Exception:
        return None


def _get_webhook(ticker: str) -> str:
    if _SCANNER_AVAILABLE:
        try:
            return get_webhook(symbol=ticker)
        except Exception:
            pass
    return _FALLBACK_WEBHOOK


def _post_alert(ticker: str, title: str, description: str, color: int, spot: float, level: float):
    """Post a level-break alert embed to Discord."""
    webhook = _get_webhook(ticker)
    embed   = {
        "title":       f"⚡ LEVEL BREAK — {ticker}  |  {title}",
        "description": description,
        "color":       color,
        "fields": [
            {"name": "Current Spot",  "value": f"`${spot:.2f}`",  "inline": True},
            {"name": "Level Breached","value": f"`${level:.2f}`", "inline": True},
            {"name": "Time",         "value": f"`{datetime.datetime.now().strftime('%H:%M:%S ET')}`", "inline": True},
        ],
        "footer":    {"text": "Q-Matrix Level Monitor  ·  Trishula QuantNode"},
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    try:
        r = requests.post(webhook, json={"embeds": [embed]}, timeout=10)
        if r.status_code not in (200, 204):
            print(f"  [MONITOR] Alert POST error {r.status_code}: {r.text[:80]}")
        else:
            print(f"  [MONITOR] 🔔 Alert sent: {ticker} — {title}")
    except Exception as e:
        print(f"  [MONITOR] Alert send error: {e}")


class _ThrottleRegistry:
    """Tracks last-alert timestamps per (ticker, level_key) pair."""

    def __init__(self):
        self._lock     = threading.Lock()
        self._registry = {}   # key -> datetime of last alert

    def can_fire(self, key: str) -> bool:
        with self._lock:
            last = self._registry.get(key)
            if last is None:
                return True
            return (datetime.datetime.now() - last).total_seconds() >= THROTTLE_SECS

    def mark(self, key: str):
        with self._lock:
            self._registry[key] = datetime.datetime.now()


class LevelMonitor:
    """
    Polls spot price for each ticker every POLL_INTERVAL_SECS.
    Fires Discord alerts on GEX zero / Max Pain crosses.
    """

    def __init__(self, tickers: list[str] | None = None):
        self.tickers   = tickers or _DEFAULT_TICKERS
        self.throttle  = _ThrottleRegistry()
        self._stop_evt = threading.Event()

        # Per-ticker state: tracks previous spot to detect crosses
        self._prev_spot: dict[str, float] = {}
        # Cached levels from DB1 (refreshed every ~30 min)
        self._levels:    dict[str, dict]  = {}
        self._levels_ts: dict[str, float] = {}

    def _refresh_levels(self, ticker: str):
        """Refresh DB1 levels if cache is stale (>30 min)."""
        now   = time.monotonic()
        last  = self._levels_ts.get(ticker, 0)
        if now - last > 1800:
            lvl = _fetch_levels(ticker)
            if lvl:
                self._levels[ticker]    = lvl
                self._levels_ts[ticker] = now
                print(f"  [MONITOR] {ticker}: levels refreshed — "
                      f"GEX0={lvl.get('gex_zero')} MP={lvl.get('max_pain')}")

    def _check_ticker(self, ticker: str):
        """Check one ticker for level breaks."""
        self._refresh_levels(ticker)
        lvls = self._levels.get(ticker)
        if not lvls:
            return

        spot = _get_spot(ticker)
        if spot is None:
            return

        prev = self._prev_spot.get(ticker)
        self._prev_spot[ticker] = spot

        if prev is None:
            return   # first poll — no cross possible

        gex_zero  = lvls.get("gex_zero")
        max_pain  = lvls.get("max_pain")
        net_gex_m = float(lvls.get("net_gex_m") or 0)

        # ── 1. GEX Zero Cross ──────────────────────────────────
        if gex_zero is not None:
            try:
                gz = float(gex_zero)
                cross_key = f"{ticker}:gex_zero:{gz:.0f}"
                crossed_up   = prev < gz <= spot
                crossed_down = prev > gz >= spot
                if (crossed_up or crossed_down) and self.throttle.can_fire(cross_key):
                    if crossed_up:
                        title = "GEX ZERO — Bullish Cross 🟢"
                        desc  = (
                            f"**{ticker}** spot broke **above** the GEX zero level.\n"
                            f"Price entered **positive gamma territory** — dealers pin, volatility compresses.\n"
                            f"Net GEX: `{net_gex_m:+.2f}M`"
                        )
                        color = 0x3fb950  # green
                    else:
                        title = "GEX ZERO — Bearish Cross 🔴"
                        desc  = (
                            f"**{ticker}** spot broke **below** the GEX zero level.\n"
                            f"Price entered **negative gamma territory** — dealer hedging amplifies moves.\n"
                            f"Net GEX: `{net_gex_m:+.2f}M`"
                        )
                        color = 0xf85149  # red
                    _post_alert(ticker, title, desc, color, spot, gz)
                    self.throttle.mark(cross_key)
            except Exception:
                pass

        # ── 2. Max Pain Cross (±0.5%) ─────────────────────────
        if max_pain is not None:
            try:
                mp        = float(max_pain)
                upper     = mp * (1 + MAX_PAIN_TOL_PCT)
                lower     = mp * (1 - MAX_PAIN_TOL_PCT)
                mp_key_up = f"{ticker}:maxpain_upper:{mp:.0f}"
                mp_key_dn = f"{ticker}:maxpain_lower:{mp:.0f}"

                # Crossing above upper band
                if prev <= upper < spot and self.throttle.can_fire(mp_key_up):
                    desc = (
                        f"**{ticker}** spot crossed **above** Max Pain + 0.5% band.\n"
                        f"Max Pain: `${mp:.0f}` · Upper band: `${upper:.2f}`\n"
                        f"Structural gravity may pull price back toward `${mp:.0f}`."
                    )
                    _post_alert(ticker, "MAX PAIN — Upper Break 🔼", desc, 0x3fb950, spot, upper)
                    self.throttle.mark(mp_key_up)

                # Crossing below lower band
                elif prev >= lower > spot and self.throttle.can_fire(mp_key_dn):
                    desc = (
                        f"**{ticker}** spot crossed **below** Max Pain - 0.5% band.\n"
                        f"Max Pain: `${mp:.0f}` · Lower band: `${lower:.2f}`\n"
                        f"Structural gravity may pull price back toward `${mp:.0f}`."
                    )
                    _post_alert(ticker, "MAX PAIN — Lower Break 🔽", desc, 0xf85149, spot, lower)
                    self.throttle.mark(mp_key_dn)
            except Exception:
                pass

    def run_forever(self):
        """Main polling loop — runs until stop() is called."""
        print(f"[MONITOR] Level monitor armed for {len(self.tickers)} tickers.")
        print(f"[MONITOR] Poll: {POLL_INTERVAL_SECS}s  |  Throttle: {THROTTLE_SECS}s per level")

        while not self._stop_evt.is_set():
            now_h = datetime.datetime.now().hour
            # Only monitor during market hours (9:00-16:30 ET) on weekdays
            if datetime.datetime.now().weekday() < 5 and 9 <= now_h < 16:
                for ticker in self.tickers:
                    if self._stop_evt.is_set():
                        break
                    try:
                        self._check_ticker(ticker)
                    except Exception as e:
                        print(f"  [MONITOR] {ticker} check error: {e}")
                    time.sleep(0.5)  # small stagger between tickers
            else:
                print(f"[MONITOR] Market closed ({datetime.datetime.now().strftime('%H:%M')}) — sleeping 5 min.")
                self._stop_evt.wait(timeout=300)
                continue

            self._stop_evt.wait(timeout=POLL_INTERVAL_SECS)

        print("[MONITOR] Level monitor stopped.")

    def stop(self):
        self._stop_evt.set()

    def start_thread(self) -> threading.Thread:
        """Launch the monitor in a daemon background thread."""
        t = threading.Thread(target=self.run_forever, name="LevelMonitor", daemon=True)
        t.start()
        print(f"[MONITOR] Background thread started (tid={t.ident})")
        return t


# ── Singleton for watchdog import ───────────────────────────────
_monitor_instance: LevelMonitor | None = None
_monitor_thread:   threading.Thread | None = None


def start_level_monitor(tickers: list[str] | None = None) -> threading.Thread:
    """Start (or restart) the level monitor as a daemon thread."""
    global _monitor_instance, _monitor_thread
    if _monitor_instance is not None:
        _monitor_instance.stop()
    _monitor_instance = LevelMonitor(tickers=tickers)
    _monitor_thread   = _monitor_instance.start_thread()
    return _monitor_thread


# ── Standalone entry point ────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Trishula Level Monitor")
    parser.add_argument("--tickers", nargs="*", help="Tickers to monitor (default: all)")
    args   = parser.parse_args()
    tickers = args.tickers or _DEFAULT_TICKERS

    print(f"[MONITOR] Starting standalone — {len(tickers)} tickers")
    monitor = LevelMonitor(tickers=tickers)
    try:
        monitor.run_forever()
    except KeyboardInterrupt:
        monitor.stop()
        print("[MONITOR] Stopped by user.")
