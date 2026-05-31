#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=================================================================
NEWS & EARNINGS CALENDAR FEED  (_news_feed.py)
=================================================================
Free data sources — no paid API key required:
  • yfinance ticker.calendar        (earnings dates)
  • FRED API (free)                 (macro events: CPI, FOMC)
  • Stooq / Yahoo earnings calendar (earnings week check)

Functions:
    get_earnings_date(ticker)       -> datetime.date | None
    get_days_to_earnings(ticker)    -> int  (999 if unknown)
    is_earnings_week(ticker)        -> bool (within 7 days)
    get_upcoming_macro_events()     -> list[{date, event, impact}]
    get_earnings_flag(ticker)       -> str | None  (Discord warning)
=================================================================
"""

import os
import time
import datetime
import logging
import requests
from typing import Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)

# ── FRED API key (free, optional) ─────────────────────────────────────────────
def _load_fred_key() -> str:
    key = os.environ.get("FRED_API_KEY", "")
    if key:
        return key
    env_paths = [
        Path(r"H:\Trishula\Swarm_4_Integration\Swarm_4_SBM_FINAL INTEGRATION\Project-Swarm\trishula-market-data\.env"),
        Path(os.path.dirname(__file__)) / ".env",
    ]
    for env_path in env_paths:
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("FRED_API_KEY="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val:
                        return val
    return ""

FRED_API_KEY = _load_fred_key()
FRED_BASE    = "https://api.stlouisfed.org/fred"

# ── Cache ─────────────────────────────────────────────────────────────────────
_EARNINGS_CACHE: dict  = {}   # {ticker: (ts, date_or_none)}
_MACRO_CACHE:    dict  = {}   # {"macro": (ts, events_list)}
_CACHE_TTL = 3600             # 1-hour cache


# ─────────────────────────────────────────────────────────────────────────────
# get_earnings_date
# ─────────────────────────────────────────────────────────────────────────────
def get_earnings_date(ticker: str) -> Optional[datetime.date]:
    """
    Return next earnings date for ticker, or None if unknown.
    Sources tried (in order):
      1. yfinance ticker.calendar
      2. yfinance ticker.info['earningsDate']
      3. yfinance ticker.earnings_dates
    """
    ticker = ticker.upper()

    # Cache check
    if ticker in _EARNINGS_CACHE:
        ts, cached = _EARNINGS_CACHE[ticker]
        if time.time() - ts < _CACHE_TTL:
            return cached

    result = _fetch_earnings_date(ticker)
    _EARNINGS_CACHE[ticker] = (time.time(), result)
    return result


def _fetch_earnings_date(ticker: str) -> Optional[datetime.date]:
    """Internal fetch logic."""
    try:
        import yfinance as yf
        tk   = yf.Ticker(ticker)
        today = datetime.date.today()

        # Method 1: ticker.calendar
        try:
            cal = tk.calendar
            if cal is not None:
                # calendar can be dict or DataFrame
                if isinstance(cal, dict):
                    ed = cal.get("Earnings Date")
                    if ed:
                        if isinstance(ed, (list, tuple)) and len(ed) > 0:
                            ed = ed[0]
                        if hasattr(ed, "date"):
                            d = ed.date()
                        else:
                            d = datetime.datetime.strptime(str(ed)[:10], "%Y-%m-%d").date()
                        if d >= today:
                            return d
                elif hasattr(cal, "columns"):
                    import pandas as pd
                    if "Earnings Date" in cal.columns:
                        for val in cal["Earnings Date"]:
                            if hasattr(val, "date"):
                                d = val.date()
                            else:
                                try:
                                    d = datetime.datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
                                except Exception:
                                    continue
                            if d >= today:
                                return d
        except Exception as e:
            logger.debug(f"[earnings] calendar method failed for {ticker}: {e}")

        # Method 2: ticker.info earningsDate
        try:
            info = tk.info or {}
            raw_ed = info.get("earningsDate") or info.get("earningsTimestamp")
            if raw_ed:
                if isinstance(raw_ed, (int, float)):
                    d = datetime.datetime.fromtimestamp(raw_ed).date()
                elif isinstance(raw_ed, list) and raw_ed:
                    raw_ed = raw_ed[0]
                    d = datetime.datetime.fromtimestamp(raw_ed).date() if isinstance(raw_ed, (int, float)) else None
                else:
                    d = None
                if d and d >= today:
                    return d
        except Exception as e:
            logger.debug(f"[earnings] info method failed for {ticker}: {e}")

        # Method 3: earnings_dates DataFrame
        try:
            ed_df = tk.earnings_dates
            if ed_df is not None and not ed_df.empty:
                import pandas as pd
                future = ed_df[ed_df.index >= pd.Timestamp(today)]
                if not future.empty:
                    d = future.index[0].date()
                    return d
        except Exception as e:
            logger.debug(f"[earnings] earnings_dates method failed for {ticker}: {e}")

        return None

    except Exception as e:
        logger.debug(f"[earnings] General error for {ticker}: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# get_days_to_earnings
# ─────────────────────────────────────────────────────────────────────────────
def get_days_to_earnings(ticker: str) -> int:
    """
    Return number of calendar days until next earnings.
    Returns 999 if earnings date is unknown.
    """
    d = get_earnings_date(ticker)
    if d is None:
        return 999
    today = datetime.date.today()
    delta = (d - today).days
    return max(delta, 0)


# ─────────────────────────────────────────────────────────────────────────────
# is_earnings_week
# ─────────────────────────────────────────────────────────────────────────────
def is_earnings_week(ticker: str, window_days: int = 7) -> bool:
    """Return True if earnings are within window_days calendar days."""
    return get_days_to_earnings(ticker) <= window_days


# ─────────────────────────────────────────────────────────────────────────────
# get_earnings_flag — Discord warning string
# ─────────────────────────────────────────────────────────────────────────────
def get_earnings_flag(ticker: str) -> Optional[str]:
    """
    Return a Discord-ready warning string if earnings are imminent.
    Returns None if no earnings within 14 days.

    Examples:
      '⚠️ EARNINGS IN 2 DAYS (Jun 5)'
      '🔔 EARNINGS TODAY'
      '📅 EARNINGS IN 7 DAYS (Jun 10)'
    """
    d = get_earnings_date(ticker)
    if d is None:
        return None
    days = get_days_to_earnings(ticker)
    # Cross-platform date string (Windows doesn't support %-d)
    try:
        date_str = d.strftime("%b %d").replace(" 0", " ").strip()
    except Exception:
        date_str = str(d)

    if days == 0:
        return f"🔔 **EARNINGS TODAY** ({date_str})"
    elif days == 1:
        return f"⚠️ **EARNINGS TOMORROW** ({date_str})"
    elif days <= 3:
        return f"⚠️ **EARNINGS IN {days} DAYS** ({date_str})"
    elif days <= 7:
        return f"📅 EARNINGS IN {days} DAYS ({date_str})"
    elif days <= 14:
        return f"📅 Earnings in {days} days ({date_str})"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# get_upcoming_macro_events — FRED + static fallback
# ─────────────────────────────────────────────────────────────────────────────

# Known upcoming FOMC dates 2025-2026 (static, updated quarterly)
_FOMC_DATES_2025_2026 = [
    datetime.date(2025, 6, 18),
    datetime.date(2025, 7, 30),
    datetime.date(2025, 9, 17),
    datetime.date(2025, 11, 5),
    datetime.date(2025, 12, 10),
    datetime.date(2026, 1, 28),
    datetime.date(2026, 3, 18),
    datetime.date(2026, 4, 29),
    datetime.date(2026, 6, 17),
    datetime.date(2026, 7, 29),
    datetime.date(2026, 9, 16),
    datetime.date(2026, 11, 4),
    datetime.date(2026, 12, 16),
]


def _fred_get(endpoint: str, params: dict = None, timeout: int = 10) -> Optional[dict]:
    """Hit FRED API (requires free API key)."""
    if not FRED_API_KEY:
        return None
    p = params.copy() if params else {}
    p["api_key"] = FRED_API_KEY
    p["file_type"] = "json"
    try:
        resp = requests.get(f"{FRED_BASE}{endpoint}", params=p, timeout=timeout,
                            headers={"User-Agent": "TrishulaQMatrix/3.0"})
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception:
        return None


def _get_fred_cpi_dates() -> List[dict]:
    """Fetch upcoming CPI release dates from FRED series CPIAUCSL."""
    events = []
    try:
        data = _fred_get("/series/release_dates",
                         params={"series_id": "CPIAUCSL", "include_release_dates_with_no_data": "false"})
        if not data:
            return events
        today = datetime.date.today()
        cutoff = today + datetime.timedelta(days=45)
        for item in data.get("release_dates", []):
            try:
                d = datetime.date.fromisoformat(item["date"])
                if today <= d <= cutoff:
                    events.append({
                        "date":   d,
                        "event":  "CPI Release (FRED)",
                        "impact": "HIGH",
                        "source": "fred",
                    })
            except Exception:
                continue
    except Exception as e:
        logger.debug(f"[FRED] CPI dates error: {e}")
    return events


def _get_static_macro_events() -> List[dict]:
    """Return upcoming FOMC dates from static schedule."""
    today  = datetime.date.today()
    cutoff = today + datetime.timedelta(days=60)
    events = []
    for d in _FOMC_DATES_2025_2026:
        if today <= d <= cutoff:
            events.append({
                "date":   d,
                "event":  "FOMC Decision (Fed Rate)",
                "impact": "HIGH",
                "source": "static",
            })
    return events


def get_upcoming_macro_events(days_ahead: int = 30) -> List[dict]:
    """
    Return list of upcoming macro events within days_ahead calendar days.

    Each event: {date, event, impact, source}
    impact: 'HIGH', 'MEDIUM', 'LOW'

    Sources:
      - FOMC dates (static schedule, always available)
      - FRED CPI release dates (requires FRED_API_KEY)
    """
    # Cache
    if "macro" in _MACRO_CACHE:
        ts, cached = _MACRO_CACHE["macro"]
        if time.time() - ts < _CACHE_TTL:
            return cached

    today  = datetime.date.today()
    cutoff = today + datetime.timedelta(days=days_ahead)
    events = []

    # FOMC (always available)
    events.extend(_get_static_macro_events())

    # FRED CPI (if key available)
    events.extend(_get_fred_cpi_dates())

    # Filter to window and sort
    events = [e for e in events if today <= e["date"] <= cutoff]
    events.sort(key=lambda e: e["date"])

    # Deduplicate by date+event
    seen = set()
    deduped = []
    for e in events:
        key = (e["date"], e["event"][:20])
        if key not in seen:
            seen.add(key)
            deduped.append(e)

    _MACRO_CACHE["macro"] = (time.time(), deduped)
    return deduped


def format_macro_events_field(days_ahead: int = 14) -> Optional[dict]:
    """
    Returns a Discord embed field for upcoming macro events.
    Returns None if no events.
    """
    events = get_upcoming_macro_events(days_ahead=days_ahead)
    if not events:
        return None

    lines = []
    for e in events[:4]:
        d_str = e["date"].strftime("%b %d")
        impact_emoji = "🚨" if e["impact"] == "HIGH" else "⚠️" if e["impact"] == "MEDIUM" else "📌"
        lines.append(f"{impact_emoji} `{d_str}` — {e['event']}")

    return {
        "name":   "📅 Upcoming Macro Events",
        "value":  "\n".join(lines),
        "inline": False,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Self-test
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    tickers = ["TSLA", "AMZN", "SPY", "NVDA", "AAPL"]
    print("\n── Earnings Dates ──")
    for sym in tickers:
        d    = get_earnings_date(sym)
        days = get_days_to_earnings(sym)
        flag = get_earnings_flag(sym)
        print(f"  {sym:<6} next_earnings={d}  days_away={days}  flag={flag}")

    print("\n── Upcoming Macro Events ──")
    events = get_upcoming_macro_events(days_ahead=60)
    if events:
        for e in events:
            print(f"  {e['date']}  [{e['impact']}]  {e['event']}  (source={e['source']})")
    else:
        print("  No macro events found (FOMC static schedule may be exhausted)")

    print("\n[DONE]")
