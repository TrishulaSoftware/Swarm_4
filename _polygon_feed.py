#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=================================================================
POLYGON.IO REAL-TIME DATA FEED  (_polygon_feed.py)
=================================================================
Provides real-time market data via Polygon.io REST API.
Falls back gracefully to yfinance if:
  - POLYGON_API_KEY is missing
  - Rate limited (429)
  - Any other error

Functions:
    get_quote(ticker)                           -> dict {price, bid, ask, volume}
    get_ohlcv(ticker, timespan, limit)          -> pd.DataFrame
    get_options_chain(ticker, expiry)           -> pd.DataFrame
    get_grouped_daily(date_str=None)            -> dict {ticker: {Open,High,Low,Close,Volume}}
    get_all_ohlcv_batch(tickers, date_str=None) -> dict {ticker: {Open,High,Low,Close,Volume}}
=================================================================
"""

import os
import time
import datetime
import logging
from pathlib import Path
from typing import Optional

import requests
import pandas as pd

logger = logging.getLogger(__name__)

# ── Load API Key ──────────────────────────────────────────────────────────────
def _load_api_key() -> str:
    """Load POLYGON_API_KEY from env or .env file."""
    key = os.environ.get("POLYGON_API_KEY", "")
    if key:
        return key
    # Try .env file
    env_paths = [
        Path(r"H:\Trishula\Swarm_4_Integration\Swarm_4_SBM_FINAL INTEGRATION\Project-Swarm\trishula-market-data\.env"),
        Path(os.path.dirname(__file__)) / ".env",
        Path(os.path.dirname(__file__)) / ".." / ".env",
    ]
    for env_path in env_paths:
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if line.startswith("POLYGON_API_KEY="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val:
                        os.environ["POLYGON_API_KEY"] = val
                        return val
    return ""

POLYGON_API_KEY = _load_api_key()
POLYGON_BASE    = "https://api.polygon.io"
_RATE_LIMIT_HIT = False   # module-level rate-limit flag
_LAST_429_TIME  = 0.0     # timestamp of last 429

# ── Session with retry ────────────────────────────────────────────────────────
_session = requests.Session()
_session.headers.update({"User-Agent": "TrishulaQMatrix/3.0"})


def _polygon_get(endpoint: str, params: dict = None, timeout: int = 10) -> Optional[dict]:
    """
    Execute a Polygon REST GET request.
    Returns parsed JSON dict or None on any error.
    """
    global _RATE_LIMIT_HIT, _LAST_429_TIME
    if not POLYGON_API_KEY:
        return None
    # Back off if rate limited in last 60 seconds
    if _RATE_LIMIT_HIT and (time.time() - _LAST_429_TIME) < 60:
        return None

    url = f"{POLYGON_BASE}{endpoint}"
    p   = params.copy() if params else {}
    p["apiKey"] = POLYGON_API_KEY

    try:
        resp = _session.get(url, params=p, timeout=timeout)
        if resp.status_code == 429:
            _RATE_LIMIT_HIT = True
            _LAST_429_TIME  = time.time()
            logger.warning("[Polygon] Rate limited (429) — falling back to yfinance for 60s")
            return None
        if resp.status_code == 403:
            logger.warning("[Polygon] 403 Forbidden — check API key tier")
            return None
        if resp.status_code != 200:
            logger.debug(f"[Polygon] {resp.status_code} for {endpoint}")
            return None
        _RATE_LIMIT_HIT = False  # successful call resets flag
        return resp.json()
    except Exception as e:
        logger.debug(f"[Polygon] Request error: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# get_quote — real-time snapshot
# ─────────────────────────────────────────────────────────────────────────────
def get_quote(ticker: str) -> dict:
    """
    Return {price, bid, ask, volume, source} for a ticker.
    Falls back to yfinance if Polygon unavailable.
    """
    ticker = ticker.upper()

    # ── Try Polygon v2 snapshot ──
    data = _polygon_get(f"/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}")
    if data and data.get("status") == "OK":
        snap = data.get("ticker", {})
        day  = snap.get("day", {})
        last = snap.get("lastTrade", {})
        q    = snap.get("lastQuote", {})
        price = (
            last.get("p")
            or snap.get("prevDay", {}).get("c")
            or day.get("c")
        )
        if price:
            return {
                "price":  float(price),
                "bid":    float(q.get("p", price)),
                "ask":    float(q.get("P", price)),
                "volume": int(day.get("v", 0)),
                "source": "polygon",
                "ticker": ticker,
            }

    # ── Fallback: yfinance ──
    return _yf_quote(ticker)


def _yf_quote(ticker: str) -> dict:
    """yfinance fallback for get_quote."""
    try:
        import yfinance as yf
        tk = yf.Ticker(ticker)
        try:
            price = float(tk.fast_info.last_price)
        except Exception:
            hist  = tk.history(period="1d")
            price = float(hist["Close"].iloc[-1]) if not hist.empty else 0.0
        fi = tk.fast_info
        return {
            "price":  price,
            "bid":    getattr(fi, "bid", price),
            "ask":    getattr(fi, "ask", price),
            "volume": int(getattr(fi, "three_month_average_volume", 0) or 0),
            "source": "yfinance",
            "ticker": ticker,
        }
    except Exception as e:
        logger.error(f"[yfinance] Quote error for {ticker}: {e}")
        return {"price": 0.0, "bid": 0.0, "ask": 0.0, "volume": 0, "source": "error", "ticker": ticker}


# ─────────────────────────────────────────────────────────────────────────────
# get_ohlcv — historical minute bars
# ─────────────────────────────────────────────────────────────────────────────
def get_ohlcv(ticker: str, timespan: str = "minute", limit: int = 390) -> pd.DataFrame:
    """
    Return OHLCV DataFrame with columns: open, high, low, close, volume, timestamp.
    timespan: 'minute', 'hour', 'day', 'week', 'month'
    Falls back to yfinance if Polygon unavailable.
    """
    ticker = ticker.upper()

    # Date range
    today = datetime.date.today()
    from_d = (today - datetime.timedelta(days=5)).strftime("%Y-%m-%d")
    to_d   = today.strftime("%Y-%m-%d")

    # Multiplier map
    mult_map = {"minute": 1, "hour": 1, "day": 1, "week": 1, "month": 1}
    multiplier = mult_map.get(timespan, 1)

    data = _polygon_get(
        f"/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from_d}/{to_d}",
        params={"adjusted": "true", "sort": "asc", "limit": limit}
    )

    if data and data.get("status") in ("OK", "DELAYED") and data.get("results"):
        rows = []
        for bar in data["results"]:
            rows.append({
                "timestamp": pd.Timestamp(bar["t"], unit="ms", tz="UTC"),
                "open":      float(bar["o"]),
                "high":      float(bar["h"]),
                "low":       float(bar["l"]),
                "close":     float(bar["c"]),
                "volume":    int(bar["v"]),
            })
        df = pd.DataFrame(rows).set_index("timestamp")
        return df

    # ── Fallback: yfinance ──
    return _yf_ohlcv(ticker, timespan, limit)


def _yf_ohlcv(ticker: str, timespan: str, limit: int) -> pd.DataFrame:
    """yfinance fallback for get_ohlcv."""
    try:
        import yfinance as yf
        interval_map = {
            "minute": "1m",
            "hour":   "1h",
            "day":    "1d",
            "week":   "1wk",
            "month":  "1mo",
        }
        period_map = {
            "minute": "1d",
            "hour":   "5d",
            "day":    "60d",
            "week":   "1y",
            "month":  "5y",
        }
        interval = interval_map.get(timespan, "1d")
        period   = period_map.get(timespan, "60d")
        hist = yf.Ticker(ticker).history(period=period, interval=interval)
        if hist.empty:
            return pd.DataFrame()
        hist = hist.rename(columns={"Open": "open", "High": "high", "Low": "low",
                                    "Close": "close", "Volume": "volume"})
        return hist[["open", "high", "low", "close", "volume"]].tail(limit)
    except Exception as e:
        logger.error(f"[yfinance] OHLCV error for {ticker}: {e}")
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# get_options_chain — Polygon options (requires options tier)
# ─────────────────────────────────────────────────────────────────────────────
def get_options_chain(ticker: str, expiry: str) -> pd.DataFrame:
    """
    Return options chain DataFrame for ticker at expiry (YYYY-MM-DD).
    Requires Polygon Starter+ tier for options data.
    Falls back to yfinance on 403 or missing data.
    """
    ticker = ticker.upper()

    # Polygon v3 options snapshot
    data = _polygon_get(
        "/v3/snapshot/options/" + ticker,
        params={
            "expiration_date": expiry,
            "limit": 250,
        }
    )

    if data and data.get("status") == "OK" and data.get("results"):
        rows = []
        for r in data["results"]:
            det    = r.get("details", {})
            greeks = r.get("greeks", {})
            day    = r.get("day", {})
            rows.append({
                "contractSymbol":   det.get("ticker", ""),
                "strike":           float(det.get("strike_price", 0)),
                "expiry":           det.get("expiration_date", expiry),
                "type":             det.get("contract_type", ""),
                "lastPrice":        float(day.get("close", 0) or 0),
                "bid":              float(r.get("last_quote", {}).get("bid", 0) or 0),
                "ask":              float(r.get("last_quote", {}).get("ask", 0) or 0),
                "volume":           int(day.get("volume", 0) or 0),
                "openInterest":     int(r.get("open_interest", 0) or 0),
                "impliedVolatility":float(r.get("implied_volatility", 0) or 0),
                "delta":            float(greeks.get("delta", 0) or 0),
                "gamma":            float(greeks.get("gamma", 0) or 0),
                "theta":            float(greeks.get("theta", 0) or 0),
                "vega":             float(greeks.get("vega", 0) or 0),
            })
        if rows:
            return pd.DataFrame(rows)

    # ── Fallback: yfinance ──
    return _yf_options_chain(ticker, expiry)


def _yf_options_chain(ticker: str, expiry: str) -> pd.DataFrame:
    """yfinance fallback for get_options_chain."""
    try:
        import yfinance as yf
        tk    = yf.Ticker(ticker)
        chain = tk.option_chain(expiry)
        calls = chain.calls.copy()
        puts  = chain.puts.copy()
        calls["type"] = "call"
        puts["type"]  = "put"
        df = pd.concat([calls, puts], ignore_index=True)
        return df
    except Exception as e:
        logger.error(f"[yfinance] Options chain error for {ticker}/{expiry}: {e}")
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# get_grouped_daily — single call for ALL US stocks OHLCV
# ─────────────────────────────────────────────────────────────────────────────
def get_grouped_daily(date_str: str = None) -> dict:
    """
    Fetch Polygon grouped daily bars for the entire US stock market in ONE call.
    Returns dict: {TICKER: {Open, High, Low, Close, Volume}}
    Column names match yfinance capitalized convention.

    date_str: 'YYYY-MM-DD' — defaults to most recent trading day (yesterday if
              today is weekend, else today).
    """
    if date_str is None:
        today = datetime.date.today()
        # Roll back to last weekday
        d = today - datetime.timedelta(days=1)
        while d.weekday() >= 5:
            d -= datetime.timedelta(days=1)
        date_str = d.strftime("%Y-%m-%d")

    endpoint = f"/v2/aggs/grouped/locale/us/market/stocks/{date_str}"
    data = _polygon_get(endpoint, params={"adjusted": "true"})

    result = {}
    if data and data.get("resultsCount", 0) > 0 and data.get("results"):
        for bar in data["results"]:
            ticker = bar.get("T", "")
            if not ticker:
                continue
            result[ticker] = {
                "Open":   float(bar.get("o", 0)),
                "High":   float(bar.get("h", 0)),
                "Low":    float(bar.get("l", 0)),
                "Close":  float(bar.get("c", 0)),
                "Volume": int(bar.get("v", 0)),
            }
        logger.info(f"[Polygon] Grouped daily {date_str}: {len(result)} tickers loaded.")
    else:
        logger.warning(f"[Polygon] Grouped daily {date_str}: no results (market closed or API issue).")

    return result


# ─────────────────────────────────────────────────────────────────────────────
# get_all_ohlcv_batch — batch fetch OHLCV for a list of tickers
# ─────────────────────────────────────────────────────────────────────────────
_BATCH_CACHE: dict = {}      # module-level cache {date_str: grouped_daily_dict}
_BATCH_SLEEP  = 0.35         # seconds between yfinance fallback calls

def get_all_ohlcv_batch(tickers: list, date_str: str = None) -> dict:
    """
    Return OHLCV dict for each requested ticker using a single Polygon grouped
    daily call.  For any ticker missing from the Polygon response, falls back
    to an individual yfinance call (with 0.35 s sleep between each).

    Returns dict: {TICKER: {Open, High, Low, Close, Volume}}
    """
    global _BATCH_CACHE

    if date_str is None:
        today = datetime.date.today()
        d = today - datetime.timedelta(days=1)
        while d.weekday() >= 5:
            d -= datetime.timedelta(days=1)
        date_str = d.strftime("%Y-%m-%d")

    # Pull from module cache or fetch fresh
    if date_str not in _BATCH_CACHE:
        _BATCH_CACHE[date_str] = get_grouped_daily(date_str)
    grouped = _BATCH_CACHE[date_str]

    result = {}
    missing = []
    for t in tickers:
        t_up = t.upper()
        if t_up in grouped:
            result[t_up] = grouped[t_up]
        else:
            missing.append(t_up)

    # Fallback: individual yfinance calls for missing tickers
    if missing:
        logger.info(f"[Polygon] Batch: falling back to yfinance for {missing}")
        try:
            import yfinance as yf
        except ImportError:
            logger.error("[yfinance] not installed — missing tickers will be absent.")
            return result

        for t in missing:
            try:
                hist = yf.Ticker(t).history(period="2d")
                if not hist.empty:
                    row = hist.iloc[-1]
                    result[t] = {
                        "Open":   float(row.get("Open",  0)),
                        "High":   float(row.get("High",  0)),
                        "Low":    float(row.get("Low",   0)),
                        "Close":  float(row.get("Close", 0)),
                        "Volume": int(row.get("Volume", 0)),
                    }
                    logger.debug(f"[yfinance] {t}: Close={result[t]['Close']:.2f}")
            except Exception as e:
                logger.warning(f"[yfinance] {t} batch fallback error: {e}")
            time.sleep(_BATCH_SLEEP)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Module-level spot helper (used by scanner)
# ─────────────────────────────────────────────────────────────────────────────
def get_spot_price(ticker: str) -> float:
    """
    Return current spot price for ticker.
    Tries Polygon first, falls back to yfinance.
    """
    q = get_quote(ticker)
    return q.get("price", 0.0)


# ─────────────────────────────────────────────────────────────────────────────
# Status check
# ─────────────────────────────────────────────────────────────────────────────
def polygon_status() -> dict:
    """Return Polygon connectivity status dict."""
    has_key = bool(POLYGON_API_KEY)
    if not has_key:
        return {"available": False, "reason": "No POLYGON_API_KEY in env or .env"}
    # Light ping
    data = _polygon_get("/v1/marketstatus/now")
    if data:
        return {
            "available": True,
            "key_prefix": POLYGON_API_KEY[:8] + "...",
            "market_status": data.get("market", "unknown"),
            "rate_limited": _RATE_LIMIT_HIT,
        }
    return {
        "available": False,
        "key_prefix": POLYGON_API_KEY[:8] + "...",
        "reason": "API unreachable or key invalid",
        "rate_limited": _RATE_LIMIT_HIT,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Self-test
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    status = polygon_status()
    print(f"\n[Polygon Status] {status}")

    tickers = ["SPY", "TSLA", "AMZN"]
    for sym in tickers:
        print(f"\n── {sym} ──")
        q = get_quote(sym)
        print(f"  Quote  : ${q['price']:.2f}  bid=${q['bid']:.2f}  ask=${q['ask']:.2f}  vol={q['volume']:,}  source={q['source']}")

        ohlcv = get_ohlcv(sym, timespan="minute", limit=5)
        if not ohlcv.empty:
            print(f"  OHLCV  : {len(ohlcv)} bars  last_close=${ohlcv['close'].iloc[-1]:.2f}")
        else:
            print(f"  OHLCV  : empty DataFrame")

    # ── Test: Grouped Daily + Batch ──────────────────────────────────────────
    print("\n── Grouped Daily Test (2026-05-29) ──")
    grouped = get_grouped_daily("2026-05-29")
    for sym in ["SPY", "AAPL"]:
        bar = grouped.get(sym)
        if bar:
            print(f"  {sym}: Open={bar['Open']:.2f}  Close={bar['Close']:.2f}  Vol={bar['Volume']:,}")
        else:
            print(f"  {sym}: NOT in grouped daily response (market closed or ticker absent)")

    print("\n── Batch OHLCV Test ──")
    batch = get_all_ohlcv_batch(["SPY", "AAPL", "NVDA"], date_str="2026-05-29")
    for sym, bar in batch.items():
        print(f"  {sym}: Close=${bar['Close']:.2f}  Vol={bar['Volume']:,}")

    print("\n[DONE]")
