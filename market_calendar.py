#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=================================================================
MARKET CALENDAR HELPER  —  Trishula Sovereign System
=================================================================
Provides authoritative NYSE trading-day checks using
pandas_market_calendars, with a robust hardcoded fallback.

Public API:
    is_market_open_today()          -> bool
    is_trading_day(d=None)          -> bool
    next_trading_day(d=None)        -> datetime.date
    trading_days_in_range(start, end) -> list[datetime.date]
=================================================================
"""

import datetime
import logging

logger = logging.getLogger("market_calendar")

# ---------------------------------------------------------------------------
# Hardcoded NYSE holiday fallback (2025-2027)
# Used when pandas_market_calendars is unavailable or fails.
# ---------------------------------------------------------------------------
_HARDCODED_HOLIDAYS = {
    # 2025
    datetime.date(2025, 1, 1),   # New Year's Day
    datetime.date(2025, 1, 20),  # MLK Jr Day
    datetime.date(2025, 2, 17),  # Presidents' Day
    datetime.date(2025, 4, 18),  # Good Friday
    datetime.date(2025, 5, 26),  # Memorial Day
    datetime.date(2025, 6, 19),  # Juneteenth
    datetime.date(2025, 7, 4),   # Independence Day
    datetime.date(2025, 9, 1),   # Labor Day
    datetime.date(2025, 11, 27), # Thanksgiving
    datetime.date(2025, 12, 25), # Christmas
    # 2026
    datetime.date(2026, 1, 1),   # New Year's Day
    datetime.date(2026, 1, 19),  # MLK Jr Day
    datetime.date(2026, 2, 16),  # Presidents' Day
    datetime.date(2026, 4, 3),   # Good Friday
    datetime.date(2026, 5, 25),  # Memorial Day
    datetime.date(2026, 6, 19),  # Juneteenth
    datetime.date(2026, 7, 3),   # Independence Day (observed)
    datetime.date(2026, 9, 7),   # Labor Day
    datetime.date(2026, 11, 26), # Thanksgiving
    datetime.date(2026, 12, 25), # Christmas
    # 2027
    datetime.date(2027, 1, 1),   # New Year's Day
    datetime.date(2027, 1, 18),  # MLK Jr Day
    datetime.date(2027, 2, 15),  # Presidents' Day
    datetime.date(2027, 3, 26),  # Good Friday
    datetime.date(2027, 5, 31),  # Memorial Day
    datetime.date(2027, 6, 18),  # Juneteenth (observed)
    datetime.date(2027, 7, 5),   # Independence Day (observed)
    datetime.date(2027, 9, 6),   # Labor Day
    datetime.date(2027, 11, 25), # Thanksgiving
    datetime.date(2027, 12, 24), # Christmas (observed)
}

# ---------------------------------------------------------------------------
# Internal: try to use pandas_market_calendars
# ---------------------------------------------------------------------------
_PMC_CALENDAR = None
_PMC_LOADED   = False

def _load_pmc():
    """Attempt to load the NYSE calendar from pandas_market_calendars once."""
    global _PMC_CALENDAR, _PMC_LOADED
    if _PMC_LOADED:
        return _PMC_CALENDAR
    _PMC_LOADED = True
    try:
        import pandas_market_calendars as mcal
        _PMC_CALENDAR = mcal.get_calendar("NYSE")
        logger.debug("[market_calendar] pandas_market_calendars loaded OK (NYSE)")
    except Exception as exc:
        logger.warning(f"[market_calendar] pandas_market_calendars unavailable: {exc}. Using hardcoded fallback.")
        _PMC_CALENDAR = None
    return _PMC_CALENDAR


def _is_trading_day_pmc(d: datetime.date) -> bool:
    """Check via pandas_market_calendars."""
    cal = _load_pmc()
    if cal is None:
        return None  # signal fallback
    try:
        import pandas as pd
        schedule = cal.schedule(
            start_date=d.strftime("%Y-%m-%d"),
            end_date=d.strftime("%Y-%m-%d"),
        )
        return not schedule.empty
    except Exception as exc:
        logger.warning(f"[market_calendar] PMC schedule check failed: {exc}")
        return None


def _is_trading_day_fallback(d: datetime.date) -> bool:
    """Fallback: Mon-Fri and not in hardcoded holiday set."""
    return d.weekday() < 5 and d not in _HARDCODED_HOLIDAYS


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_trading_day(d: datetime.date = None) -> bool:
    """
    Return True if `d` (default: today) is a NYSE trading day.
    Uses pandas_market_calendars when available, falls back to
    hardcoded holiday list automatically.
    """
    d = d or datetime.date.today()
    result = _is_trading_day_pmc(d)
    if result is None:
        result = _is_trading_day_fallback(d)
    return result


def is_market_open_today() -> bool:
    """
    Convenience alias: returns True if today is a NYSE trading day.
    This is the primary entry-point used by sovereign_watchdog.py.
    """
    return is_trading_day(datetime.date.today())


def next_trading_day(d: datetime.date = None) -> datetime.date:
    """Return the next NYSE trading day after `d` (default: today)."""
    d = d or datetime.date.today()
    candidate = d + datetime.timedelta(days=1)
    for _ in range(14):          # safety cap — never loop forever
        if is_trading_day(candidate):
            return candidate
        candidate += datetime.timedelta(days=1)
    return candidate             # best effort


def trading_days_in_range(
    start: datetime.date,
    end: datetime.date,
) -> list:
    """Return list of trading days [start, end] inclusive."""
    cal = _load_pmc()
    if cal is not None:
        try:
            import pandas as pd
            schedule = cal.schedule(
                start_date=start.strftime("%Y-%m-%d"),
                end_date=end.strftime("%Y-%m-%d"),
            )
            return [pd.Timestamp(ts).date() for ts in schedule.index]
        except Exception:
            pass
    # fallback
    days = []
    current = start
    while current <= end:
        if _is_trading_day_fallback(current):
            days.append(current)
        current += datetime.timedelta(days=1)
    return days


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    today = datetime.date.today()
    print(f"[market_calendar] Today           : {today} ({today.strftime('%A')})")
    print(f"[market_calendar] is_market_open  : {is_market_open_today()}")
    print(f"[market_calendar] is_trading_day  : {is_trading_day(today)}")
    print(f"[market_calendar] next_trading_day: {next_trading_day(today)}")

    # Show next 5 trading days
    print("\n  Next 5 trading days:")
    d = today
    for i in range(5):
        d = next_trading_day(d)
        print(f"    {i+1}. {d} ({d.strftime('%A')})")

    # Test specific holidays
    print("\n  Holiday checks:")
    test_dates = [
        datetime.date(2026, 1, 1),   # New Year (holiday)
        datetime.date(2026, 1, 2),   # Friday (trading)
        datetime.date(2026, 7, 4),   # Weekend
        datetime.date(2026, 7, 3),   # Independence Day observed (holiday)
    ]
    for td in test_dates:
        flag = is_trading_day(td)
        print(f"    {td} ({td.strftime('%A')}): {'TRADING' if flag else 'HOLIDAY/WEEKEND'}")
