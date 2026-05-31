#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=================================================================
STOCKTWITS SENTIMENT FEED  (_stocktwits_sentiment.py)
=================================================================
Primary: StockTwits free API (unauthenticated)
  https://api.stocktwits.com/api/2/streams/symbol/{TICKER}.json

Note: StockTwits API is now behind Cloudflare bot protection.
If blocked (403), falls back to yfinance news headline sentiment
scoring using keyword-based analysis (no external API key needed).

Functions:
    get_sentiment(ticker) -> dict {
        bullish_pct,   # 0-100
        bearish_pct,   # 0-100
        neutral_pct,   # 0-100
        message_volume,
        trending,      # bool
        score,         # -1.0 to +1.0
        source,        # 'stocktwits' | 'yfinance_news' | 'unavailable'
    }
=================================================================
"""

import time
import logging
import requests

logger = logging.getLogger(__name__)

_ST_BASE   = "https://api.stocktwits.com/api/2"
_CACHE: dict = {}       # {ticker: (timestamp, result)}
_CACHE_TTL = 300        # 5-minute cache per ticker

# ── Bullish/bearish keyword scoring for yfinance fallback ─────────────────────
_BULL_WORDS = {
    "surge", "surges", "surged", "rally", "rallies", "rallied", "beat", "beats",
    "bullish", "upgrade", "upgraded", "buy", "strong", "record", "breakout",
    "outperform", "exceed", "exceeds", "exceeded", "growth", "profit", "gain",
    "gains", "positive", "up", "rise", "rises", "rose", "higher", "high",
    "launch", "launched", "deal", "acquisition", "partnership", "revenue",
    "upside", "overweight", "momentum", "expansion", "boost", "jump", "jumps",
    "jumped", "soar", "soars", "soared",
}
_BEAR_WORDS = {
    "fall", "falls", "fell", "drop", "drops", "dropped", "decline", "declines",
    "declined", "miss", "misses", "missed", "bearish", "downgrade", "downgraded",
    "sell", "weak", "loss", "losses", "negative", "down", "lower", "low",
    "concern", "concerns", "risk", "risks", "lawsuit", "fine", "penalty",
    "recall", "warning", "cut", "cuts", "slump", "plunge", "plunges",
    "plunged", "crash", "crashes", "crashed", "layoff", "layoffs", "debt",
    "underperform", "underweight", "downside", "disappoint", "disappoints",
    "disappointed",
}


def _st_get(endpoint: str, timeout: int = 10) -> dict | None:
    """Hit a StockTwits endpoint, return JSON or None."""
    try:
        # Use a browser-like User-Agent to reduce bot detection
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://stocktwits.com/",
        }
        resp = requests.get(
            f"{_ST_BASE}{endpoint}",
            headers=headers,
            timeout=timeout,
        )
        if resp.status_code == 200:
            ct = resp.headers.get("Content-Type", "")
            if "json" in ct or resp.text.strip().startswith("{"):
                return resp.json()
        if resp.status_code == 429:
            logger.warning("[StockTwits] Rate limited (429)")
        elif resp.status_code == 403:
            logger.info("[StockTwits] 403 (Cloudflare bot protection) — using yfinance fallback")
        else:
            logger.debug(f"[StockTwits] {resp.status_code} for {endpoint}")
        return None
    except Exception as e:
        logger.debug(f"[StockTwits] Request error: {e}")
        return None


def _yf_news_sentiment(ticker: str) -> dict:
    """
    Fallback sentiment using yfinance news headline keyword scoring.
    No API key required.
    """
    EMPTY = {
        "bullish_pct":    0.0,
        "bearish_pct":    0.0,
        "neutral_pct":    100.0,
        "message_volume": 0,
        "trending":       False,
        "score":          0.0,
        "source":         "yfinance_news",
        "ticker":         ticker,
    }
    try:
        import yfinance as yf
        tk   = yf.Ticker(ticker)
        news = tk.news or []
        if not news:
            return {**EMPTY, "source": "no_news"}

        bull, bear, neutral = 0, 0, 0
        for item in news[:20]:
            # Try both old and new yfinance news formats
            title = (
                item.get("title", "")
                or item.get("content", {}).get("title", "")
                or ""
            )
            summary = (
                item.get("summary", "")
                or item.get("content", {}).get("summary", "")
                or ""
            )
            text = (title + " " + summary).lower()
            words = set(text.split())

            b_score = len(words & _BULL_WORDS)
            r_score = len(words & _BEAR_WORDS)

            if b_score > r_score:
                bull += 1
            elif r_score > b_score:
                bear += 1
            else:
                neutral += 1

        total = bull + bear + neutral
        if total == 0:
            return EMPTY

        bullish_pct = round(bull  / total * 100, 1)
        bearish_pct = round(bear  / total * 100, 1)
        neutral_pct = round(neutral / total * 100, 1)
        labeled = bull + bear
        score   = round((bull - bear) / labeled, 3) if labeled > 0 else 0.0

        return {
            "bullish_pct":    bullish_pct,
            "bearish_pct":    bearish_pct,
            "neutral_pct":    neutral_pct,
            "message_volume": len(news),
            "trending":       False,
            "score":          score,
            "source":         "yfinance_news",
            "ticker":         ticker,
        }
    except Exception as e:
        logger.debug(f"[yfinance_news] Error for {ticker}: {e}")
        return {
            "bullish_pct":    0.0,
            "bearish_pct":    0.0,
            "neutral_pct":    100.0,
            "message_volume": 0,
            "trending":       False,
            "score":          0.0,
            "source":         "error",
            "ticker":         ticker,
        }


def get_sentiment(ticker: str) -> dict:
    """
    Fetch StockTwits stream for ticker and compute sentiment.
    Falls back to yfinance news keyword scoring if StockTwits blocked.

    Returns:
        {
            'bullish_pct':    float (0-100),
            'bearish_pct':    float (0-100),
            'neutral_pct':    float (0-100),
            'message_volume': int,
            'trending':       bool,
            'score':          float (-1.0 to +1.0),
            'source':         'stocktwits' | 'yfinance_news' | 'unavailable',
            'ticker':         str,
        }
    """
    ticker = ticker.upper()

    # Cache check
    if ticker in _CACHE:
        ts, cached = _CACHE[ticker]
        if time.time() - ts < _CACHE_TTL:
            return cached

    result = _fetch_sentiment(ticker)
    _CACHE[ticker] = (time.time(), result)
    return result


def _fetch_sentiment(ticker: str) -> dict:
    """Internal: try StockTwits first, fall back to yfinance news."""
    # 1. Try StockTwits
    data = _st_get(f"/streams/symbol/{ticker}.json")
    if data:
        st_result = _parse_stocktwits(ticker, data)
        if st_result["source"] == "stocktwits":
            return st_result

    # 2. Fallback: yfinance news keyword sentiment
    return _yf_news_sentiment(ticker)


def _parse_stocktwits(ticker: str, data: dict) -> dict:
    """Parse a valid StockTwits API response."""
    EMPTY = {
        "bullish_pct":    0.0,
        "bearish_pct":    0.0,
        "neutral_pct":    100.0,
        "message_volume": 0,
        "trending":       False,
        "score":          0.0,
        "source":         "api_error",
        "ticker":         ticker,
    }

    if data.get("response", {}).get("status") != 200:
        return EMPTY

    messages = data.get("messages", [])
    if not messages:
        return {**EMPTY, "source": "no_messages"}

    bull_count    = 0
    bear_count    = 0
    neutral_count = 0

    for msg in messages:
        entities = msg.get("entities", {})
        sentiment_obj = entities.get("sentiment")
        if sentiment_obj is None:
            sentiment_obj = msg.get("sentiment")
        if not sentiment_obj:
            neutral_count += 1
            continue
        label = sentiment_obj.get("basic", "").lower()
        if label == "bullish":
            bull_count += 1
        elif label == "bearish":
            bear_count += 1
        else:
            neutral_count += 1

    total = bull_count + bear_count + neutral_count
    if total == 0:
        return {**EMPTY, "source": "parse_error"}

    bullish_pct = round(bull_count  / total * 100, 1)
    bearish_pct = round(bear_count  / total * 100, 1)
    neutral_pct = round(neutral_count / total * 100, 1)
    labeled = bull_count + bear_count
    score   = round((bull_count - bear_count) / labeled, 3) if labeled > 0 else 0.0

    symbol_data = data.get("symbol", {})
    trending    = bool(
        symbol_data.get("is_trending") or
        symbol_data.get("watchlist_count", 0) > 10000
    )

    return {
        "bullish_pct":    bullish_pct,
        "bearish_pct":    bearish_pct,
        "neutral_pct":    neutral_pct,
        "message_volume": len(messages),
        "trending":       trending,
        "score":          score,
        "source":         "stocktwits",
        "ticker":         ticker,
    }


def format_sentiment_field(ticker: str) -> dict | None:
    """
    Returns a Discord embed field dict for sentiment.
    Returns None if data unavailable.
    """
    s = get_sentiment(ticker)
    if s["source"] in ("error", "unavailable", "api_error", "no_news"):
        return None

    if s["score"] >= 0.25:
        mood_emoji = "\U0001f7e2"  # green circle
        mood_label = "Bullish"
    elif s["score"] <= -0.25:
        mood_emoji = "\U0001f53b"  # red triangle
        mood_label = "Bearish"
    else:
        mood_emoji = "\u2194"      # double arrow
        mood_label = "Mixed"

    source_label = "ST" if s["source"] == "stocktwits" else "News"
    trending_tag = " TRENDING" if s["trending"] else ""
    value = (
        f"{mood_emoji} `{mood_label}` [{source_label}] "
        f"Bull `{s['bullish_pct']}%` Bear `{s['bearish_pct']}%` "
        f"`{s['message_volume']} msgs`{trending_tag}"
    )
    return {
        "name":   "Sentiment",
        "value":  value,
        "inline": True,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Self-test
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    tickers = ["TSLA", "AMZN", "SPY"]
    for sym in tickers:
        print(f"\n-- {sym} --")
        s = get_sentiment(sym)
        print(f"  Bull: {s['bullish_pct']}%  Bear: {s['bearish_pct']}%  Neutral: {s['neutral_pct']}%")
        print(f"  Score: {s['score']:+.3f}  Volume: {s['message_volume']} msgs  Trending: {s['trending']}")
        print(f"  Source: {s['source']}")
        field = format_sentiment_field(sym)
        if field:
            print(f"  Discord field: {field['value']}")

    print("\n[DONE]")
