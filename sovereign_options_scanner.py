# -*- coding: utf-8 -*-
"""
Q-MATRIX OPTIONS SCANNER  v3.1  —  PRODUCTION MAINSTAY
======================================================
Runs every US stock trading session (Mon–Fri, non-holiday).
Fires to the Q-MATRIX Discord webhook:
  • WEEKLY sweep    — nearest Friday expiry, all tickers
  • DAILY sweep     — nearest 0-2 DTE expiry, core tickers
  • PREMARKET sweep — 8:30 ET gap/drift/VIX/earnings scan

New in v3.1 (R2-5 + R2-6):
  • Multi-Expiry GEX Stacking (stack_gex_expiries)
  • Pre-Market Scanner with overnight gap, futures drift, VIX, news catalysts

Usage:
    python sovereign_options_scanner.py                     # both modes
    python sovereign_options_scanner.py --mode weekly
    python sovereign_options_scanner.py --mode daily
    python sovereign_options_scanner.py --mode premarket
    python sovereign_options_scanner.py --mode premarket --dry-run
    python sovereign_options_scanner.py --force             # skip market-day guard

Dependencies:
    pip install yfinance matplotlib requests pandas numpy

Scheduled via Windows Task Scheduler — see setup_scheduler.ps1
"""

import io
import json
import math
import sys
import time
import datetime
import requests
import numpy as np
import pandas as pd
import matplotlib
# Force UTF-8 stdout on Windows to avoid cp1252 encode errors
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec

try:
    import yfinance as yf
except ImportError:
    raise SystemExit("[ERROR] yfinance not installed. Run: pip install yfinance")

# ── Polygon.io real-time feed (P2-A) ─────────────────────────────────────────
try:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(__file__))
    from _polygon_feed import (
        get_spot_price as _polygon_spot,
        polygon_status as _poly_status,
        get_all_ohlcv_batch as _polygon_batch_ohlcv,
    )
    _POLYGON_AVAILABLE = True
except Exception as _poly_err:
    print(f"[Polygon] Feed unavailable: {_poly_err}")
    _POLYGON_AVAILABLE = False
    def _polygon_spot(ticker): return None
    def _polygon_batch_ohlcv(tickers, date_str=None): return {}

# Module-level cache for batch OHLCV (populated at top of run_sweep)
_OHLCV_BATCH_CACHE: dict = {}  # {TICKER: {Open,High,Low,Close,Volume}}

# ── StockTwits sentiment (P3-A) ───────────────────────────────────────────────
try:
    from _stocktwits_sentiment import get_sentiment as _st_sentiment, format_sentiment_field as _st_field
    _STOCKTWITS_AVAILABLE = True
except Exception as _st_err:
    print(f"[StockTwits] Module unavailable: {_st_err}")
    _STOCKTWITS_AVAILABLE = False
    def _st_sentiment(ticker): return {"score": 0.0, "bullish_pct": 0.0, "source": "unavailable"}
    def _st_field(ticker): return None

# ── News & Earnings feed (P3-B) ───────────────────────────────────────────────
try:
    from _news_feed import (
        get_earnings_date as _get_earnings_date,
        get_days_to_earnings as _days_to_earnings,
        is_earnings_week as _is_earnings_week,
        get_earnings_flag as _earnings_flag,
        get_upcoming_macro_events as _macro_events,
        format_macro_events_field as _macro_events_field,
    )
    _NEWS_FEED_AVAILABLE = True
except Exception as _news_err:
    print(f"[NewsFeed] Module unavailable: {_news_err}")
    _NEWS_FEED_AVAILABLE = False
    def _get_earnings_date(t): return None
    def _days_to_earnings(t): return 999
    def _is_earnings_week(t): return False
    def _earnings_flag(t): return None
    def _macro_events(**kwargs): return []
    def _macro_events_field(**kwargs): return None

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# DISCORD CHANNEL WEBHOOKS
# ─────────────────────────────────────────────────────────────────────────────
WEBHOOK_MACRO      = "https://discord.com/api/webhooks/1508273976558882906/Scvp9yK6mmfrEJ7hMu38fJn24Fa7TljEeSs4tL0xHwfOIs_0P26mhrbaFuzwoxEgy5F5"
WEBHOOK_ETFS       = "https://discord.com/api/webhooks/1508274096230629478/-RAAG6M1QXbZZUkFfj3tXaTFcLNHGi1YeS9vCkSTZg4ypnmJHhBAujkNhvRvAhW0e-0o"
WEBHOOK_MEGACAP    = "https://discord.com/api/webhooks/1508274221644517446/_MDRuliSQdtgqsCCNRJcSq7PSbVP-t1eSWxZQGs27XomPNb53tMCXDVFL80OIBnDH0hz"
WEBHOOK_MAG7       = "https://discord.com/api/webhooks/1508276190295752714/EiHG_VmUz9fTf-G_JBw1O17A33LdNsx7ut_F69ZfmYCnpLf8P4v2HkGG8TmX6TreSyct"
WEBHOOK_COMMODITIES= "https://discord.com/api/webhooks/1508274339009659042/jufgQIU7u5vaT804mlkyg-m4hM0Wf-ZhJugGuKgo3LwSSeHiQsrE1WmVUfGK8EiDw9O1"
WEBHOOK_CRYPTO     = "https://discord.com/api/webhooks/1508274523948974190/fZ2p9DFKIrs3WZZvgujjjhooIeUaX5sEtYjpJKd6gWXNnV5E0XJhIQUAVPpS0GWzHTXb"
WEBHOOK_FOREX      = "https://discord.com/api/webhooks/1508274623303909507/3Jh2EKwZ_ihnmVRB4yCgtpgobzQBD0B8Zcg_iKmh4EPntQNe9tnAm03oqPQFNQHl3fQz"
WEBHOOK_FUTURES    = "https://discord.com/api/webhooks/1508274707172950087/q6X5eZyT5dxgQX5rd61dm9YPgHJEl6oVbimuICM-OkfBWWoXaH0mHdoADWyBCWvZlajA"
WEBHOOK_MIDCAP     = "https://discord.com/api/webhooks/1508274773350944818/uk9UE_rI_HJPE2eLHrgsb_DCobVAsl0oz3YJX_HOz11iTkpZfMyQUI3-_V3a_WyzOqyX"
WEBHOOK_LOWCAP     = "https://discord.com/api/webhooks/1508274874697781429/3Nl6GKPMazt1RUFOO3WLXXSrc2gPf6KaIddOWkQc6bHYv0ryJrEqeh1ZraO35mFVkyIx"
WEBHOOK_EARNINGS   = "https://discord.com/api/webhooks/1508522150657654935/bh9OgEkGq-rgDbZ80e89Fkq4ATFWbPB5dwqODF2U0P-91IyYY-YKf6djYqL-7giEIG4F"

# Ticker → channel routing
_TICKER_WEBHOOK_MAP = {
    # ── ETFs ───────────────────────────────────────────────────────────────────────────
    "SPY":  WEBHOOK_ETFS,
    "QQQ":  WEBHOOK_ETFS,
    "IWM":  WEBHOOK_ETFS,
    "SOXL": WEBHOOK_ETFS,
    "SMH":  WEBHOOK_ETFS,
    "IBIT": WEBHOOK_ETFS,
    "GDX":  WEBHOOK_ETFS,
    # ── Magnificent 7 ────────────────────────────────────────────────────────────
    "TSLA":  WEBHOOK_MAG7,
    "MSFT":  WEBHOOK_MAG7,
    "META":  WEBHOOK_MAG7,
    "AMZN":  WEBHOOK_MAG7,
    "AAPL":  WEBHOOK_MAG7,
    "GOOGL": WEBHOOK_MAG7,
    "NVDA":  WEBHOOK_MAG7,
    # ── Mega-Cap ─────────────────────────────────────────────────────────────────
    "AVGO": WEBHOOK_MEGACAP,
    "CRWD": WEBHOOK_MEGACAP,
    "CRWV": WEBHOOK_MEGACAP,
    "NFLX": WEBHOOK_MEGACAP,
    "TSM":  WEBHOOK_MEGACAP,
    "ADBE": WEBHOOK_MEGACAP,
    "ARM":  WEBHOOK_MEGACAP,
    "NOW":  WEBHOOK_MEGACAP,
    "IBM":  WEBHOOK_MEGACAP,
    # ── Mid-Cap ──────────────────────────────────────────────────────────────────
    "PLTR": WEBHOOK_MIDCAP,
    "AMD":  WEBHOOK_MIDCAP,
    "INTC": WEBHOOK_MIDCAP,
    "ORCL": WEBHOOK_MIDCAP,
    "COIN": WEBHOOK_MIDCAP,
    "MU":   WEBHOOK_MIDCAP,
    "APP":  WEBHOOK_MIDCAP,
    "MSTR": WEBHOOK_MIDCAP,
    "NET":  WEBHOOK_MIDCAP,
    "RDDT": WEBHOOK_MIDCAP,
    "DDOG": WEBHOOK_MIDCAP,
    "ASTS": WEBHOOK_MIDCAP,
    "IREN": WEBHOOK_MIDCAP,
    # ── Commodities ───────────────────────────────────────────────────────────────
    "GLD": WEBHOOK_COMMODITIES,
    "SLV": WEBHOOK_COMMODITIES,
    # ── Low-Cap ──────────────────────────────────────────────────────────────────
    "SOFI": WEBHOOK_LOWCAP,
    "RKLB": WEBHOOK_LOWCAP,
    "HOOD": WEBHOOK_LOWCAP,
    "SNAP": WEBHOOK_LOWCAP,
    "MARA": WEBHOOK_LOWCAP,
    # ── Earnings watch (week of May 27) — routes to #qm-earnings ────────────
    "CRM":  WEBHOOK_EARNINGS,  # Salesforce — reports May 27
    "SNOW": WEBHOOK_EARNINGS,  # Snowflake  — reports May 27
    "OKTA": WEBHOOK_EARNINGS,  # Okta       — reports May 28
    "MDB":  WEBHOOK_EARNINGS,  # MongoDB    — reports May 28
}


# Fallback for any ticker not explicitly mapped
WEBHOOK_FALLBACK = WEBHOOK_MEGACAP

def get_webhook(symbol: str = None, channel: str = None) -> str:
    """Return the correct Discord webhook for a ticker or named channel."""
    if channel == "macro":       return WEBHOOK_MACRO
    if channel == "etfs":        return WEBHOOK_ETFS
    if channel == "mag7":        return WEBHOOK_MAG7
    if channel == "mega":        return WEBHOOK_MEGACAP
    if channel == "mid":         return WEBHOOK_MIDCAP
    if channel == "commodities": return WEBHOOK_COMMODITIES
    if channel == "crypto":      return WEBHOOK_CRYPTO
    if channel == "forex":       return WEBHOOK_FOREX
    if channel == "futures":     return WEBHOOK_FUTURES
    if channel == "lowcap":      return WEBHOOK_LOWCAP
    if symbol:
        return _TICKER_WEBHOOK_MAP.get(symbol.upper(), WEBHOOK_FALLBACK)
    return WEBHOOK_FALLBACK

# Legacy alias — used by any code that still references DISCORD_WEBHOOK directly
DISCORD_WEBHOOK = WEBHOOK_FALLBACK

TICKERS = [
    "SPY",  "QQQ",  "IWM",  "SOXL",
    "TSLA", "MSFT", "META", "PLTR",
    "AMZN", "AMD",  "NVDA", "INTC",
    "AAPL", "GOOGL","COIN", "ORCL",
    "GLD",  "SLV",  "ASTS", "NOW",
    "IBM",  "IREN", "MARA", "CRWV",
    "CRM",
]

RFR            = 0.053    # Risk-free rate
STRIKE_RANGE   = 0.10     # ±10% around spot
DELAY_SECS     = 4        # Pause between tickers (webhook rate-limit safety)

# Tickers eligible for 0DTE / daily sweep (must have same-day or next-day options)
DAILY_TICKERS = ["SPY", "QQQ", "IWM", "TSLA", "NVDA", "AMD", "AAPL", "SOXL"]

# US market holidays 2025-2026 (NYSE)
US_HOLIDAYS = {
    datetime.date(2025, 1, 1), datetime.date(2025, 1, 20),
    datetime.date(2025, 2, 17), datetime.date(2025, 4, 18),
    datetime.date(2025, 5, 26), datetime.date(2025, 6, 19),
    datetime.date(2025, 7, 4),  datetime.date(2025, 9, 1),
    datetime.date(2025, 11, 27),datetime.date(2025, 12, 25),
    datetime.date(2026, 1, 1),  datetime.date(2026, 1, 19),
    datetime.date(2026, 2, 16), datetime.date(2026, 4, 3),
    datetime.date(2026, 5, 25), datetime.date(2026, 6, 19),
    datetime.date(2026, 7, 3),  datetime.date(2026, 9, 7),
    datetime.date(2026, 11, 26),datetime.date(2026, 12, 25),
}

def is_trading_day(d: datetime.date = None) -> bool:
    """Return True if d is a US stock market trading day."""
    d = d or datetime.date.today()
    return d.weekday() < 5 and d not in US_HOLIDAYS

# ─────────────────────────────────────────────────────────────────────────────
# BLACK-SCHOLES GREEKS (inline — no external dependency)
# ─────────────────────────────────────────────────────────────────────────────
def _ncdf(x):
    a1,a2,a3,a4,a5,p = 0.254829592,-0.284496736,1.421413741,-1.453152027,1.061405429,0.3275911
    s = 1 if x >= 0 else -1
    x = abs(x) / math.sqrt(2)
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5*t+a4)*t)+a3)*t+a2)*t+a1)*t*math.exp(-x*x)
    return 0.5*(1.0 + s*y)

def _npdf(x):
    return math.exp(-0.5*x*x) / math.sqrt(2.0*math.pi)

def bs_gamma(S, K, T, r, sigma):
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.0
    try:
        d1 = (math.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*math.sqrt(T))
        return _npdf(d1) / (S * sigma * math.sqrt(T))
    except Exception:
        return 0.0

def bs_delta_call(S, K, T, r, sigma):
    """Black-Scholes call delta. Falls back to a moneyness approximation if BS fails."""
    if T > 0 and sigma > 0 and S > 0 and K > 0:
        try:
            d1 = (math.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*math.sqrt(T))
            return _ncdf(d1)
        except Exception:
            pass
    # Fallback: linear moneyness approximation clamped to [0.05, 0.95]
    return max(0.05, min(0.95, (S - K) / (S * 0.20) + 0.5))

def bs_delta_put(S, K, T, r, sigma):
    """Black-Scholes put delta (negative). Returns absolute value."""
    return abs(bs_delta_call(S, K, T, r, sigma) - 1.0)

# ─────────────────────────────────────────────────────────────────────────────
# MAX PAIN
# ─────────────────────────────────────────────────────────────────────────────
def compute_max_pain(strikes, call_oi, put_oi):
    best_strike = strikes[0]
    best_pain   = float("inf")
    for pin in strikes:
        pain = sum(max(0, pin - K) * call_oi.get(K, 0) * 100 for K in strikes)
        pain += sum(max(0, K - pin) * put_oi.get(K, 0) * 100  for K in strikes)
        if pain < best_pain:
            best_pain   = pain
            best_strike = pin
    return best_strike

# ─────────────────────────────────────────────────────────────────────────────
# NEAREST WEEKLY EXPIRY
# ─────────────────────────────────────────────────────────────────────────────
def nearest_weekly(tk_obj):
    """Return the nearest Friday expiry string from the chain."""
    today = datetime.date.today()
    for exp_str in tk_obj.options:
        try:
            exp_dt = datetime.date.fromisoformat(exp_str)
            if exp_dt >= today:
                return exp_str
        except ValueError:
            continue
    return tk_obj.options[0] if tk_obj.options else None

# ─────────────────────────────────────────────────────────────────────────────
# FETCH & PROCESS ONE TICKER
# ─────────────────────────────────────────────────────────────────────────────
def process_ticker(symbol: str):
    print(f"  [{symbol}] Fetching data...")
    tk = yf.Ticker(symbol)

    # Spot price
    try:
        spot = float(tk.fast_info.last_price)
    except Exception:
        hist = tk.history(period="1d")
        spot = float(hist["Close"].iloc[-1]) if not hist.empty else None
    if not spot:
        print(f"  [{symbol}] Could not fetch spot — skipping.")
        return None

    # Nearest expiry
    weekly_exp = nearest_weekly(tk)
    if not weekly_exp:
        print(f"  [{symbol}] No options chain — skipping.")
        return None

    # Days to expiry
    exp_dt = datetime.datetime.strptime(weekly_exp, "%Y-%m-%d")
    T = max((exp_dt - datetime.datetime.now()).total_seconds() / (365.25 * 24 * 3600), 1/365)

    # Pull chain
    try:
        chain = tk.option_chain(weekly_exp)
        calls = chain.calls.fillna(0)
        puts  = chain.puts.fillna(0)
    except Exception as e:
        print(f"  [{symbol}] Chain error: {e} — skipping.")
        return None

    # Filter to ±STRIKE_RANGE of spot
    lo = spot * (1 - STRIKE_RANGE)
    hi = spot * (1 + STRIKE_RANGE)
    calls = calls[(calls["strike"] >= lo) & (calls["strike"] <= hi)].copy()
    puts  = puts[ (puts["strike"]  >= lo) & (puts["strike"]  <= hi)].copy()

    # Intelligent Fallback: If Open Interest is zero (after-hours/unpropagated), use Volume as a proxy
    if calls["openInterest"].sum() == 0 and puts["openInterest"].sum() == 0:
        calls["openInterest"] = calls["volume"]
        puts["openInterest"] = puts["volume"]

    # Build dicts keyed by strike
    all_strikes = sorted(set(calls["strike"].tolist()) | set(puts["strike"].tolist()))

    call_oi  = dict(zip(calls["strike"], calls["openInterest"]))
    put_oi   = dict(zip(puts["strike"],  puts["openInterest"]))
    call_vol = dict(zip(calls["strike"], calls["volume"]))
    put_vol  = dict(zip(puts["strike"],  puts["volume"]))
    call_iv  = dict(zip(calls["strike"], calls["impliedVolatility"]))
    put_iv   = dict(zip(puts["strike"],  puts["impliedVolatility"]))

    # Totals
    tot_call_oi = sum(call_oi.values())
    tot_put_oi  = sum(put_oi.values())
    pc_ratio    = round(tot_put_oi / tot_call_oi, 2) if tot_call_oi > 0 else 0.0

    # Max Pain
    max_pain = compute_max_pain(all_strikes, call_oi, put_oi)

    # Net GEX ($M)
    net_gex = 0.0
    for K in all_strikes:
        iv_c = call_iv.get(K, 0.30) or 0.30
        iv_p = put_iv.get(K,  0.30) or 0.30
        g_c  = bs_gamma(spot, K, T, RFR, iv_c)
        g_p  = bs_gamma(spot, K, T, RFR, iv_p)
        net_gex += (call_oi.get(K, 0) * g_c - put_oi.get(K, 0) * g_p) * 100 * spot
    net_gex_m = round(net_gex / 1_000_000, 2)

    # Top call / put walls (by OI)
    top_call_wall = max(call_oi, key=call_oi.get) if call_oi else spot
    top_put_wall  = max(put_oi,  key=put_oi.get)  if put_oi  else spot

    # ── Delta-Adjusted OI (DBOI) ─────────────────────────────────────────────
    dboi_call_per_k = {}
    dboi_put_per_k  = {}
    net_dboi_per_k  = {}
    net_dboi_total  = 0.0
    for K in all_strikes:
        iv_c = call_iv.get(K, 0.30) or 0.30
        iv_p = put_iv.get(K,  0.30) or 0.30
        d_c  = bs_delta_call(spot, K, T, RFR, iv_c)
        d_p  = bs_delta_put(spot,  K, T, RFR, iv_p)
        dc   = call_oi.get(K, 0) * d_c * 100
        dp   = put_oi.get(K,  0) * d_p * 100
        dboi_call_per_k[K] = dc
        dboi_put_per_k[K]  = dp
        net_dboi_per_k[K]  = dc - dp
        net_dboi_total    += dc - dp

    dboi_call_wall = max(dboi_call_per_k, key=dboi_call_per_k.get) if dboi_call_per_k else spot
    dboi_put_wall  = max(dboi_put_per_k,  key=dboi_put_per_k.get)  if dboi_put_per_k  else spot

    # DBOI zero-line: strike where net_dboi crosses zero
    dboi_zero_line = None
    _sorted_k = sorted(all_strikes)
    for _i in range(len(_sorted_k) - 1):
        _ka, _kb = _sorted_k[_i], _sorted_k[_i+1]
        _va, _vb = net_dboi_per_k[_ka], net_dboi_per_k[_kb]
        if _va * _vb < 0:  # sign change
            dboi_zero_line = round(
                _ka + (_kb - _ka) * abs(_va) / (abs(_va) + abs(_vb)), 2
            )
            break
    net_dboi_m = round(net_dboi_total / 1_000_000, 4)

    # Flow anomalies (Vol/OI > 2.0 with vol > 300)
    anomalies = []
    for K in all_strikes:
        for side, oi_d, vol_d in [("CALL", call_oi, call_vol), ("PUT", put_oi, put_vol)]:
            oi_val  = oi_d.get(K, 0)
            vol_val = vol_d.get(K, 0)
            if oi_val > 0 and vol_val > 300 and vol_val / oi_val > 2.0:
                anomalies.append((side, K, round(vol_val / oi_val, 1), int(vol_val)))
    anomalies.sort(key=lambda x: x[2], reverse=True)

    # ── vol_spike: 1 if total options vol > 2× the 20-day avg stock volume ──
    try:
        hist20 = tk.history(period="25d")
        avg_vol_20d = float(hist20["Volume"].tail(20).mean()) if len(hist20) >= 5 else 0.0
        tot_options_vol = sum(call_vol.values()) + sum(put_vol.values())
        vol_spike = 1 if (avg_vol_20d > 0 and tot_options_vol > 2 * avg_vol_20d) else 0
    except Exception:
        vol_spike = 0

    # ── whale_flow_flag: 1 if any strike has Vol/OI > 5× with vol > 1000 ──
    whale_flow_flag = 0
    for K in all_strikes:
        for oi_d, vol_d in [(call_oi, call_vol), (put_oi, put_vol)]:
            oi_v  = oi_d.get(K, 0)
            vol_v = vol_d.get(K, 0)
            if oi_v > 0 and vol_v > 1000 and vol_v / oi_v > 5.0:
                whale_flow_flag = 1
                break
        if whale_flow_flag:
            break

    return {
        "symbol":          symbol,
        "spot":            spot,
        "expiry":          weekly_exp,
        "T":               T,
        "strikes":         all_strikes,
        "call_oi":         call_oi,
        "put_oi":          put_oi,
        "call_vol":        call_vol,
        "put_vol":         put_vol,
        "max_pain":        max_pain,
        "net_gex_m":       net_gex_m,
        "pc_ratio":        pc_ratio,
        "top_call_wall":   top_call_wall,
        "top_put_wall":    top_put_wall,
        "tot_call_oi":     int(tot_call_oi),
        "tot_put_oi":      int(tot_put_oi),
        "anomalies":       anomalies[:5],
        "vol_spike":       vol_spike,
        "whale_flow_flag": whale_flow_flag,
        # ── R2-8: DBOI fields ────────────────────────────────────────────────
        "dboi_call_wall":  dboi_call_wall,
        "dboi_put_wall":   dboi_put_wall,
        "dboi_zero_line":  dboi_zero_line,
        "net_dboi_m":      net_dboi_m,
    }

# ─────────────────────────────────────────────────────────────────────────────
# CHART GENERATION
# ─────────────────────────────────────────────────────────────────────────────
DARK_BG   = "#0a0a12"
PANEL_BG  = "#0f0f1a"
GREEN     = "#00cc88"
GREEN_D   = "#006644"
RED       = "#ff3344"
RED_D     = "#880022"
GOLD      = "#ffbd15"
CYAN      = "#00e5ff"
WHITE     = "#e2e8f0"
DIM       = "#64748b"
BORDER    = "#1e1e30"

# ─────────────────────────────────────────────────────────────────────────────
# CHART HEADER FRAME  (PIL wrapper — stamps every panel before Discord upload)
# ─────────────────────────────────────────────────────────────────────────────
def _add_chart_header(buf: io.BytesIO, symbol: str, chart_type: str,
                      description: str, accent: str = "#00e5ff") -> io.BytesIO:
    """
    Wraps an existing chart PNG with a branded header strip and colored border.
    Returns a new BytesIO containing the framed image.
    Falls back to original buffer if Pillow is not available.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        buf.seek(0)
        orig = Image.open(buf).convert("RGB")
        ow, oh = orig.size

        BORDER_W  = 3
        HEADER_H  = 78
        BAR_H     = 5
        PAD       = 14
        new_w     = ow + BORDER_W * 2
        new_h     = oh + HEADER_H + BORDER_W * 2

        # Parse accent hex to RGB
        acc = tuple(int(accent.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
        bg  = (10, 10, 18)   # DARK_BG

        canvas = Image.new("RGB", (new_w, new_h), bg)
        draw   = ImageDraw.Draw(canvas)

        # Border
        draw.rectangle([0, 0, new_w - 1, new_h - 1], outline=acc, width=BORDER_W)

        # Accent top bar
        draw.rectangle([BORDER_W, BORDER_W, new_w - BORDER_W, BORDER_W + BAR_H], fill=acc)

        # Fonts — try system fonts, fall back gracefully
        try:
            from PIL import ImageFont
            f_title = ImageFont.truetype("arialbd.ttf",  20)
            f_sub   = ImageFont.truetype("arial.ttf",   11)
            f_badge = ImageFont.truetype("arialbd.ttf",  11)
        except Exception:
            try:
                f_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 20)
                f_sub   = ImageFont.truetype("DejaVuSans.ttf",      11)
                f_badge = f_title
            except Exception:
                f_title = ImageFont.load_default()
                f_sub   = f_title
                f_badge = f_title

        ty = BORDER_W + BAR_H + 8

        # Ticker badge in accent color
        badge_text = f" {symbol} "
        draw.text((BORDER_W + PAD, ty), badge_text,
                  fill=bg, font=f_badge,
                  stroke_width=0)
        # Filled badge background
        try:
            bw = draw.textlength(badge_text, font=f_badge)
        except Exception:
            bw = len(badge_text) * 8
        draw.rectangle([BORDER_W + PAD - 2, ty - 1,
                         BORDER_W + PAD + bw + 2, ty + 20], fill=acc)
        draw.text((BORDER_W + PAD, ty), badge_text, fill=bg, font=f_badge)

        # Chart type title
        title_x = BORDER_W + PAD + bw + 10
        draw.text((title_x, ty), f"Q-MATRIX  —  {chart_type}",
                  fill=(226, 232, 240), font=f_title)

        # Description subtitle
        draw.text((BORDER_W + PAD, ty + 30), description,
                  fill=(100, 116, 139), font=f_sub)

        # Thin separator line above chart
        sep_y = BORDER_W + HEADER_H - 2
        draw.line([BORDER_W, sep_y, new_w - BORDER_W, sep_y], fill=acc, width=1)

        # Paste original chart
        canvas.paste(orig, (BORDER_W, BORDER_W + HEADER_H))

        out = io.BytesIO()
        canvas.save(out, format="PNG")
        out.seek(0)
        return out

    except ImportError:
        buf.seek(0)
        return buf
    except Exception:
        buf.seek(0)
        return buf

# Chart metadata: type label, educational caption, accent color
_CHART_META = {
    "heatmap": (
        "Weekly Options Heatmap",
        "Shows Open Interest and Volume stacked by strike price for calls (green) and puts (red). "
        "Look for the largest bars — those are where the most contracts are positioned. "
        "The Max Pain strike (gold line) is where the market maker wins most. "
        "Spot price (cyan) shows where you are relative to the walls. "
        "Strikes with massive OI on both sides are pinch points — price tends to hover there into expiry.",
        "#00e5ff"
    ),
    "gex": (
        "GEX Heatmap",
        "Gamma Exposure by strike × expiry. Green = positive gamma (dealer pin zone — acts like a magnet, price is drawn here and held). "
        "Red = negative gamma (accelerant zone — if price reaches here, dealer hedging amplifies the move, it does not slow down). "
        "The right panel aggregates all expirations into one wall view. "
        "Read the cage: the deepest green cluster above spot is your ceiling, the deepest green below is your floor. "
        "If price breaks through a red zone, expect the move to accelerate, not stabilize.",
        "#00cc88"
    ),
    "iv_skew": (
        "IV Skew Surface",
        "Implied Volatility plotted across strikes for each expiry. A steep put skew (IV rising sharply below spot) means "
        "the market is pricing in downside fear — institutions are paying up for protection. "
        "A flat or inverted skew signals complacency. When call skew steepens, breakout premium is being bought. "
        "Watch for skew divergence between near-term and far-term expirations — that gap tells you where the risk is priced.",
        "#aa66ff"
    ),
    "maxpain": (
        "Max Pain Convergence",
        "Max Pain is the strike price where the total payout to options holders is minimized — meaning options writers (dealers) lose the least. "
        "As expiry approaches, price has a structural tendency to drift toward this level because dealer hedging activity creates gravity. "
        "The table shows Max Pain for each expiry. The chart shows where spot sits relative to pain across the term structure. "
        "A large gap between spot and Max Pain late in the week is a high-conviction mean reversion setup.",
        "#ffbd15"
    ),
    "smartflow": (
        "Smart Flow Scanner",
        "Flags options contracts where Volume/Open Interest ratio exceeds 2× and volume is above 500 contracts. "
        "This ratio spike means new money is entering — not just existing holders rolling positions. "
        "Sorted by ratio intensity. A 10× Vol/OI spike on a put at a strike below spot = someone is positioning for a breakdown. "
        "Cross-reference with the GEX chart — if the flow hits a negative GEX zone, the setup has structural backing.",
        "#ff6622"
    ),
    "whale": (
        "Whale Liquidity Profile",
        "A volume profile built exclusively from the top 3% highest-volume candles — institutional moves only, retail noise filtered out. "
        "Strong Bull (bright green) = institutions buying with conviction on that bar. Strong Bear (red) = institutions selling with conviction. "
        "The gold horizontal line is the POC (Point of Control) — the price level where the most institutional volume has traded. Price gravitates back here. "
        "The yellow wick absorption line spikes where institutions absorbed selling pressure (long lower wicks) or buying pressure (long upper wicks) on high volume — "
        "those levels are where the big money made their stand and will defend again.",
        "#00ddaa"
    ),
}

def build_chart(d: dict) -> io.BytesIO:
    strikes  = d["strikes"]
    n        = len(strikes)
    if n == 0:
        fig, ax = plt.subplots(figsize=(10, 4), facecolor=DARK_BG)
        ax.text(0.5, 0.5, "No data", color=WHITE, ha="center", transform=ax.transAxes)
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=120, facecolor=DARK_BG)
        plt.close(fig)
        buf.seek(0)
        return buf

    # Arrays
    call_oi  = np.array([d["call_oi"].get(k, 0)  / 1000 for k in strikes])
    put_oi   = np.array([d["put_oi"].get(k, 0)   / 1000 for k in strikes])
    call_vol = np.array([d["call_vol"].get(k, 0) / 1000 for k in strikes])
    put_vol  = np.array([d["put_vol"].get(k, 0)  / 1000 for k in strikes])

    y     = np.arange(n)
    bar_h = 0.72

    # ── Key level Y indices ──
    spot_y  = int(np.argmin(np.abs(np.array(strikes) - d["spot"])))
    mp_y    = strikes.index(d["max_pain"])     if d["max_pain"]      in strikes else None
    cw_y    = strikes.index(d["top_call_wall"]) if d["top_call_wall"] in strikes else None
    pw_y    = strikes.index(d["top_put_wall"])  if d["top_put_wall"]  in strikes else None

    # Dynamic figure height: ~0.30 inch per strike, min 9
    fig_h = max(9, min(n * 0.30 + 2.5, 22))
    fig   = plt.figure(figsize=(17, fig_h), facecolor=DARK_BG)

    # Layout: [Calls OI (4)] [Center spine (1)] [Puts OI (4)] [gap(0.3)] [Calls Vol(2.5)] [Puts Vol(2.5)]
    gs = GridSpec(
        1, 6, figure=fig,
        width_ratios=[4, 0.9, 4, 0.25, 2.5, 2.5],
        wspace=0.0,
        left=0.03, right=0.97, top=0.91, bottom=0.07
    )
    ax_coi  = fig.add_subplot(gs[0])   # Call OI  (inverted)
    ax_lbl  = fig.add_subplot(gs[1])   # Strike labels centre spine
    ax_poi  = fig.add_subplot(gs[2])   # Put OI
    ax_cvol = fig.add_subplot(gs[4])   # Call Volume (inverted)
    ax_pvol = fig.add_subplot(gs[5])   # Put Volume

    # ── Helpers ──
    def style_ax(ax, xlabel, invert=False):
        ax.set_facecolor(PANEL_BG)
        ax.set_yticks([])
        ax.set_xlabel(xlabel, color=DIM, fontsize=7.5)
        ax.tick_params(colors=DIM, labelsize=7)
        for sp in ax.spines.values():
            sp.set_color(BORDER)
        if invert:
            ax.invert_xaxis()

    def draw_level_band(ax, yi, color, alpha=0.12):
        ax.axhspan(yi - 0.5, yi + 0.5, color=color, alpha=alpha, zorder=0)

    def draw_hline(ax, yi, color, ls, lw, alpha=0.92):
        ax.axhline(yi, color=color, linestyle=ls, linewidth=lw, alpha=alpha, zorder=3)

    # ── OI Bars ──
    ax_coi.barh(y, call_oi, bar_h, color=GREEN, alpha=0.88)
    ax_poi.barh(y, put_oi,  bar_h, color=RED,   alpha=0.88)
    style_ax(ax_coi, "← Call OI  (K contracts)", invert=True)
    style_ax(ax_poi, "Put OI  (K contracts) →")

    # ── Volume Bars ──
    ax_cvol.barh(y, call_vol, bar_h, color=GREEN, alpha=0.72)
    ax_pvol.barh(y, put_vol,  bar_h, color=RED,   alpha=0.72)
    style_ax(ax_cvol, "← Call Vol (K)", invert=True)
    style_ax(ax_pvol, "Put Vol (K) →")

    # Column headers
    ax_coi.set_title("CALL  Open Interest", color=GREEN, fontsize=8.5, pad=5)
    ax_poi.set_title("PUT  Open Interest",  color=RED,   fontsize=8.5, pad=5)
    ax_cvol.set_title("CALL  Volume", color=GREEN, fontsize=8, pad=5)
    ax_pvol.set_title("PUT  Volume",  color=RED,   fontsize=8, pad=5)

    # ── Level bands + lines across all data axes ──
    for ax in [ax_coi, ax_poi, ax_cvol, ax_pvol]:
        ax.set_ylim(-0.5, n - 0.5)
        # Spot band
        draw_level_band(ax, spot_y, CYAN,  alpha=0.10)
        draw_hline(ax, spot_y, CYAN,  "-",  1.6)
        # Max pain
        if mp_y is not None:
            draw_level_band(ax, mp_y, GOLD, alpha=0.08)
            draw_hline(ax, mp_y, GOLD, ":", 1.4)
        # Call wall
        if cw_y is not None:
            draw_hline(ax, cw_y, GREEN, "-.", 0.9, alpha=0.65)
        # Put wall
        if pw_y is not None:
            draw_hline(ax, pw_y, RED, "-.", 0.9, alpha=0.65)
        # Alternating row shading for readability
        for yi in range(n):
            if yi % 2 == 0:
                ax.axhspan(yi - 0.5, yi + 0.5, color="#ffffff", alpha=0.018, zorder=0)

    # ── Centre Spine: Strike Price Labels ──
    ax_lbl.set_xlim(0, 1)
    ax_lbl.set_ylim(-0.5, n - 0.5)
    ax_lbl.set_xticks([])
    ax_lbl.set_facecolor("#0d0d1a")
    ax_lbl.spines["left"].set_color(BORDER)
    ax_lbl.spines["right"].set_color(BORDER)
    ax_lbl.spines["top"].set_color(BORDER)
    ax_lbl.spines["bottom"].set_color(BORDER)
    ax_lbl.set_title("Strike", color=DIM, fontsize=7.5, pad=5)

    for yi, k in enumerate(strikes):
        # Colour code label by level
        if yi == spot_y:
            fc, fw, fs = CYAN,  "bold", 7.5
        elif yi == mp_y:
            fc, fw, fs = GOLD,  "bold", 7.5
        elif yi == cw_y:
            fc, fw, fs = GREEN, "bold", 7.0
        elif yi == pw_y:
            fc, fw, fs = RED,   "bold", 7.0
        else:
            fc, fw, fs = WHITE, "normal", 6.8

        ax_lbl.text(
            0.5, yi, f"${k:.0f}",
            color=fc, fontsize=fs, fontweight=fw,
            ha="center", va="center"
        )

    # Level annotations on the right edge of the spine
    for yi, label, color in [
        (spot_y,  f"Spot",      CYAN),
        (mp_y,    "MaxPain",    GOLD),
        (cw_y,    "CallWall",   GREEN),
        (pw_y,    "PutWall",    RED),
    ]:
        if yi is None:
            continue
        ax_poi.text(
            ax_poi.get_xlim()[1] * 0.02 if ax_poi.get_xlim()[1] > 0 else 0.01,
            yi + 0.38, label,
            color=color, fontsize=6.0, va="bottom", alpha=0.85, zorder=5
        )

    # ── Title ──
    gex_sign = "+" if d["net_gex_m"] >= 0 else ""
    title_str = (
        f"Q-MATRIX  |  {d['symbol']} — Weekly Options Heatmap\n"
        f"Expiry: {d['expiry']}   |   Spot: ${d['spot']:.2f}   |   "
        f"Max Pain: ${d['max_pain']:.0f}   |   GEX: {gex_sign}{d['net_gex_m']}M   |   P/C: {d['pc_ratio']}"
    )
    fig.suptitle(title_str, color=WHITE, fontsize=9.5, fontweight="bold", y=0.975)

    # ── Legend ──
    handles = [
        mpatches.Patch(color=GREEN, label="Calls"),
        mpatches.Patch(color=RED,   label="Puts"),
        plt.Line2D([0],[0], color=CYAN,  lw=1.6, linestyle="-",  label=f"Spot  ${d['spot']:.2f}"),
        plt.Line2D([0],[0], color=GOLD,  lw=1.4, linestyle=":",  label=f"Max Pain  ${d['max_pain']:.0f}"),
        plt.Line2D([0],[0], color=GREEN, lw=0.9, linestyle="-.", label=f"Call Wall  ${d['top_call_wall']:.0f}"),
        plt.Line2D([0],[0], color=RED,   lw=0.9, linestyle="-.", label=f"Put Wall  ${d['top_put_wall']:.0f}"),
    ]
    fig.legend(
        handles=handles, loc="lower center", ncol=6, fontsize=7.5,
        facecolor="#0d0d1a", edgecolor=BORDER,
        labelcolor=WHITE, framealpha=0.95,
        bbox_to_anchor=(0.5, 0.0)
    )
    fig.patch.set_facecolor(DARK_BG)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=130, facecolor=DARK_BG, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


# ─────────────────────────────────────────────────────────────────────────────
# ENHANCED CHART PANELS (GEX Grid · IV Skew · Max Pain · Smart Flow)
# ─────────────────────────────────────────────────────────────────────────────
SKEW_COLORS = ["#ff4444","#ff8800","#ffdd00","#00cc88","#00aaff","#aa44ff","#ff44aa","#e2e8f0"]

def _empty_buf(msg="No data"):
    fig, ax = plt.subplots(figsize=(10, 3), facecolor=DARK_BG)
    ax.text(0.5, 0.5, msg, color=DIM, ha="center", va="center", transform=ax.transAxes, fontsize=10)
    ax.axis("off")
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=100, facecolor=DARK_BG, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf

def _ax_dark(ax):
    ax.set_facecolor(PANEL_BG)
    ax.tick_params(colors=DIM, labelsize=7)
    for sp in ax.spines.values():
        sp.set_color(BORDER)

def fetch_full_data(symbol: str, max_exp: int = 6):
    """Call options_heatmap_engine for multi-expiry data."""
    import os
    engine_paths = [
        os.path.join(os.path.dirname(__file__), "..", "scratch"),
        os.path.join(os.path.dirname(__file__), "."),
    ]
    for p in engine_paths:
        abs_p = os.path.abspath(p)
        if abs_p not in sys.path:
            sys.path.insert(0, abs_p)
    try:
        from options_heatmap_engine import fetch_and_compute
        return fetch_and_compute(symbol, max_expirations=max_exp)
    except Exception as e:
        print(f"  [{symbol}] Engine unavailable ({e}) — enhanced charts skipped.")
        return None

def send_image_to_discord(buf: io.BytesIO, filename: str, caption: str = "", symbol: str = None):
    """Post an image to the correct channel webhook, with optional text caption above it."""
    if buf is None:
        return
    webhook = get_webhook(symbol=symbol) if symbol else DISCORD_WEBHOOK
    buf.seek(0)
    payload = {"content": caption} if caption else {}
    resp = requests.post(
        webhook,
        data={"payload_json": json.dumps(payload)},
        files={"file": (filename, buf, "image/png")},
        timeout=30,
    )
    if resp.status_code not in (200, 204):
        print(f"  [IMG] Discord error {resp.status_code}: {resp.text[:120]}")

# ── 1. GEX Heatmap Grid + Aggregate Net GEX ──
def build_gex_chart(symbol: str, eng: dict, spot: float) -> io.BytesIO:
    gex_matrix = eng.get("gex_matrix", {})
    agg_gex    = eng.get("aggregate_gex", {})
    expirations = list(gex_matrix.keys())
    if not expirations or not agg_gex:
        return _empty_buf("No GEX data")

    raw_strikes = sorted(set(float(k) for exp in gex_matrix.values() for k in exp))
    strikes = [k for k in raw_strikes if abs(k - spot) / spot <= 0.12]
    if not strikes:
        return _empty_buf("No strikes in range")

    grid = np.zeros((len(strikes), len(expirations)))
    for j, exp in enumerate(expirations):
        for i, k in enumerate(strikes):
            grid[i, j] = gex_matrix[exp].get(str(k), gex_matrix[exp].get(k, 0))
    agg_vals = [float(agg_gex.get(str(k), agg_gex.get(k, 0))) for k in strikes]

    fig_h = max(8, min(len(strikes) * 0.22 + 2, 20))
    fig = plt.figure(figsize=(16, fig_h), facecolor=DARK_BG)
    gs  = GridSpec(1, 2, figure=fig, width_ratios=[3, 1], wspace=0.04,
                   left=0.04, right=0.97, top=0.91, bottom=0.09)
    ax_g = fig.add_subplot(gs[0])
    ax_a = fig.add_subplot(gs[1])

    vmax = max(abs(grid).max(), 0.01)
    im   = ax_g.imshow(grid, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax,
                       origin="lower", alpha=0.88)
    ax_g.set_xticks(range(len(expirations)))
    ax_g.set_xticklabels(expirations, rotation=28, ha="right", fontsize=7, color=WHITE)
    ax_g.set_yticks(range(len(strikes)))
    ax_g.set_yticklabels([f"${k:.0f}" for k in strikes], fontsize=6.5, color=WHITE)
    ax_g.set_title("GAMMA EXPOSURE GRID (Strikes × Expirations)", color=WHITE, fontsize=9, pad=5)
    _ax_dark(ax_g)
    spot_yi = int(np.argmin(np.abs(np.array(strikes) - spot)))
    ax_g.axhline(spot_yi, color=CYAN, lw=1.5, ls="--", alpha=0.9)
    cbar = fig.colorbar(im, ax=ax_g, shrink=0.55, pad=0.01)
    cbar.set_label("GEX ($M)", color=DIM, fontsize=7)
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color=DIM, fontsize=6)

    y = np.arange(len(strikes))
    ax_a.barh(y, agg_vals, 0.72, color=[GREEN if v >= 0 else RED for v in agg_vals], alpha=0.88)
    ax_a.axvline(0, color=WHITE, lw=0.6, alpha=0.4)
    ax_a.axhline(spot_yi, color=CYAN, lw=1.5, ls="--", alpha=0.9)
    ax_a.set_yticks(y)
    ax_a.set_yticklabels([f"${k:.0f}" for k in strikes], fontsize=6.5, color=WHITE)
    ax_a.set_title("AGGREGATE NET GEX", color=WHITE, fontsize=9, pad=5)
    ax_a.set_xlabel("Total Net GEX ($M)", color=DIM, fontsize=7.5)
    _ax_dark(ax_a)

    fig.suptitle(f"Q-MATRIX  |  {symbol} — GEX Heatmap",
                 color=WHITE, fontsize=10, fontweight="bold", y=0.975)
    fig.patch.set_facecolor(DARK_BG)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, facecolor=DARK_BG, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf

# ── 2. IV Skew Surface ──
def build_iv_skew_chart(symbol: str, eng: dict, spot: float) -> io.BytesIO:
    iv_skew = eng.get("iv_skew_curves", {})
    if not iv_skew:
        return _empty_buf("No IV skew data")

    fig, ax = plt.subplots(figsize=(14, 6), facecolor=DARK_BG)
    _ax_dark(ax)
    plotted = 0
    for idx, (exp, curve) in enumerate(iv_skew.items()):
        if not curve:
            continue
        pcts    = [pt["pct_from_spot"] for pt in curve]
        call_iv = [pt["call_iv"]       for pt in curve]
        put_iv  = [pt["put_iv"]        for pt in curve]
        smile   = [p_iv if p < 0 else c_iv for p, c_iv, p_iv in zip(pcts, call_iv, put_iv)]
        smile   = [max(0.0, v) for v in smile]
        ax.plot(pcts, smile, color=SKEW_COLORS[idx % len(SKEW_COLORS)],
                linewidth=1.4, alpha=0.9, label=exp)
        plotted += 1

    if plotted == 0:
        plt.close(fig)
        return _empty_buf("IV skew empty")

    ax.axvline(0, color=CYAN, lw=1.2, ls="--", alpha=0.75, label="ATM")
    ax.set_xlabel("Distance from Spot (%)", color=DIM, fontsize=8)
    ax.set_ylabel("Implied Volatility (IV %)", color=DIM, fontsize=8)
    ax.set_title("IMPLIED VOLATILITY SMILE (SKEW CURVES)", color=WHITE, fontsize=9, pad=5)
    ax.set_ylim(bottom=0)
    ax.legend(fontsize=7, facecolor="#0d0d1a", edgecolor=BORDER, labelcolor=WHITE,
              framealpha=0.9, loc="upper right", ncol=2)
    fig.suptitle(f"Q-MATRIX  |  {symbol} — IV Skew Surface",
                 color=WHITE, fontsize=10, fontweight="bold", y=0.99)
    fig.patch.set_facecolor(DARK_BG)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, facecolor=DARK_BG, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf

# ── 3. Max Pain Convergence (table + line chart) ──
def build_max_pain_chart(symbol: str, eng: dict, spot: float) -> io.BytesIO:
    es_list = eng.get("expiry_summary", [])
    if not es_list:
        return _empty_buf("No expiry summary")

    fig = plt.figure(figsize=(16, 6), facecolor=DARK_BG)
    gs  = GridSpec(1, 2, figure=fig, width_ratios=[1.1, 1], wspace=0.08,
                   left=0.03, right=0.97, top=0.88, bottom=0.10)
    ax_t = fig.add_subplot(gs[0])
    ax_c = fig.add_subplot(gs[1])

    # Table panel
    ax_t.set_facecolor(PANEL_BG)
    ax_t.set_xlim(0, 1); ax_t.set_ylim(0, 1); ax_t.axis("off")
    ax_t.set_title("EXPIRY SUMMARY TIMELINE", color=WHITE, fontsize=9, pad=5)
    cols   = ["EXPIRY","DTE","MAX PAIN","DIST %","P/C","CALL OI","PUT OI"]
    col_xs = [0.01, 0.22, 0.35, 0.48, 0.58, 0.69, 0.85]
    for cx, col in zip(col_xs, cols):
        ax_t.text(cx, 0.94, col, color=DIM, fontsize=6.5, fontweight="bold", va="top")
    ax_t.axhline(0.91, color=BORDER, lw=0.8)
    row_h = min(0.11, 0.87 / max(len(es_list), 1))
    for ri, es in enumerate(es_list[:8]):
        yp   = 0.89 - ri * row_h
        dist = es["max_pain_dist"]
        dc   = GREEN if dist >= 0 else RED
        rows = [
            (es["expiry"],                      WHITE),
            (f"{es['dte']}d",                   DIM),
            (f"${es['max_pain']:.0f}",          GOLD),
            (f"{'+' if dist>=0 else ''}{dist:.2f}%", dc),
            (f"{es['put_call_ratio']}",         WHITE),
            (f"{es['total_call_oi']:,}",        GREEN),
            (f"{es['total_put_oi']:,}",         RED),
        ]
        for cx, (val, fc) in zip(col_xs, rows):
            ax_t.text(cx, yp, val, color=fc, fontsize=6.5, va="top")
        if ri % 2 == 0:
            ax_t.axhspan(yp - row_h * 0.1, yp + row_h * 0.85, color="#fff", alpha=0.02)

    # Convergence line chart
    _ax_dark(ax_c)
    exps      = [es["expiry"]   for es in es_list]
    mp_prices = [es["max_pain"] for es in es_list]
    ax_c.plot(range(len(exps)), mp_prices, color=GOLD, lw=1.8, marker="o",
              markersize=5, label="Max Pain")
    ax_c.axhline(spot, color=CYAN, lw=1.4, ls="--", alpha=0.85, label=f"Spot ${spot:.2f}")
    ax_c.set_xticks(range(len(exps)))
    ax_c.set_xticklabels(exps, rotation=25, ha="right", fontsize=7, color=WHITE)
    ax_c.set_ylabel("Strike Price ($)", color=DIM, fontsize=8)
    ax_c.set_title("MAX PAIN vs SPOT CONVERGENCE", color=WHITE, fontsize=9, pad=5)
    ax_c.legend(fontsize=7.5, facecolor="#0d0d1a", edgecolor=BORDER, labelcolor=WHITE, framealpha=0.9)

    fig.suptitle(f"Q-MATRIX  |  {symbol} — Max Pain Convergence",
                 color=WHITE, fontsize=10, fontweight="bold", y=0.975)
    fig.patch.set_facecolor(DARK_BG)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, facecolor=DARK_BG, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf

# ── 4. Smart Flow Scanner (anomaly table) ──
def build_smart_flow_chart(symbol: str, eng: dict) -> io.BytesIO:
    rows = eng.get("unusual_activity", [])[:15]
    if not rows:
        return _empty_buf("No flow anomalies detected")

    fig_h = max(4, len(rows) * 0.37 + 2.2)
    fig, ax = plt.subplots(figsize=(15, fig_h), facecolor=DARK_BG)
    ax.set_facecolor(PANEL_BG)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.set_title(
        f"Q-MATRIX  |  {symbol}  —  FLOW ANOMALIES  (Vol/OI > 2.0  ·  Vol > 500)",
        color=WHITE, fontsize=9, pad=8
    )
    cols   = ["EXPIRY","DTE","STRIKE","TYPE","VOLUME","OPEN INT","VOL/OI","IV %","DIST %"]
    col_xs = [0.01, 0.12, 0.21, 0.31, 0.41, 0.52, 0.63, 0.73, 0.83]
    for cx, col in zip(col_xs, cols):
        ax.text(cx, 0.95, col, color=DIM, fontsize=7, fontweight="bold", va="top")
    ax.axhline(0.93, color=BORDER, lw=0.8)
    row_h = min(0.115, 0.90 / max(len(rows), 1))
    for ri, a in enumerate(rows):
        yp      = 0.92 - ri * row_h
        tc      = GREEN if a["type"] == "CALL" else RED
        ratio_c = "#ff8800" if a["vol_oi_ratio"] > 5 else GOLD if a["vol_oi_ratio"] > 3 else WHITE
        dist_c  = GREEN if a["pct_from_spot"] >= 0 else RED
        vals = [
            (a["expiry"],   WHITE),
            (f"{a['dte']}d", DIM),
            (f"${a['strike']:.2f}",   WHITE),
            (a["type"],     tc),
            (f"{a['volume']:,}",      WHITE),
            (f"{a['oi']:,}",          DIM),
            (f"{a['vol_oi_ratio']:.2f}x", ratio_c),
            (f"{a['iv']:.1f}%",       GOLD),
            (f"{'+' if a['pct_from_spot']>=0 else ''}{a['pct_from_spot']:.2f}%", dist_c),
        ]
        for cx, (val, fc) in zip(col_xs, vals):
            ax.text(cx, yp, val, color=fc, fontsize=7, va="top")
        if ri % 2 == 0:
            ax.axhspan(yp - row_h*0.15, yp + row_h*0.85, color="#fff", alpha=0.025)

    fig.patch.set_facecolor(DARK_BG)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, facecolor=DARK_BG, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


# ── 5. Whale Liquidity Profile + Wick Absorption ──
def build_whale_chart(symbol: str, eng: dict, spot: float) -> io.BytesIO:
    wp = eng.get("whale_profile", {})
    if not wp or not wp.get("bins"):
        return _empty_buf("No whale profile data")

    bins   = wp["bins"]
    levels = wp.get("levels", [])
    poc    = wp.get("poc_price", spot)

    # Arrays for chart
    prices       = [(b["price_bottom"] + b["price_top"]) / 2 for b in bins]
    strong_bull  = np.array([b["strong_bull"]  for b in bins])
    weak_bull    = np.array([b["weak_bull"]    for b in bins])
    weak_bear    = np.array([b["weak_bear"]    for b in bins])
    strong_bear  = np.array([b["strong_bear"]  for b in bins])
    absorption   = np.array([b["absorption"]   for b in bins])
    in_va        = [b["in_value_area"]         for b in bins]
    labels       = [f"${p:.1f}" for p in prices]

    fig_h = max(10, min(len(bins) * 0.30 + 2, 22))
    fig   = plt.figure(figsize=(18, fig_h), facecolor=DARK_BG)
    gs    = GridSpec(1, 2, figure=fig, width_ratios=[0.85, 2.15], wspace=0.07,
                     left=0.04, right=0.97, top=0.91, bottom=0.06)
    ax_l = fig.add_subplot(gs[0])   # absorption pillars table
    ax_r = fig.add_subplot(gs[1])   # whale profile chart

    # ── Left: Absorption Pillars ──
    ax_l.set_facecolor(PANEL_BG)
    ax_l.set_xlim(0, 1); ax_l.set_ylim(0, 1); ax_l.axis("off")
    ax_l.set_title("ABSORPTION PILLARS", color=WHITE, fontsize=9, pad=5)

    col_xs = [0.04, 0.44, 0.72]
    for cx, col in zip(col_xs, ["PRICE", "TYPE", "DIST"]):
        ax_l.text(cx, 0.965, col, color=DIM, fontsize=7, fontweight="bold", va="top")
    ax_l.axhline(0.945, color=BORDER, lw=0.8)

    n_levels = min(len(levels), 10)
    row_h = 0.87 / max(n_levels, 1)
    for ri, lv in enumerate(levels[:10]):
        yp     = 0.935 - ri * row_h
        dist   = round((lv["price"] - spot) / spot * 100, 2)
        is_res = lv["price"] > spot
        lc     = RED if is_res else GREEN
        lbl    = "RES" if is_res else "SUP"
        sign   = "+" if dist >= 0 else ""

        # Colored badge background
        ax_l.add_patch(mpatches.FancyBboxPatch(
            (0.38, yp - row_h * 0.65), 0.28, row_h * 0.78,
            boxstyle="round,pad=0.01", facecolor=lc, edgecolor="none", alpha=0.18))

        ax_l.text(col_xs[0], yp, f"${lv['price']:.2f}", color=WHITE,
                  fontsize=7.5, va="top", fontweight="bold")
        ax_l.text(col_xs[1], yp, lbl, color=lc,
                  fontsize=7, va="top", fontweight="bold")
        ax_l.text(col_xs[2], yp, f"{sign}{dist:.2f}%", color=lc,
                  fontsize=7, va="top")
        if ri % 2 == 0:
            ax_l.axhspan(yp - row_h * 0.65, yp + row_h * 0.15,
                         color="#fff", alpha=0.018)

    # POC callout
    ax_l.axhline(0.06, color=BORDER, lw=0.6)
    ax_l.text(0.04, 0.04, f"POC: ${poc:.2f}", color=GOLD,
              fontsize=8, fontweight="bold", va="bottom")
    ax_l.text(0.55, 0.04, f"Spot: ${spot:.2f}", color=CYAN,
              fontsize=8, fontweight="bold", va="bottom")

    # ── Right: Whale Volume Profile + Wick Absorption ──
    _ax_dark(ax_r)
    y = np.arange(len(bins))
    h = 0.78  # bar height

    # Normalise absorption for overlay scale
    abs_max   = absorption.max() if absorption.max() > 0 else 1
    total_max = (strong_bull + weak_bull + weak_bear + strong_bear).max()
    if total_max == 0: total_max = 1

    # Value area highlight
    for i, in_v in enumerate(in_va):
        if in_v:
            ax_r.axhspan(i - h/2, i + h/2, color=CYAN, alpha=0.055)

    # Stacked horizontal bars: Strong Bear | Weak Bear | Weak Bull | Strong Bull
    ax_r.barh(y,  strong_bear,  h, color="#cc0022",  alpha=0.88, label="Strong Bear")
    ax_r.barh(y,  weak_bear,    h, left=strong_bear,
              color="#882233",  alpha=0.88, label="Weak Bear")
    bull_left = strong_bear + weak_bear
    ax_r.barh(y,  weak_bull,    h, left=bull_left,
              color="#226644",  alpha=0.88, label="Weak Bull")
    ax_r.barh(y,  strong_bull,  h, left=bull_left + weak_bull,
              color=GREEN,      alpha=0.90, label="Strong Bull")

    # Wick absorption overlay — scaled to match bar axis
    abs_scaled = absorption / abs_max * total_max * 0.55
    ax_r.plot(abs_scaled, y, color=GOLD, lw=1.6, alpha=0.90,
              label="Wick Absorption", marker="o", markersize=2.5)

    # POC line
    poc_yi = int(np.argmin(np.abs(np.array(prices) - poc)))
    ax_r.axhline(poc_yi, color=GOLD, lw=1.8, ls="-", alpha=0.85, label=f"POC ${poc:.2f}")

    # Spot line
    spot_yi = int(np.argmin(np.abs(np.array(prices) - spot)))
    ax_r.axhline(spot_yi, color=CYAN, lw=1.5, ls="--", alpha=0.90,
                 label=f"Spot ${spot:.2f}")

    ax_r.set_yticks(y)
    ax_r.set_yticklabels(labels, fontsize=5.5, color=WHITE)
    ax_r.set_xlabel("Whale Profile Volume", color=DIM, fontsize=8)
    ax_r.set_title("WHALE PROFILE & WICK ABSORPTION", color=WHITE, fontsize=9, pad=5)

    # Secondary x-axis label for absorption
    ax_r2 = ax_r.twiny()
    ax_r2.set_xlim(ax_r.get_xlim())
    ax_r2.set_xlabel("← Wick Absorption (scaled)", color=GOLD, fontsize=7)
    ax_r2.tick_params(colors=GOLD, labelsize=6)
    ax_r2.set_facecolor(PANEL_BG)

    ax_r.legend(fontsize=7, facecolor="#0d0d1a", edgecolor=BORDER,
                labelcolor=WHITE, framealpha=0.9, loc="lower right",
                ncol=2, markerscale=1.5)

    fig.suptitle(f"Q-MATRIX  |  {symbol}  —  Whale Liquidity Profile",
                 color=WHITE, fontsize=10, fontweight="bold", y=0.975)
    fig.patch.set_facecolor(DARK_BG)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, facecolor=DARK_BG, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf

def send_enhanced_charts(symbol: str, spot: float, base_d: dict = None):
    """Fetch full engine data and post all enhanced panels to the ticker's channel."""
    print(f"  [{symbol}] Fetching multi-expiry engine data...")
    eng = fetch_full_data(symbol)
    if eng is None:
        return
    time.sleep(1)
    charts = [
        (build_gex_chart(symbol, eng, spot),     f"{symbol}_gex.png",       "gex"),
        (build_iv_skew_chart(symbol, eng, spot),  f"{symbol}_iv_skew.png",   "iv_skew"),
        (build_max_pain_chart(symbol, eng, spot), f"{symbol}_maxpain.png",   "maxpain"),
        (build_smart_flow_chart(symbol, eng),     f"{symbol}_smartflow.png", "smartflow"),
        (build_whale_chart(symbol, eng, spot),    f"{symbol}_whale.png",     "whale"),
    ]
    for buf, fname, key in charts:
        label, desc, _ = _CHART_META[key]
        now   = datetime.datetime.now()
        hr    = now.hour
        sweep = "\U0001f514 Market Open" if hr < 11 else ("\U0001f55b Midday" if hr < 14 else "\u26a1 Power Hour")
        ts    = now.strftime("%b %d %Y  %I:%M %p ET")
        caption = f"**{symbol}  —  {label}**  `{sweep}  \u00b7  {ts}`\n{desc}"
        send_image_to_discord(buf, fname, caption=caption, symbol=symbol)
        time.sleep(2)
    print(f"  [{symbol}] \u2713 Enhanced charts sent.")
    # ── DB1 Persistence — save all 6 module metrics ───────────────────────────
    try:
        from _db1_persistence import save_snapshot
        save_snapshot(base_d or {"symbol": symbol, "spot": spot}, eng)
    except Exception as _db1_err:
        pass  # Always silent — never block the sweep


# ─────────────────────────────────────────────────────────────────────────────
# GCP NATURAL LANGUAGE -- SENTIMENT ENRICHMENT (earnings tickers only)
# ─────────────────────────────────────────────────────────────────────────────
# Tickers that get NL sentiment wired into their embed (earnings-watch)
_SENTIMENT_TICKERS = {"CRM", "SNOW", "OKTA", "MDB", "NVDA", "MSFT", "META", "AMZN", "AAPL", "GOOGL", "TSLA"}

def _gcp_sentiment_field(symbol: str) -> dict | None:
    """
    Fetch recent news headlines for symbol via yfinance and run GCP NL sentiment.
    Returns a Discord embed field dict or None if GCP NL unavailable / not an earnings ticker.
    Always fails silently — never blocks the main sweep.
    """
    if symbol not in _SENTIMENT_TICKERS:
        return None
    try:
        import os as _os
        _os.environ.setdefault(
            "GOOGLE_APPLICATION_CREDENTIALS",
            r"H:\Trishula\Swarm_4_Integration\Swarm_4_SBM_FINAL INTEGRATION\Project-Swarm\trishula-gcp-key.json"
        )
        from google.cloud import language_v2

        # Pull yfinance news headlines (free, no API key needed)
        tk = yf.Ticker(symbol)
        news = tk.news or []
        headlines = " ".join(
            item.get("content", {}).get("title", "") or item.get("title", "")
            for item in news[:5]
        ).strip()
        if not headlines:
            return None

        client = language_v2.LanguageServiceClient()
        doc    = language_v2.Document(
            content=headlines[:1000],
            type_=language_v2.Document.Type.PLAIN_TEXT
        )
        sent = client.analyze_sentiment(request={"document": doc}).document_sentiment
        score = round(sent.score, 2)
        mag   = round(sent.magnitude, 2)

        if score >= 0.25:
            label = "🟢 Bullish"
        elif score <= -0.25:
            label = "🔻 Bearish"
        else:
            label = "↔ Neutral"

        return {
            "name":   "📰 News Sentiment (GCP NL)",
            "value":  f"`{label}` score `{score:+.2f}` mag `{mag:.2f}`",
            "inline": True,
        }
    except Exception:
        return None

# ─────────────────────────────────────────────────────────────────────────────
# R2-8: DBOI DISCORD FIELD BUILDER
# ─────────────────────────────────────────────────────────────────────────────
def _build_dboi_field(d: dict, gex_zero: float = None) -> str:
    """
    Build the value string for the '🔬 DBOI Walls' Discord embed field.
    Shows DBOI call wall, put wall, and zero-line.
    Compares DBOI zero vs GEX zero and flags confluence or divergence.
    """
    dcw  = d.get("dboi_call_wall")
    dpw  = d.get("dboi_put_wall")
    dz   = d.get("dboi_zero_line")
    spot = d.get("spot", 0)

    cw_str = f"**DBOI Call Wall:** `${dcw:.0f}`" if dcw is not None else "**DBOI Call Wall:** N/A"
    pw_str = f"**DBOI Put Wall:** `${dpw:.0f}`"  if dpw is not None else "**DBOI Put Wall:** N/A"
    dz_str = f"**DBOI Zero:** `${dz:.2f}`"        if dz  is not None else "**DBOI Zero:** N/A"

    lines = [
        f"{cw_str}  |  {pw_str}  |  {dz_str}",
        "_\\(delta-adjusted — more accurate than raw OI\\)_",
    ]

    # Compare DBOI zero vs GEX zero
    if dz is not None and gex_zero is not None and spot > 0:
        gap = abs(dz - gex_zero)
        pct_gap = gap / spot * 100
        if pct_gap < 0.30:
            lines.append(
                f"⚡ **LEVEL LOCK:** DBOI Zero `${dz:.2f}` ≈ GEX Zero `${gex_zero:.2f}` "
                f"(Δ`{gap:.2f}`) — **Extreme confluence — structural magnet confirmed**"
            )
        elif pct_gap < 1.00:
            lines.append(
                f"🟡 DBOI Zero `${dz:.2f}` vs GEX Zero `${gex_zero:.2f}` "
                f"(Δ`{gap:.2f}`, `{pct_gap:.2f}%`) — Modest divergence, watch for recalibration"
            )
        else:
            lines.append(
                f"🔴 **DIVERGENCE:** DBOI Zero `${dz:.2f}` vs GEX Zero `${gex_zero:.2f}` "
                f"(Δ`{gap:.2f}`, `{pct_gap:.2f}%`) — Levels split; delta hedging pressure ≠ gamma pinning"
            )

    return "\n".join(lines)

# ─────────────────────────────────────────────────────────────────────────────
# LOCAL OLLAMA THESIS GENERATION (P3-C)
# ─────────────────────────────────────────────────────────────────────────────
def generate_local_ollama_thesis(d: dict, squeeze_status: str, wvf_val: float) -> str:
    """Query local Ollama instance for structured options thesis, with fallback."""
    try:
        # Check available models
        r_models = requests.get("http://localhost:11434/api/tags", timeout=2)
        if r_models.status_code != 200:
            return ""
        
        models = [m["name"] for m in r_models.json().get("models", [])]
        preferred = ["qwen2.5-coder:7b", "llama3:latest", "trishula-core-kill:latest", "dolphin-llama3:latest", "llama3.3:latest"]
        selected_model = None
        for p in preferred:
            if p in models:
                selected_model = p
                break
        
        if not selected_model:
            # Fallback to prefix matching
            for p in preferred:
                prefix = p.split(":")[0]
                for m in models:
                    if m.startswith(prefix):
                        selected_model = m
                        break
                if selected_model:
                    break
        
        if not selected_model and models:
            selected_model = models[0]
            
        if not selected_model:
            return ""

        direction = "BULLISH MAGNET" if d["net_gex_m"] >= 0 else "BEARISH REVERSIBLE"
        gex_sign = "+" if d["net_gex_m"] >= 0 else ""
        
        prompt = (
            f"You are Trishula Black, an elite institutional options strategist. Write a concise, high-conviction 2-sentence market intelligence thesis for {d['symbol']} based on this option chain data:\n"
            f"- Spot Price: ${d['spot']:.2f}\n"
            f"- Max Pain: ${d['max_pain']:.0f}\n"
            f"- Net GEX: {gex_sign}{d['net_gex_m']}M\n"
            f"- Put/Call Ratio: {d['pc_ratio']} (Top Call Wall: ${d['top_call_wall']:.0f}, Top Put Wall: ${d['top_put_wall']:.0f})\n"
            f"- Technical Squeeze Status: {squeeze_status}\n"
            f"- Williams Vix Fix: {wvf_val:.2f}%\n\n"
            f"Analyze the dealer hedging gravity and potential pinning/expansion. Output ONLY the 2-sentence quote. Do not include introductory text, explanations, or label headers. Keep it professional, sharp, and technical."
        )
        
        payload = {
            "model": selected_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "max_tokens": 120
            }
        }
        
        # 15s timeout for fast execution
        r = requests.post("http://localhost:11434/api/generate", json=payload, timeout=15)
        if r.status_code == 200:
            res = r.json()
            thesis = res.get("response", "").strip()
            # Clean up any wrapping quotes the model might have returned
            if thesis.startswith('"') and thesis.endswith('"'):
                thesis = thesis[1:-1].strip()
            return f"\"{thesis}\""
    except Exception as e:
        print(f"  [Ollama] Local thesis generation failed: {e} (using fallback)")
    return ""

# ─────────────────────────────────────────────────────────────────────────────
# DISCORD SEND
# ─────────────────────────────────────────────────────────────────────────────
def send_to_discord(d: dict, chart_buf: io.BytesIO,
                    gex_zero: float = None, whale_poc: float = None,
                    whale_bull_pct: float = None):
    """Post the main Q-Matrix embed with heatmap + GEX level chart attached."""
    webhook    = get_webhook(symbol=d["symbol"])
    gex_sign  = "+" if d["net_gex_m"] >= 0 else ""
    gex_color = 0x00cc88 if d["net_gex_m"] >= 0 else 0xff3344
    pc_note   = "Bearish Skew 🔻" if d["pc_ratio"] > 1.0 else "Bullish Skew 🟢" if d["pc_ratio"] < 0.8 else "Neutral ↔"

    # ── ADVANCED TECH CONFLUENCES & AI THESIS (Panel 1 Integration) ──
    wvf_val, squeeze_status, ai_thesis = 4.0, "🟢 COMPRESSED (Released)", ""
    try:
        import pandas as pd
        tk = yf.Ticker(d["symbol"])
        hist = tk.history(period="60d")
        if not hist.empty:
            closes = hist["Close"]
            highs  = hist["High"]
            lows   = hist["Low"]
            # Williams Vix Fix
            highest_close = closes.rolling(window=22).max()
            wvf = ((highest_close - lows) / highest_close) * 100
            wvf_val = float(wvf.iloc[-1])
            # Squeeze Momentum
            sma20 = closes.rolling(window=20).mean()
            std20 = closes.rolling(window=20).std()
            bb_upper = sma20 + 2 * std20
            bb_lower = sma20 - 2 * std20
            tr = pd.concat([highs - lows, abs(highs - closes.shift(1)), abs(lows - closes.shift(1))], axis=1).max(axis=1)
            atr20 = tr.rolling(window=20).mean()
            ema20 = closes.ewm(span=20, adjust=False).mean()
            kc_upper = ema20 + 1.5 * atr20
            kc_lower = ema20 - 1.5 * atr20
            squeeze_active = (bb_upper < kc_upper).iloc[-1] and (bb_lower > kc_lower).iloc[-1]
            squeeze_status = "🔴 **ACTIVE SQUEEZE** (Coiled)" if squeeze_active else "🟢 **RELEASED** (Dispersion)"
    except Exception as e:
        print(f"  [{d['symbol']}] Technical confluence calculation error: {e}")

    # Generate Swarm AI Expert Thesis (Local Ollama first, fallback to deterministic)
    ai_thesis = generate_local_ollama_thesis(d, squeeze_status, wvf_val)
    if not ai_thesis:
        direction = "BULLISH MAGNET" if d["net_gex_m"] >= 0 else "BEARISH REVERSIBLE"
        ai_thesis = (f"\"{d['symbol']} spot closes at ${d['spot']:.2f} showing an {squeeze_status.replace('**', '')} "
                     f"options structure. Strong option walls reveal a massive {direction} pinning at the "
                     f"${d['top_call_wall'] if d['net_gex_m'] >= 0 else d['top_put_wall']:.0f} wall level with "
                     f"{gex_sign}{d['net_gex_m']}M GEX force. Expect dealer hedging gravity to forcefully attract price "
                     f"action as expiration approaches.\"")


    anomaly_lines = ""
    for side, K, ratio, vol in d["anomalies"][:3]:
        emoji = "📞" if side == "CALL" else "📉"
        anomaly_lines += f"{emoji} `${K:.0f} {side}` — Vol/OI **{ratio}x** ({vol:,} contracts)\n"

    embed = {
        "title": f"\U0001f9e0 Q-MATRIX  |  {d['symbol']} — Weekly Options Heatmap  ·  Exp: {d['expiry']}",
        "color": gex_color,
        "fields": [
            {"name": "Spot",          "value": f"`${d['spot']:.2f}`",                    "inline": True},
            {"name": "Max Pain",      "value": f"`${d['max_pain']:.0f}`",                "inline": True},
            {"name": "Net GEX",       "value": f"`{gex_sign}{d['net_gex_m']}M`",         "inline": True},
            {"name": "P/C Ratio",     "value": f"`{d['pc_ratio']}` — {pc_note}",         "inline": True},
            {"name": "Top Call Wall", "value": f"`${d['top_call_wall']:.0f}` ({d['tot_call_oi']:,} OI)", "inline": True},
            {"name": "Top Put Wall",  "value": f"`${d['top_put_wall']:.0f}` ({d['tot_put_oi']:,} OI)",  "inline": True},
            {"name": "🔬 DBOI Walls",  "value": _build_dboi_field(d, gex_zero), "inline": False},
            {"name": "📊 Swarm Confluence Suite", "value": f"• **Squeeze Status:** {squeeze_status}\n• **Williams Vix Fix:** `{wvf_val:.2f}%` ({'⚠️ Spike' if wvf_val > 12 else '🟢 Compression'})", "inline": False},
            {"name": "🤖 Swarm AI Intelligence Thesis", "value": ai_thesis, "inline": False},
            {"name": "\u26a1 Flow Anomalies (Vol/OI spike)", "value": anomaly_lines or "None detected", "inline": False},
        ],
        "footer": {"text": "Q-Matrix  \u00b7  Trishula QuantNode"},
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    # ── R2-5: GEX Expiry Stack field ──────────────────────────────────────────
    gex_stack = d.get("gex_stack")
    if gex_stack:
        stack_field = _format_expiry_stack_field(gex_stack)
        if stack_field:
            embed["fields"].append(stack_field)

    # GCP NL sentiment — high-profile tickers only, silent fallback (never blocks sweep)
    sentiment_field = _gcp_sentiment_field(d["symbol"])
    if sentiment_field:
        embed["fields"].insert(-1, sentiment_field)

    # ── StockTwits sentiment field (P3-A) ──────────────────────────────────────
    if _STOCKTWITS_AVAILABLE:
        try:
            st_field = _st_field(d["symbol"])
            if st_field:
                embed["fields"].insert(-1, st_field)
        except Exception:
            pass

    # ── Earnings warning field (P3-B) ──────────────────────────────────────────
    if _NEWS_FEED_AVAILABLE:
        try:
            earn_flag = _earnings_flag(d["symbol"])
            if earn_flag:
                embed["fields"].append({
                    "name":   "📅 Earnings Alert",
                    "value":  earn_flag,
                    "inline": False,
                })
                # Colour the embed red/orange when earnings imminent
                days_left = _days_to_earnings(d["symbol"])
                if days_left <= 3:
                    embed["color"] = 0xff8800  # Orange alert
        except Exception:
            pass

    # ── Macro events field ─────────────────────────────────────────────────────
    if _NEWS_FEED_AVAILABLE:
        try:
            macro_field = _macro_events_field(days_ahead=7)
            if macro_field:
                embed["fields"].append(macro_field)
        except Exception:
            pass


    # ── Delta comparison vs last scan (Since Last Scan field) ─────────────────
    try:
        from _delta_compare import compute_delta_fields
        delta_fields = compute_delta_fields(
            ticker=d["symbol"],
            current_spot=d["spot"],
            current_gex_m=d["net_gex_m"],
            current_gex_zero=gex_zero,
            current_whale_bull_pct=whale_bull_pct,
        )
        for df in delta_fields:
            embed["fields"].append(df)
    except Exception as _delta_err:
        pass  # always silent

    label, desc, _ = _CHART_META["heatmap"]
    now   = datetime.datetime.now()
    hr    = now.hour
    sweep = "🔔 Market Open" if hr < 11 else ("🕛 Midday" if hr < 14 else "⚡ Power Hour")
    ts    = now.strftime("%b %d %Y  %I:%M %p ET")
    heatmap_caption = f"**{d['symbol']}  —  {label}**  `{sweep}  ·  {ts}`\n{desc}"

    payload = {"content": heatmap_caption, "embeds": [embed]}
    chart_buf.seek(0)

    resp = requests.post(
        webhook,
        data={"payload_json": json.dumps(payload)},
        files={"file": (f"{d['symbol']}_heatmap.png", chart_buf, "image/png")},
        timeout=30,
    )

    if resp.status_code not in (200, 204):
        print(f"  [{d['symbol']}] Discord error {resp.status_code}: {resp.text[:200]}")
    else:
        print(f"  [{d['symbol']}] ✓ Embed sent to Discord.")

    # ── GEX Level Chart ────────────────────────────────────────────────
    try:
        from _gex_level_chart import build_gex_level_chart
        gex_chart_buf = build_gex_level_chart(
            symbol=d["symbol"],
            spot=d["spot"],
            max_pain=d["max_pain"],
            net_gex_m=d["net_gex_m"],
            gex_zero=gex_zero,
            whale_poc=whale_poc,
            call_wall=d.get("top_call_wall"),
            put_wall=d.get("top_put_wall"),
            expiry=d.get("expiry", ""),
        )
        time.sleep(1)  # rate-limit gap
        gex_chart_buf.seek(0)
        gex_resp = requests.post(
            webhook,
            data={"payload_json": json.dumps({
                "content": f"`{d['symbol']}` — GEX Level Map  ·  Spot vs Key Structural Levels"
            })},
            files={"file": (f"{d['symbol']}_gex_levels.png", gex_chart_buf, "image/png")},
            timeout=30,
        )
        if gex_resp.status_code not in (200, 204):
            print(f"  [{d['symbol']}] GEX chart upload error {gex_resp.status_code}")
        else:
            print(f"  [{d['symbol']}] ✓ GEX level chart uploaded.")
    except Exception as _gex_err:
        print(f"  [{d['symbol']}] GEX chart error (non-fatal): {str(_gex_err)[:80]}")


def send_intro():
    now_str = datetime.datetime.now().strftime("%A %b %d %Y  %I:%M %p ET")
    embed = {
        "title": "Q-MATRIX  —  WEEKLY SWEEP",
        "description": (
            f"**Run Started:** `{now_str}`\n"
            f"**Tickers:** `{', '.join(TICKERS)}`\n\n"
            "Scanning nearest weekly expiry for each ticker.\n"
            "Metrics: Max Pain · Net GEX · P/C Ratio · Call/Put Walls · Flow Anomalies"
        ),
        "color": 0x00ffbb,
        "footer": {"text": "Q-Matrix  ·  Trishula QuantNode"},
    }
    requests.post(DISCORD_WEBHOOK, json={"embeds": [embed]}, timeout=20)

def send_summary(results: list):
    lines = []
    for d in results:
        gex_str  = f"+{d['net_gex_m']}M" if d['net_gex_m'] >= 0 else f"{d['net_gex_m']}M"
        pc_emoji = "🔻" if d['pc_ratio'] > 1.0 else "🟢"
        lines.append(
            f"`{d['symbol']:<5}` Spot `${d['spot']:.2f}` | MP `${d['max_pain']:.0f}` | "
            f"GEX `{gex_str}` | P/C `{d['pc_ratio']}` {pc_emoji}"
        )
    embed = {
        "title": "Q-MATRIX  —  Summary",
        "description": "\n".join(lines),
        "color": 0xffbd15,
        "footer": {"text": "Q-Matrix  ·  Trishula QuantNode"},
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    resp = requests.post(DISCORD_WEBHOOK, json={"embeds": [embed]}, timeout=20)
    if resp.status_code not in (200, 204):
        print(f"[SUMMARY] Discord error {resp.status_code}")
    else:
        print("[SUMMARY] ✓ Summary sent.")

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
import argparse

# Macro module — graceful fallback if not present
try:
    import os as _os
    import sys as _sys
    _sys.path.insert(0, _os.path.dirname(__file__))
    from qmatrix_macro import (
        fetch_all_macro, build_macro_panel, build_macro_embed,
        fetch_ticker_fundamentals
    )
    _MACRO_AVAILABLE = True
except Exception as _macro_err:
    print(f"[MACRO] Module unavailable: {_macro_err}")
    _MACRO_AVAILABLE = False

def run_sweep(ticker_list: list, mode_label: str, expiry_fn):
    """Fetch macro pulse, then chart + post all tickers."""
    global _OHLCV_BATCH_CACHE
    now_str = datetime.datetime.now().strftime("%A %b %d %Y  %I:%M %p ET")
    mode_color = 0x00ffbb if mode_label == "WEEKLY" else 0x00aaff

    # ── Pre-fetch batch OHLCV for all tickers in ONE Polygon call ──
    if _POLYGON_AVAILABLE:
        try:
            print(f"\n[{mode_label}][BATCH] Pre-fetching grouped daily OHLCV for {len(ticker_list)} tickers...")
            _OHLCV_BATCH_CACHE = _polygon_batch_ohlcv(ticker_list)
            hits = sum(1 for t in ticker_list if t.upper() in _OHLCV_BATCH_CACHE)
            print(f"  [BATCH] {hits}/{len(ticker_list)} tickers populated from Polygon grouped daily.")
        except Exception as _be:
            print(f"  [BATCH] Grouped daily fetch failed ({_be}) — will use individual calls.")
            _OHLCV_BATCH_CACHE = {}

    # ── Macro Pulse (fires once per sweep) ──
    macro = None
    if _MACRO_AVAILABLE:
        print(f"\n[{mode_label}][MACRO] Fetching macro context...")
        try:
            macro = fetch_all_macro()
            macro_chart = build_macro_panel(macro)
            macro_embed = build_macro_embed(macro)
            macro_chart.seek(0)
            requests.post(
                WEBHOOK_MACRO,
                data={"payload_json": json.dumps({"embeds": [macro_embed]})},
                files={"file": ("macro_pulse.png", macro_chart, "image/png")},
                timeout=30,
            )
            print(f"  [MACRO] ✓ Macro Pulse sent to #macro-pulse.")
            time.sleep(2)
        except Exception as e:
            print(f"  [MACRO] Error: {e}")

    intro_embed = {
        "title": f"Q-MATRIX  —  {mode_label} SWEEP",
        "description": (
            f"**{now_str}**\n"
            f"**Tickers:** `{', '.join(ticker_list)}`\n"
            f"Scanning {mode_label.lower()} expiry  ·  Max Pain  ·  GEX  ·  P/C  ·  Walls  ·  Flow Anomalies"
        ),
        "color": mode_color,
        "footer": {"text": "Q-Matrix  ·  Trishula QuantNode"},
    }
    requests.post(get_webhook(channel="macro"), json={"embeds": [intro_embed]}, timeout=20)
    time.sleep(1)

    results = []
    for symbol in ticker_list:
        print(f"\n[{mode_label}][{symbol}]")
        tk  = yf.Ticker(symbol)
        exp = expiry_fn(tk)
        if exp is None:
            print(f"  [{symbol}] No valid expiry found — skipping.")
            continue
        d = process_ticker_with_expiry(symbol, exp)
        if d is None:
            continue

        # ── R2-5: Multi-Expiry GEX Stack ──────────────────────────────────────
        try:
            spot_for_stack = d.get("spot")
            gex_stack = stack_gex_expiries(symbol, tk_obj=tk, spot=spot_for_stack)
            d["gex_stack"] = gex_stack
            # Inject top-level fields for DB1
            d["dominant_expiry"]  = gex_stack.get("dominant_expiry")
            d["stacked_gex_zero"] = gex_stack.get("stacked_gex_zero")
            d["expiry_oi_weight"] = json.dumps(gex_stack.get("expiry_oi_weight", {}))
            print(f"  [{symbol}] GEX stack: dominant={d['dominant_expiry']}  "
                  f"stacked_zero={d['stacked_gex_zero']}")
        except Exception as _gsx:
            print(f"  [{symbol}] GEX stack error (non-fatal): {_gsx}")
            d["gex_stack"]        = {}
            d["dominant_expiry"]  = None
            d["stacked_gex_zero"] = None
            d["expiry_oi_weight"] = "{}"

        # ── Fundamentals (earnings / SI / insider / WSB) ──
        fundamentals = {}
        if _MACRO_AVAILABLE:
            try:
                fundamentals = fetch_ticker_fundamentals(symbol, exp)
            except Exception as fe:
                print(f"  [{symbol}] Fundamentals error: {fe}")
        d["fundamentals"] = fundamentals

        chart_buf = build_chart(d)

        # ── Extract engine-level data for GEX chart + delta compare ──
        _gex_zero_val    = None
        _whale_poc_val   = None
        _whale_bull_val  = None
        try:
            eng_data = fetch_full_data(symbol, max_exp=4)
            if eng_data:
                # GEX zero crossing
                agg_gex = eng_data.get("aggregate_gex", {})
                if agg_gex:
                    strikes_s  = sorted(float(k) for k in agg_gex.keys())
                    gex_vals_s = [float(agg_gex.get(str(k), agg_gex.get(k, 0))) for k in strikes_s]
                    for _i in range(len(gex_vals_s) - 1):
                        if gex_vals_s[_i] * gex_vals_s[_i+1] < 0:
                            _gex_zero_val = round(
                                strikes_s[_i] + (strikes_s[_i+1] - strikes_s[_i]) *
                                abs(gex_vals_s[_i]) / (abs(gex_vals_s[_i]) + abs(gex_vals_s[_i+1])), 2
                            )
                            break
                # Whale POC + bull%
                wp = eng_data.get("whale_profile", {})
                if wp:
                    _whale_poc_val = float(wp.get("poc_price", 0)) or None
                    bins = wp.get("bins", [])
                    if bins:
                        total_vol = sum(b.get("strong_bull", 0) + b.get("weak_bull", 0) +
                                        b.get("strong_bear", 0) + b.get("weak_bear", 0) for b in bins)
                        bull_vol  = sum(b.get("strong_bull", 0) + b.get("weak_bull", 0) for b in bins)
                        _whale_bull_val = round(bull_vol / total_vol * 100, 2) if total_vol > 0 else None
        except Exception as _eng_ex:
            pass  # always silent

        send_to_discord(d, chart_buf,
                        gex_zero=_gex_zero_val,
                        whale_poc=_whale_poc_val,
                        whale_bull_pct=_whale_bull_val)
        time.sleep(2)
        send_enhanced_charts(symbol, d["spot"], base_d=d)
        results.append(d)
        time.sleep(DELAY_SECS)

    if results:
        lines = []
        for d in results:
            gex_str  = f"+{d['net_gex_m']}M" if d['net_gex_m'] >= 0 else f"{d['net_gex_m']}M"
            pc_emoji = "🔻" if d['pc_ratio'] > 1.0 else "🟢"
            f = d.get("fundamentals", {})
            si_str  = f" | SI `{f['short_pct']}%`"   if "short_pct"  in f else ""
            ins_str = f" | Ins `{f['insider_signal']}`" if "insider_signal" in f else ""
            wsb_str = f" | WSB `{f['wsb_mentions']}`" if "wsb_mentions" in f else ""
            earn_str = " | ⚠️ Earn" if f.get("earnings_in_window") else ""
            lines.append(
                f"`{d['symbol']:<5}` `${d['spot']:.2f}` MP:`${d['max_pain']:.0f}` "
                f"GEX:`{gex_str}` P/C:`{d['pc_ratio']}` {pc_emoji}"
                f"{si_str}{ins_str}{wsb_str}{earn_str}"
            )
        summary_embed = {
            "title": f"Q-MATRIX  —  {mode_label} Summary",
            "description": "\n".join(lines),
            "color": 0xffbd15,
            "footer": {"text": "Q-Matrix  ·  Trishula QuantNode"},
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        # Summary goes to macro-pulse as a master overview
        requests.post(WEBHOOK_MACRO, json={"embeds": [summary_embed]}, timeout=20)
        print(f"[{mode_label}][SUMMARY] ✓ Sent to #macro-pulse.")

    return results


def process_ticker_with_expiry(symbol: str, expiry: str):
    """Same as process_ticker but with a fixed expiry string."""
    import yfinance as yf
    tk = yf.Ticker(symbol)

    # ── Spot price: batch cache first, then Polygon live, then yfinance ──
    spot = None
    sym_up = symbol.upper()

    # 1. Check batch OHLCV cache (populated at top of run_sweep)
    if sym_up in _OHLCV_BATCH_CACHE:
        cached_close = _OHLCV_BATCH_CACHE[sym_up].get("Close", 0)
        if cached_close and cached_close > 0:
            spot = float(cached_close)
            print(f"  [{symbol}] Spot from batch cache: ${spot:.2f}")

    # 2. Polygon live quote
    if not spot and _POLYGON_AVAILABLE:
        try:
            poly_price = _polygon_spot(symbol)
            if poly_price and poly_price > 0:
                spot = float(poly_price)
                print(f"  [{symbol}] Spot from Polygon live: ${spot:.2f}")
        except Exception as _pe:
            print(f"  [{symbol}] Polygon spot failed ({_pe}), falling back to yfinance")

    # 3. yfinance fallback
    if not spot:
        try:
            spot = float(tk.fast_info.last_price)
        except Exception:
            hist = tk.history(period="1d")
            spot = float(hist["Close"].iloc[-1]) if not hist.empty else None
    if not spot:
        return None

    exp_dt = datetime.datetime.strptime(expiry, "%Y-%m-%d")
    T = max((exp_dt - datetime.datetime.now()).total_seconds() / (365.25*24*3600), 1/365)

    try:
        chain = tk.option_chain(expiry)
        calls = chain.calls.fillna(0)
        puts  = chain.puts.fillna(0)
    except Exception as e:
        print(f"  [{symbol}] Chain error: {e}")
        return None

    lo = spot * (1 - STRIKE_RANGE)
    hi = spot * (1 + STRIKE_RANGE)
    calls = calls[(calls["strike"] >= lo) & (calls["strike"] <= hi)].copy()
    puts  = puts[ (puts["strike"]  >= lo) & (puts["strike"]  <= hi)].copy()

    all_strikes = sorted(set(calls["strike"].tolist()) | set(puts["strike"].tolist()))
    call_oi  = dict(zip(calls["strike"], calls["openInterest"]))
    put_oi   = dict(zip(puts["strike"],  puts["openInterest"]))
    call_vol = dict(zip(calls["strike"], calls["volume"]))
    put_vol  = dict(zip(puts["strike"],  puts["volume"]))
    call_iv  = dict(zip(calls["strike"], calls["impliedVolatility"]))
    put_iv   = dict(zip(puts["strike"],  puts["impliedVolatility"]))

    tot_call_oi = sum(call_oi.values())
    tot_put_oi  = sum(put_oi.values())
    pc_ratio    = round(tot_put_oi / tot_call_oi, 2) if tot_call_oi > 0 else 0.0
    max_pain    = compute_max_pain(all_strikes, call_oi, put_oi)

    net_gex = 0.0
    for K in all_strikes:
        iv_c = call_iv.get(K, 0.30) or 0.30
        iv_p = put_iv.get(K,  0.30) or 0.30
        net_gex += (call_oi.get(K,0)*bs_gamma(spot,K,T,RFR,iv_c) - put_oi.get(K,0)*bs_gamma(spot,K,T,RFR,iv_p)) * 100 * spot
    net_gex_m = round(net_gex / 1_000_000, 2)

    top_call_wall = max(call_oi, key=call_oi.get) if call_oi else spot
    top_put_wall  = max(put_oi,  key=put_oi.get)  if put_oi  else spot

    anomalies = []
    for K in all_strikes:
        for side, oi_d, vol_d in [("CALL", call_oi, call_vol), ("PUT", put_oi, put_vol)]:
            oi_v, vol_v = oi_d.get(K,0), vol_d.get(K,0)
            if oi_v > 0 and vol_v > 300 and vol_v/oi_v > 2.0:
                anomalies.append((side, K, round(vol_v/oi_v,1), int(vol_v)))
    anomalies.sort(key=lambda x: x[2], reverse=True)

    # ── vol_spike: 1 if total options vol > 2× 20-day avg stock volume ──
    try:
        hist20 = tk.history(period="25d")
        avg_vol_20d = float(hist20["Volume"].tail(20).mean()) if len(hist20) >= 5 else 0.0
        tot_options_vol = sum(call_vol.values()) + sum(put_vol.values())
        vol_spike = 1 if (avg_vol_20d > 0 and tot_options_vol > 2 * avg_vol_20d) else 0
    except Exception:
        vol_spike = 0

    # ── whale_flow_flag: 1 if any strike has Vol/OI > 5× with vol > 1000 ──
    whale_flow_flag = 0
    for K in all_strikes:
        for oi_d, vol_d in [(call_oi, call_vol), (put_oi, put_vol)]:
            oi_v  = oi_d.get(K, 0)
            vol_v = vol_d.get(K, 0)
            if oi_v > 0 and vol_v > 1000 and vol_v / oi_v > 5.0:
                whale_flow_flag = 1
                break
        if whale_flow_flag:
            break

    # ── Delta-Adjusted OI (DBOI) ─────────────────────────────────────────────
    dboi_call_per_k = {}
    dboi_put_per_k  = {}
    net_dboi_per_k  = {}
    net_dboi_total  = 0.0
    for K in all_strikes:
        iv_c = call_iv.get(K, 0.30) or 0.30
        iv_p = put_iv.get(K,  0.30) or 0.30
        d_c  = bs_delta_call(spot, K, T, RFR, iv_c)
        d_p  = bs_delta_put(spot,  K, T, RFR, iv_p)
        dc   = call_oi.get(K, 0) * d_c * 100
        dp   = put_oi.get(K,  0) * d_p * 100
        dboi_call_per_k[K] = dc
        dboi_put_per_k[K]  = dp
        net_dboi_per_k[K]  = dc - dp
        net_dboi_total    += dc - dp

    dboi_call_wall = max(dboi_call_per_k, key=dboi_call_per_k.get) if dboi_call_per_k else spot
    dboi_put_wall  = max(dboi_put_per_k,  key=dboi_put_per_k.get)  if dboi_put_per_k  else spot

    dboi_zero_line = None
    _sorted_k = sorted(all_strikes)
    for _i in range(len(_sorted_k) - 1):
        _ka, _kb = _sorted_k[_i], _sorted_k[_i+1]
        _va, _vb = net_dboi_per_k[_ka], net_dboi_per_k[_kb]
        if _va * _vb < 0:
            dboi_zero_line = round(
                _ka + (_kb - _ka) * abs(_va) / (abs(_va) + abs(_vb)), 2
            )
            break
    net_dboi_m = round(net_dboi_total / 1_000_000, 4)

    return {
        "symbol":          symbol,      "spot":     spot,
        "expiry":          expiry,      "T":        T,
        "strikes":         all_strikes,
        "call_oi":         call_oi,     "put_oi":   put_oi,
        "call_vol":        call_vol,    "put_vol":  put_vol,
        "max_pain":        max_pain,    "net_gex_m": net_gex_m,
        "pc_ratio":        pc_ratio,
        "top_call_wall":   top_call_wall,
        "top_put_wall":    top_put_wall,
        "tot_call_oi":     int(tot_call_oi),
        "tot_put_oi":      int(tot_put_oi),
        "anomalies":       anomalies[:5],
        "vol_spike":       vol_spike,
        "whale_flow_flag": whale_flow_flag,
        # ── R2-8: DBOI fields ────────────────────────────────────────────────
        "dboi_call_wall":  dboi_call_wall,
        "dboi_put_wall":   dboi_put_wall,
        "dboi_zero_line":  dboi_zero_line,
        "net_dboi_m":      net_dboi_m,
    }


# ─────────────────────────────────────────────────────────────────────────────
# R2-5: MULTI-EXPIRY GEX STACKING
# ─────────────────────────────────────────────────────────────────────────────
def _get_nearest_n_expiries(tk_obj, n: int = 4) -> list:
    """
    Return up to n upcoming expiry strings from the chain, covering:
    0DTE (today/tomorrow), this Friday, next Friday, monthly.
    """
    today    = datetime.date.today()
    # Next Friday and the Friday after
    days_to_fri = (4 - today.weekday()) % 7  # Friday = weekday 4
    if days_to_fri == 0:
        days_to_fri = 0  # today is Friday
    this_fri = today + datetime.timedelta(days=days_to_fri)
    next_fri = this_fri + datetime.timedelta(days=7)

    # Collect all upcoming expiries from chain
    upcoming = []
    for exp_str in tk_obj.options:
        try:
            exp_dt = datetime.date.fromisoformat(exp_str)
            if exp_dt >= today:
                upcoming.append((exp_dt, exp_str))
        except ValueError:
            continue
    upcoming.sort(key=lambda x: x[0])

    if not upcoming:
        return []

    # Build target set: 0DTE (≤1 day), this Fri, next Fri, nearest monthly (3rd Fri)
    selected = []
    seen_strs = set()

    def _add(exp_str):
        if exp_str and exp_str not in seen_strs:
            selected.append(exp_str)
            seen_strs.add(exp_str)

    # 1. 0DTE — nearest expiry that is today or tomorrow
    for dt, es in upcoming:
        if (dt - today).days <= 1:
            _add(es)
            break

    # 2. This Friday
    for dt, es in upcoming:
        if dt == this_fri:
            _add(es)
            break
    else:
        # Nearest expiry on or before this_fri
        cands = [(dt, es) for dt, es in upcoming if dt <= this_fri + datetime.timedelta(days=1)]
        if cands:
            _add(cands[-1][1])

    # 3. Next Friday
    for dt, es in upcoming:
        if dt == next_fri:
            _add(es)
            break
    else:
        cands = [(dt, es) for dt, es in upcoming
                 if this_fri < dt <= next_fri + datetime.timedelta(days=1)]
        if cands:
            _add(cands[-1][1])

    # 4. Nearest monthly (3rd Friday of a month at least 3 weeks out)
    def _is_third_friday(d: datetime.date) -> bool:
        return d.weekday() == 4 and 15 <= d.day <= 21

    for dt, es in upcoming:
        if _is_third_friday(dt) and (dt - today).days >= 14:
            _add(es)
            break

    # Pad with next available expiries if we still have fewer than n
    for dt, es in upcoming:
        if len(selected) >= n:
            break
        _add(es)

    return selected[:n]


def stack_gex_expiries(symbol: str, tk_obj=None, spot: float = None) -> dict:
    """
    R2-5: Multi-Expiry GEX Stacking.

    Calculates GEX for up to 4 expiries and returns:
      dominant_expiry  — expiry with highest total OI
      stacked_gex_zero — OI-weighted average of zero-crossings across expiries
      expiry_oi_weight — dict of {expiry_str: oi_weight_pct}
      expiry_breakdown  — list of per-expiry dicts with full GEX metrics

    Always returns a valid dict even on failure.
    """
    empty = {
        "dominant_expiry":  None,
        "stacked_gex_zero": None,
        "expiry_oi_weight": {},
        "expiry_breakdown": [],
    }
    try:
        import yfinance as yf
        tk = tk_obj or yf.Ticker(symbol)

        if spot is None:
            try:
                spot = float(tk.fast_info.last_price)
            except Exception:
                hist = tk.history(period="1d")
                spot = float(hist["Close"].iloc[-1]) if not hist.empty else None
        if not spot:
            return empty

        expiries = _get_nearest_n_expiries(tk, n=4)
        if not expiries:
            return empty

        lo = spot * (1 - STRIKE_RANGE)
        hi = spot * (1 + STRIKE_RANGE)

        breakdown   = []
        total_oi_all = 0.0
        now_dt       = datetime.datetime.now()

        for exp_str in expiries:
            try:
                exp_dt = datetime.datetime.strptime(exp_str, "%Y-%m-%d")
                T = max((exp_dt - now_dt).total_seconds() / (365.25 * 24 * 3600), 1 / 365)

                chain = tk.option_chain(exp_str)
                calls = chain.calls.fillna(0)
                puts  = chain.puts.fillna(0)

                calls = calls[(calls["strike"] >= lo) & (calls["strike"] <= hi)].copy()
                puts  = puts[ (puts["strike"]  >= lo) & (puts["strike"]  <= hi)].copy()

                call_oi = dict(zip(calls["strike"], calls["openInterest"]))
                put_oi  = dict(zip(puts["strike"],  puts["openInterest"]))
                call_iv = dict(zip(calls["strike"], calls["impliedVolatility"]))
                put_iv  = dict(zip(puts["strike"],  puts["impliedVolatility"]))

                all_strikes = sorted(set(call_oi.keys()) | set(put_oi.keys()))
                total_oi    = sum(call_oi.values()) + sum(put_oi.values())

                # Per-expiry GEX and zero-crossing
                gex_by_strike = {}
                for K in all_strikes:
                    iv_c = call_iv.get(K, 0.30) or 0.30
                    iv_p = put_iv.get(K, 0.30)  or 0.30
                    g_c  = bs_gamma(spot, K, T, RFR, iv_c)
                    g_p  = bs_gamma(spot, K, T, RFR, iv_p)
                    gex_by_strike[K] = (call_oi.get(K, 0) * g_c - put_oi.get(K, 0) * g_p) * 100 * spot

                # GEX zero crossing
                gex_zero = None
                sorted_strikes = sorted(gex_by_strike.keys())
                gex_vals       = [gex_by_strike[k] for k in sorted_strikes]
                for i in range(len(gex_vals) - 1):
                    if gex_vals[i] * gex_vals[i + 1] < 0:
                        denom = abs(gex_vals[i]) + abs(gex_vals[i + 1])
                        if denom > 0:
                            gex_zero = round(
                                sorted_strikes[i] + (sorted_strikes[i + 1] - sorted_strikes[i]) *
                                abs(gex_vals[i]) / denom, 2
                            )
                        break

                # Call/put walls
                call_wall = max(call_oi, key=call_oi.get) if call_oi else spot
                put_wall  = max(put_oi,  key=put_oi.get)  if put_oi  else spot

                net_gex_m = round(sum(gex_by_strike.values()) / 1_000_000, 2)

                breakdown.append({
                    "expiry":    exp_str,
                    "total_oi":  int(total_oi),
                    "net_gex_m": net_gex_m,
                    "gex_zero":  gex_zero,
                    "call_wall": call_wall,
                    "put_wall":  put_wall,
                })
                total_oi_all += total_oi
            except Exception as _ex:
                print(f"  [{symbol}] GEX stack error for {exp_str}: {_ex}")
                continue

        if not breakdown:
            return empty

        # OI weights
        oi_weights = {}
        for item in breakdown:
            w = round(item["total_oi"] / total_oi_all * 100, 1) if total_oi_all > 0 else 0.0
            oi_weights[item["expiry"]] = w

        # Dominant expiry = highest OI
        dominant = max(breakdown, key=lambda x: x["total_oi"])

        # Stacked GEX zero = OI-weighted average of all valid zero-crossings
        zero_sum  = 0.0
        oi_sum    = 0.0
        for item in breakdown:
            if item["gex_zero"] is not None:
                zero_sum += item["gex_zero"] * item["total_oi"]
                oi_sum   += item["total_oi"]
        stacked_gex_zero = round(zero_sum / oi_sum, 2) if oi_sum > 0 else None

        return {
            "dominant_expiry":  dominant["expiry"],
            "stacked_gex_zero": stacked_gex_zero,
            "expiry_oi_weight": oi_weights,
            "expiry_breakdown": breakdown,
        }
    except Exception as e:
        print(f"  [{symbol}] stack_gex_expiries error (non-fatal): {e}")
        return empty


def _format_expiry_stack_field(stack: dict) -> dict | None:
    """Format the GEX Expiry Stack Discord embed field."""
    weights = stack.get("expiry_oi_weight", {})
    if not weights:
        return None
    parts = []
    for exp, w in sorted(weights.items(), key=lambda x: -x[1]):
        # Shorten date: 2026-06-06 -> 6/6
        try:
            dt = datetime.date.fromisoformat(exp)
            label = f"{dt.month}/{dt.day}"
        except Exception:
            label = exp
        parts.append(f"`{label}`: **{w}%**")
    stack_line = " │ ".join(parts)

    dom  = stack.get("dominant_expiry", "?")
    szero = stack.get("stacked_gex_zero")
    try:
        dom_label = f"{datetime.date.fromisoformat(dom).month}/{datetime.date.fromisoformat(dom).day}"
    except Exception:
        dom_label = dom

    value = stack_line
    if szero:
        value += f"\nWeighted GEX Zero: `${szero:.2f}`  ·  Dominant: `{dom_label}`"

    return {
        "name":   "📊 GEX Expiry Stack",
        "value":  value,
        "inline": False,
    }


def nearest_weekly_expiry(tk_obj):
    """Nearest Friday-ish expiry (standard weekly)."""
    today = datetime.date.today()
    for exp_str in tk_obj.options:
        try:
            if datetime.date.fromisoformat(exp_str) >= today:
                return exp_str
        except ValueError:
            continue
    return tk_obj.options[0] if tk_obj.options else None


def nearest_daily_expiry(tk_obj):
    """Nearest 0-2 DTE expiry (for 0DTE sweep)."""
    today = datetime.date.today()
    cutoff = today + datetime.timedelta(days=2)
    for exp_str in tk_obj.options:
        try:
            exp_dt = datetime.date.fromisoformat(exp_str)
            if today <= exp_dt <= cutoff:
                return exp_str
        except ValueError:
            continue
    # Fall back to nearest available
    return nearest_weekly_expiry(tk_obj)


# ─────────────────────────────────────────────────────────────────────────────
# R2-6: PRE-MARKET SCANNER
# ─────────────────────────────────────────────────────────────────────────────
_PREMARKET_TICKERS = ["SPY", "QQQ", "IWM", "TSLA", "NVDA", "AAPL", "MSFT", "AMZN"]

def _get_prior_close_polygon(symbol: str) -> float | None:
    """Pull yesterday's close from Polygon grouped-daily endpoint."""
    try:
        env_path = r"H:\Trishula\Swarm_4_Integration\Swarm_4_SBM_FINAL INTEGRATION\Project-Swarm\trishula-market-data\.env"
        api_key = ""
        import os
        api_key = os.environ.get("POLYGON_API_KEY", "")
        if not api_key:
            from pathlib import Path
            p = Path(env_path)
            if p.exists():
                for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if line.startswith("POLYGON_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        if not api_key:
            return None
        today = datetime.date.today()
        # Get prior trading day
        prior = today - datetime.timedelta(days=1)
        while prior.weekday() >= 5 or prior in US_HOLIDAYS:
            prior -= datetime.timedelta(days=1)
        date_str = prior.strftime("%Y-%m-%d")
        url = f"https://api.polygon.io/v1/open-close/{symbol}/{date_str}?adjusted=true&apiKey={api_key}"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return float(r.json().get("close", 0)) or None
        return None
    except Exception:
        return None


def _get_premarket_price(symbol: str) -> float | None:
    """Get current pre-market / last price via yfinance fast_info."""
    try:
        tk = yf.Ticker(symbol)
        p = tk.fast_info.last_price
        if p and float(p) > 0:
            return float(p)
    except Exception:
        pass
    return None


def _get_vix_data() -> dict:
    """Pull ^VIX current level and prior close."""
    try:
        tk = yf.Ticker("^VIX")
        hist = tk.history(period="5d")
        if hist.empty:
            return {"level": None, "prior_close": None, "change": None}
        current = float(tk.fast_info.last_price or hist["Close"].iloc[-1])
        prior   = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current
        change  = round(current - prior, 2)
        return {"level": round(current, 2), "prior_close": round(prior, 2), "change": change}
    except Exception:
        return {"level": None, "prior_close": None, "change": None}


def _gap_fill_signal(gap_pct: float, spot: float, gex_zero: float | None) -> str:
    """
    Assess gap-fill probability using GEX zero line.
    If spot gapped up and GEX zero is below current spot → gravity pulls back → gap fill likely.
    If spot gapped down and GEX zero is above current spot → gravity pulls up → gap fill likely.
    """
    if gex_zero is None or abs(gap_pct) < 0.5:
        return "—"
    if gap_pct > 0:  # Gap up
        if gex_zero < spot:
            return f"⬇️ Gap-fill toward GEX zero `${gex_zero:.2f}` likely (GEX zero BELOW spot)"
        else:
            return f"⬆️ Gap holds — GEX zero `${gex_zero:.2f}` supports price above gap"
    else:  # Gap down
        if gex_zero > spot:
            return f"⬆️ Gap-fill toward GEX zero `${gex_zero:.2f}` likely (GEX zero ABOVE spot)"
        else:
            return f"⬇️ Gap extends — GEX zero `${gex_zero:.2f}` confirms downside bias"


def run_premarket_sweep(dry_run: bool = False) -> dict:
    """
    R2-6: Pre-Market Scanner Sweep.

    Runs at ~8:30 ET before market open.
    Detects overnight gaps, futures drift (via SPY/QQQ/IWM),
    VIX level, earnings catalysts, and gap-fill probability.

    Returns structured result dict. If dry_run=True, prints output
    and skips Discord posting.
    """
    now_str = datetime.datetime.now().strftime("%A %b %d %Y  %I:%M %p ET")
    print(f"\n{'='*60}")
    print(f" Q-MATRIX PRE-MARKET SCAN — {now_str}")
    print(f" dry_run={dry_run}")
    print(f"{'='*60}")

    # ── 1. VIX ─────────────────────────────────────────────────────────────────
    vix = _get_vix_data()
    if vix["level"]:
        vix_dir = "⬆️" if vix["change"] and vix["change"] > 0 else "⬇️"
        vix_str = f"`{vix['level']:.2f}` {vix_dir} `{vix['change']:+.2f}` from `{vix['prior_close']:.2f}`"
        print(f"  [VIX] {vix_str}")
    else:
        vix_str = "Unavailable"
        print("  [VIX] Unavailable")

    # ── 2. Futures drift (SPY/QQQ/IWM as proxies for /ES, /NQ, /RTY) ──────────
    futures_proxies = {"SPY": "/ES", "QQQ": "/NQ", "IWM": "/RTY"}
    futures_lines   = []
    for sym, fut_name in futures_proxies.items():
        try:
            prior = _get_prior_close_polygon(sym)
            cur   = _get_premarket_price(sym)
            if prior and cur:
                gap_pct = round((cur - prior) / prior * 100, 2)
                emoji   = "⬆️" if gap_pct > 0 else ("⬇️" if gap_pct < 0 else "↔️")
                futures_lines.append(
                    f"`{sym}` ({fut_name}): `${cur:.2f}` vs close `${prior:.2f}` → {emoji} `{gap_pct:+.2f}%`"
                )
                print(f"  [{sym}/{fut_name}] {gap_pct:+.2f}%  prior={prior:.2f}  cur={cur:.2f}")
        except Exception as _fx:
            futures_lines.append(f"`{sym}` ({fut_name}): data error")

    # ── 3. Overnight gap detection for all premarket tickers ───────────────────
    gap_results = []
    for symbol in _PREMARKET_TICKERS:
        try:
            prior = _get_prior_close_polygon(symbol)
            cur   = _get_premarket_price(symbol)
            if not prior or not cur:
                # fallback to yfinance history
                tk   = yf.Ticker(symbol)
                hist = tk.history(period="5d")
                if not hist.empty:
                    prior = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else float(hist["Close"].iloc[-1])
                    cur   = float(hist["Close"].iloc[-1])
            if prior and cur:
                gap_pct = round((cur - prior) / prior * 100, 2)
                gap_results.append({
                    "symbol":  symbol,
                    "prior":   prior,
                    "current": cur,
                    "gap_pct": gap_pct,
                })
                print(f"  [{symbol}] gap={gap_pct:+.2f}%  prior={prior:.2f}  cur={cur:.2f}")
        except Exception as _ge:
            print(f"  [{symbol}] gap detection error: {_ge}")

    # Sort by abs gap size
    gap_results.sort(key=lambda x: abs(x["gap_pct"]), reverse=True)

    # ── 4. Market regime determination (from SPY gap) ──────────────────────────
    spy_gap = next((g["gap_pct"] for g in gap_results if g["symbol"] == "SPY"), None)
    if spy_gap is None:
        regime = "UNKNOWN OPEN"
        regime_emoji = "❓"
    elif spy_gap >= 0.3:
        regime = "GAP UP OPEN"
        regime_emoji = "🟢"
    elif spy_gap <= -0.3:
        regime = "GAP DOWN OPEN"
        regime_emoji = "🔴"
    else:
        regime = "FLAT OPEN"
        regime_emoji = "⬜"
    if spy_gap is not None:
        print(f"  [REGIME] {regime_emoji} {regime} (SPY gap: {spy_gap:+.2f}%)")
    else:
        print(f"  [REGIME] {regime_emoji} {regime}")

    # ── 5. Earnings catalysts (within 3 days) ──────────────────────────────────
    earnings_alerts = []
    if _NEWS_FEED_AVAILABLE:
        for symbol in _PREMARKET_TICKERS:
            try:
                days = _days_to_earnings(symbol)
                flag = _earnings_flag(symbol)
                if days <= 3 and flag:
                    earnings_alerts.append({"symbol": symbol, "days": days, "flag": flag})
                    print(f"  [{symbol}] EARNINGS ALERT: {flag}")
            except Exception:
                pass

    # Also check for macro events today
    macro_today = []
    if _NEWS_FEED_AVAILABLE:
        try:
            today = datetime.date.today()
            all_macro = _macro_events(days_ahead=1)
            macro_today = [e for e in all_macro if e["date"] == today]
            for e in macro_today:
                print(f"  [MACRO TODAY] {e['event']} ({e['impact']})")
        except Exception:
            pass

    # ── 6. Gap-fill probability for top-3 gapped tickers ──────────────────────
    gap_fill_signals = []
    for gr in gap_results[:3]:
        sym = gr["symbol"]
        if abs(gr["gap_pct"]) >= 0.5:
            # Get GEX zero from stack
            try:
                tk_obj = yf.Ticker(sym)
                stack  = stack_gex_expiries(sym, tk_obj=tk_obj, spot=gr["current"])
                gz     = stack.get("stacked_gex_zero")
            except Exception:
                gz = None
            sig = _gap_fill_signal(gr["gap_pct"], gr["current"], gz)
            gap_fill_signals.append({"symbol": sym, "gap_pct": gr["gap_pct"],
                                      "current": gr["current"], "signal": sig, "gex_zero": gz})
            print(f"  [{sym}] gap-fill signal: {sig}")

    # ── Build output structure ─────────────────────────────────────────────────
    result = {
        "regime":          regime,
        "regime_emoji":    regime_emoji,
        "vix":             vix,
        "vix_str":         vix_str,
        "futures_lines":   futures_lines,
        "gap_results":     gap_results,
        "gap_top3":        gap_results[:3],
        "earnings_alerts": earnings_alerts,
        "macro_today":     macro_today,
        "gap_fill_signals": gap_fill_signals,
        "spy_gap":         spy_gap,
    }

    # ── Print dry-run summary ──────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print(f" PRE-MARKET SUMMARY — {regime_emoji} {regime}")
    print(f"{'─'*60}")
    print(f" VIX: {vix_str}")
    print(f" Futures Drift:")
    for fl in futures_lines:
        print(f"   {fl}")
    print(f" Top Gaps:")
    for gr in gap_results[:5]:
        emoji = "⬆️" if gr['gap_pct'] > 0 else "⬇️"
        print(f"   {gr['symbol']}: {emoji} {gr['gap_pct']:+.2f}%  (${gr['current']:.2f} vs ${gr['prior']:.2f})")
    print(f" Earnings Catalysts: {len(earnings_alerts)} firing")
    for ea in earnings_alerts:
        print(f"   {ea['symbol']}: {ea['flag']}")
    print(f" Macro Events Today: {len(macro_today)}")
    for me in macro_today:
        print(f"   {me['event']} [{me['impact']}]")
    print(f" Gap-Fill Signals:")
    for gf in gap_fill_signals:
        print(f"   {gf['symbol']} ({gf['gap_pct']:+.2f}%): {gf['signal']}")
    print(f"{'─'*60}\n")

    if dry_run:
        print("[DRY-RUN] Discord posting skipped.")
        return result

    # ── Build and post Discord embed ───────────────────────────────────────────
    embed_color = 0x00cc88 if regime == "GAP UP OPEN" else (0xff3344 if regime == "GAP DOWN OPEN" else 0xffbd15)

    # Top-3 gap field
    gap_top3_lines = []
    for gr in gap_results[:3]:
        emoji = "⬆️" if gr['gap_pct'] > 0 else ("⬇️" if gr['gap_pct'] < 0 else "↔️")
        gap_top3_lines.append(
            f"`{gr['symbol']}` {emoji} **{gr['gap_pct']:+.2f}%**  `${gr['current']:.2f}` vs `${gr['prior']:.2f}`"
        )

    # Earnings field
    earn_lines = [ea["flag"] + f" — `{ea['symbol']}`" for ea in earnings_alerts]
    if not earn_lines:
        earn_lines = ["No earnings within 3 days"]

    # Macro today field
    macro_lines = [f"🚨 `{me['date']}` {me['event']}" for me in macro_today]
    if not macro_lines:
        macro_lines = ["No major macro events today"]

    # Gap-fill probability field
    gf_lines = []
    for gf in gap_fill_signals:
        gf_lines.append(f"`{gf['symbol']}` ({gf['gap_pct']:+.2f}%): {gf['signal']}")
    if not gf_lines:
        gf_lines = ["No significant gaps (>0.5%)"]

    # Futures field
    fut_str = "\n".join(futures_lines) if futures_lines else "Data unavailable"

    embed = {
        "title": f"🌅 Q-MATRIX PRE-MARKET SCAN  ·  {now_str}",
        "description": f"## {regime_emoji} {regime}",
        "color": embed_color,
        "fields": [
            {"name": "📊 VIX Level",
             "value": vix_str, "inline": False},
            {"name": "📈 Futures Drift (SPY/QQQ/IWM)",
             "value": "\n".join(futures_lines) if futures_lines else "Data unavailable",
             "inline": False},
            {"name": "🔥 Top 3 Overnight Gaps",
             "value": "\n".join(gap_top3_lines) if gap_top3_lines else "No gap data",
             "inline": False},
            {"name": "⚠️ Earnings Catalysts (≤3 days)",
             "value": "\n".join(earn_lines),
             "inline": False},
            {"name": "🚨 Macro Events Today",
             "value": "\n".join(macro_lines),
             "inline": False},
            {"name": "🎯 Gap-Fill Probability",
             "value": "\n".join(gf_lines),
             "inline": False},
        ],
        "footer": {"text": "Q-Matrix Pre-Market  ·  Trishula QuantNode"},
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    try:
        resp = requests.post(
            WEBHOOK_MACRO,
            json={"embeds": [embed]},
            timeout=20,
        )
        if resp.status_code in (200, 204):
            print("[PREMARKET] ✓ Pre-market embed sent to #macro-pulse.")
        else:
            print(f"[PREMARKET] Discord error {resp.status_code}: {resp.text[:120]}")
    except Exception as _pe:
        print(f"[PREMARKET] Discord post error: {_pe}")

    return result


# ─────────────────────────────────────────────────────────────────────────────
# AUTO-BACKTEST: Monday 6 PM — score prior-week snapshots vs actual closes
# ─────────────────────────────────────────────────────────────────────────────
def run_backtest() -> None:
    """
    Queries DB1 for snapshots where actual_close IS NULL and expiry < today.
    Fetches actual close from yfinance, computes WIN/MISS vs max_pain (±1%),
    writes outcome back to DB1 via ORDS PATCH, and posts a summary to Discord.
    """
    import math
    today = datetime.date.today()
    now_str = datetime.datetime.now().strftime("%A %b %d %Y  %I:%M %p ET")
    print(f"\n{'='*60}")
    print(f" Q-MATRIX AUTO-BACKTEST — {now_str}")
    print(f"{'='*60}")

    # ── 1. Fetch unscored rows from DB1 via _db1_persistence ─────────────────
    try:
        from _db1_persistence import _ORDS_BASE as _BT_BASE, _ORDS_USER as _BT_USER, _get_pass as _bt_pass
        _bt_url = _BT_BASE + "/qmatrix_snapshots/?limit=500"
        resp = requests.get(_bt_url, auth=(_BT_USER, _bt_pass()), verify=False, timeout=20)
        rows = resp.json().get("items", []) if resp.status_code == 200 else []
    except Exception as e:
        print(f"[BACKTEST] DB1 fetch error: {e}")
        return

    # Filter: expiry has passed AND actual_close is still null
    pending = [
        r for r in rows
        if r.get("actual_close") is None
        and r.get("expiry")
        and datetime.date.fromisoformat(r["expiry"][:10]) < today
    ]

    print(f"[BACKTEST] Found {len(pending)} unscored expired snapshots.")
    if not pending:
        print("[BACKTEST] Nothing to score — all rows current. Exiting.")
        _post_backtest_discord(now_str, scored=[], skipped=0)
        return

    # ── 2. Score each row ──────────────────────────────────────────────────────
    scored = []
    skipped = 0
    for row in pending:
        symbol   = row.get("ticker", "") or row.get("symbol", "")  # DB1 uses 'ticker'
        expiry   = row.get("expiry", "")[:10]
        max_pain = row.get("max_pain")
        row_id   = row.get("id") or row.get("snapshot_id")
        if not symbol or not expiry or not max_pain or not row_id:
            skipped += 1
            continue
        try:
            tk       = yf.Ticker(symbol)
            hist     = tk.history(start=expiry, end=str(datetime.date.fromisoformat(expiry) + datetime.timedelta(days=3)))
            if hist.empty:
                skipped += 1
                continue
            # Use close on expiry day (first row)
            actual_close = round(float(hist["Close"].iloc[0]), 4)
            pct_from_mp  = abs(actual_close - float(max_pain)) / float(max_pain) * 100
            outcome      = "WIN" if pct_from_mp <= 1.0 else "MISS"
            print(f"  [{symbol}] expiry={expiry}  close=${actual_close:.2f}  max_pain=${float(max_pain):.2f}  {pct_from_mp:.2f}%  → {outcome}")

            # ── 3. UPDATE back to DB1 via SQL ────────────────────────────────────
            try:
                from _db1_persistence import _sql_exec as _bt_sql
                upd = (
                    f"UPDATE qmatrix_snapshots "
                    f"SET actual_close={actual_close}, outcome='{outcome}' "
                    f"WHERE id={row_id}"
                )
                ok = _bt_sql(upd)
                if ok:
                    _bt_sql("COMMIT")
                else:
                    print(f"  [{symbol}] DB1 UPDATE failed — continuing")
            except Exception as pe:
                print(f"  [{symbol}] DB1 UPDATE exception: {pe}")

            scored.append({
                "symbol": symbol, "expiry": expiry,
                "actual_close": actual_close, "max_pain": float(max_pain),
                "pct_from_mp": round(pct_from_mp, 2), "outcome": outcome
            })
        except Exception as ex:
            print(f"  [{symbol}] scoring error: {ex}")
            skipped += 1

    # ── 4. Summary ─────────────────────────────────────────────────────────────
    wins   = sum(1 for s in scored if s["outcome"] == "WIN")
    misses = sum(1 for s in scored if s["outcome"] == "MISS")
    acc    = round(wins / len(scored) * 100, 1) if scored else 0.0
    print(f"\n[BACKTEST] Complete — {wins}W / {misses}M  Accuracy: {acc}%  Skipped: {skipped}")
    _post_backtest_discord(now_str, scored=scored, skipped=skipped)


def _post_backtest_discord(now_str: str, scored: list, skipped: int) -> None:
    """Post backtest summary embed to Discord #qm-backtest channel."""
    wins   = sum(1 for s in scored if s["outcome"] == "WIN")
    misses = sum(1 for s in scored if s["outcome"] == "MISS")
    total  = len(scored)
    acc    = round(wins / total * 100, 1) if total else 0.0

    color = 0x00cc88 if acc >= 60 else (0xffbd15 if acc >= 40 else 0xff3344)

    # Build row table
    if scored:
        rows_lines = []
        for s in sorted(scored, key=lambda x: x["pct_from_mp"]):
            icon = "✅" if s["outcome"] == "WIN" else "❌"
            rows_lines.append(
                f"{icon} `{s['symbol']}` exp `{s['expiry']}`  close `${s['actual_close']:.2f}`  "
                f"MP `${s['max_pain']:.2f}`  Δ `{s['pct_from_mp']:.2f}%`"
            )
        detail_val = "\n".join(rows_lines[:15])  # Discord 1024-char field limit
        if len(rows_lines) > 15:
            detail_val += f"\n… +{len(rows_lines)-15} more"
    else:
        detail_val = "No expired snapshots to score this week."

    embed = {
        "title": f"📊 Q-MATRIX AUTO-BACKTEST  ·  {now_str}",
        "description": f"### Max-Pain Pin Accuracy — Week Ending {datetime.date.today().strftime('%b %d, %Y')}",
        "color": color,
        "fields": [
            {"name": "📈 Results",
             "value": f"**{wins}** WIN  /  **{misses}** MISS  /  **{skipped}** Skipped\n**Accuracy: {acc}%** (within ±1% of Max Pain at expiry)",
             "inline": False},
            {"name": "📋 Ticker Breakdown",
             "value": detail_val,
             "inline": False},
            {"name": "🤖 ML Pipeline",
             "value": f"Labels written to DB1. Training dataset growing → SageMaker AutoPilot threshold: **500 rows**.",
             "inline": False},
        ],
        "footer": {"text": "Q-Matrix Backtest Engine  ·  Trishula QuantNode"},
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    try:
        webhook = WEBHOOK_MACRO  # post to #macro-pulse or add a dedicated backtest webhook
        r = requests.post(webhook, json={"embeds": [embed]}, timeout=20)
        if r.status_code in (200, 204):
            print("[BACKTEST] ✓ Summary posted to Discord.")
        else:
            print(f"[BACKTEST] Discord error {r.status_code}: {r.text[:120]}")
    except Exception as e:
        print(f"[BACKTEST] Discord post error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Trishula Sovereign Options Scanner")
    parser.add_argument("--mode",  choices=["weekly", "daily", "both", "premarket", "backtest"], default="both",
                        help="Sweep mode (default: both)")
    parser.add_argument("--force", action="store_true",
                        help="Run even if today is not a trading day")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simulate run without posting to Discord (premarket mode only)")
    args = parser.parse_args()

    today = datetime.date.today()
    if not args.force and not is_trading_day(today) and args.mode != "premarket":
        print(f"[GUARD] {today.strftime('%A %b %d')} is not a trading day. Exiting. Use --force to override.")
        return

    print("=" * 60)
    print(" Q-MATRIX  v3.1  —  TRISHULA SOVEREIGN QUANT NODE")
    print(f" Mode    : {args.mode.upper()}")
    print(f" Dry-Run : {getattr(args, 'dry_run', False)}")
    print(f" Macro   : {'ENABLED' if _MACRO_AVAILABLE else 'DISABLED'}")
    print(f" Started : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    if args.mode == "premarket":
        run_premarket_sweep(dry_run=getattr(args, "dry_run", False))
        print("\n[DONE]")
        return

    if args.mode == "backtest":
        run_backtest()
        print("\n[DONE]")
        return

    if args.mode in ("weekly", "both"):
        run_sweep(TICKERS,        "WEEKLY", nearest_weekly_expiry)

    if args.mode in ("daily", "both"):
        run_sweep(DAILY_TICKERS,  "DAILY",  nearest_daily_expiry)

    print("\n[DONE]")

if __name__ == "__main__":
    main()
