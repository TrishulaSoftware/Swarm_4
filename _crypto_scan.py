#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=================================================================
CRYPTO SCAN MODULE  (_crypto_scan.py)
=================================================================
Pulls crypto OHLCV + 24h change data from:
  1. Polygon.io  /v2/aggs/ticker/X:{TICKER}USD/prev  (free tier)
  2. CoinGecko   free API  (no key required)

Supported coins: BTC, ETH, SOL, DOGE, XRP, AVAX

Signal logic:
  change_24h > +3%  => BULLISH
  change_24h < -3%  => BEARISH
  else              => NEUTRAL

run_crypto_scan() returns list of {coin, price, change_24h_pct, vol_24h, signal}
Posts a dark-theme Discord embed with coin rows and colored indicators.
=================================================================
"""

import os
import time
import datetime
import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# ─────────────────────────────────────────────────────────────────────────────
# Load credentials from .env
# ─────────────────────────────────────────────────────────────────────────────
def _load_env():
    """Load POLYGON_API_KEY and Discord webhooks from .env file."""
    env_paths = [
        Path(r"H:\Trishula\Swarm_4_Integration\Swarm_4_SBM_FINAL INTEGRATION\Project-Swarm\trishula-market-data\.env"),
        Path(os.path.dirname(__file__)) / ".env",
        Path(os.path.dirname(__file__)) / ".." / ".env",
    ]
    result = {}
    for env_path in env_paths:
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    result[k.strip()] = v.strip().strip('"').strip("'")
            break  # use first .env found
    return result

_ENV = _load_env()

# Polygon key
POLYGON_API_KEY = _ENV.get("POLYGON_API_KEY", os.environ.get("POLYGON_API_KEY", ""))

# Discord webhook — prefer CRYPTO, then MACRO, then first available
def _pick_webhook(env: dict) -> str:
    for key in ("DISCORD_WEBHOOK_CRYPTO", "DISCORD_WEBHOOK_MACRO",
                "DISCORD_WEBHOOK_PICKS", "DISCORD_WEBHOOK_ALERTS"):
        v = env.get(key, "")
        if v and v.startswith("https://discord.com"):
            return v
    # Fallback: hardcoded from scanner constants
    return "https://discord.com/api/webhooks/1508274523948974190/fZ2p9DFKIrs3WZZvgujjjhooIeUaX5sEtYjpJKd6gWXNnV5E0XJhIQUAVPpS0GWzHTXb"

WEBHOOK_URL = _pick_webhook(_ENV)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
COINS = [
    {"symbol": "BTC",  "coingecko_id": "bitcoin",   "emoji": "₿"},
    {"symbol": "ETH",  "coingecko_id": "ethereum",  "emoji": "🔷"},
    {"symbol": "SOL",  "coingecko_id": "solana",    "emoji": "◎"},
    {"symbol": "DOGE", "coingecko_id": "dogecoin",  "emoji": "🐕"},
    {"symbol": "XRP",  "coingecko_id": "ripple",    "emoji": "✕"},
    {"symbol": "AVAX", "coingecko_id": "avalanche-2", "emoji": "🔺"},
]

SIGNAL_THRESHOLD = 3.0   # ±3% for BULLISH/BEARISH

# ─────────────────────────────────────────────────────────────────────────────
# Polygon crypto endpoint
# ─────────────────────────────────────────────────────────────────────────────
POLYGON_BASE = "https://api.polygon.io"
_session = requests.Session()
_session.headers.update({"User-Agent": "TrishulaQMatrix/3.0"})


def _polygon_crypto_prev(ticker: str) -> dict | None:
    """
    Fetch previous day aggregate for a crypto ticker via Polygon.
    ticker: 'BTC', 'ETH', etc. — will be formatted as X:{TICKER}USD
    Returns dict with keys: open, high, low, close, volume, change_pct
    """
    if not POLYGON_API_KEY:
        return None
    poly_ticker = f"X:{ticker.upper()}USD"
    url = f"{POLYGON_BASE}/v2/aggs/ticker/{poly_ticker}/prev"
    try:
        resp = _session.get(url, params={"apiKey": POLYGON_API_KEY}, timeout=10)
        if resp.status_code != 200:
            logger.debug(f"[Polygon Crypto] {poly_ticker}: HTTP {resp.status_code}")
            return None
        data = resp.json()
        results = data.get("results", [])
        if not results:
            return None
        bar = results[0]
        o = float(bar.get("o", 0))
        c = float(bar.get("c", 0))
        change_pct = round((c - o) / o * 100, 2) if o > 0 else 0.0
        return {
            "open":       o,
            "high":       float(bar.get("h", 0)),
            "low":        float(bar.get("l", 0)),
            "close":      c,
            "volume":     float(bar.get("v", 0)),
            "change_pct": change_pct,
            "source":     "polygon",
        }
    except Exception as e:
        logger.debug(f"[Polygon Crypto] {poly_ticker} error: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# CoinGecko free API  (no key)
# ─────────────────────────────────────────────────────────────────────────────
COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=bitcoin,ethereum,solana,dogecoin,ripple,avalanche-2"
    "&vs_currencies=usd"
    "&include_24hr_change=true"
    "&include_24hr_vol=true"
)


def _fetch_coingecko() -> dict:
    """
    Returns {coingecko_id: {usd, usd_24h_change, usd_24h_vol}}
    Falls back gracefully to {} on any error.
    """
    try:
        resp = requests.get(COINGECKO_URL, timeout=12,
                            headers={"User-Agent": "TrishulaQMatrix/3.0"})
        if resp.status_code == 200:
            return resp.json()
        logger.warning(f"[CoinGecko] HTTP {resp.status_code}")
    except Exception as e:
        logger.warning(f"[CoinGecko] Error: {e}")
    return {}


# ─────────────────────────────────────────────────────────────────────────────
# Signal logic
# ─────────────────────────────────────────────────────────────────────────────
def _signal(change_pct: float) -> str:
    if change_pct > SIGNAL_THRESHOLD:
        return "BULLISH"
    if change_pct < -SIGNAL_THRESHOLD:
        return "BEARISH"
    return "NEUTRAL"


def _signal_emoji(signal: str) -> str:
    return {"BULLISH": "🟢", "BEARISH": "🔴", "NEUTRAL": "🟡"}.get(signal, "⚪")


# ─────────────────────────────────────────────────────────────────────────────
# Main scan function
# ─────────────────────────────────────────────────────────────────────────────
def run_crypto_scan() -> list:
    """
    Pull data for all supported coins from Polygon (prev day) + CoinGecko.
    Returns list of dicts:
        {coin, price, change_24h_pct, vol_24h, signal, source}
    Also posts a Discord embed automatically.
    """
    cg_data = _fetch_coingecko()
    results = []

    for coin_info in COINS:
        sym          = coin_info["symbol"]
        cg_id        = coin_info["coingecko_id"]
        emoji        = coin_info["emoji"]

        price        = None
        change_24h   = None
        vol_24h      = None
        source       = "unknown"

        # 1. Try Polygon
        poly = _polygon_crypto_prev(sym)
        if poly:
            price      = poly["close"]
            change_24h = poly["change_pct"]
            vol_24h    = poly["volume"]
            source     = "polygon"

        # 2. Supplement / override with CoinGecko (more reliable for live price)
        cg = cg_data.get(cg_id, {})
        if cg:
            cg_price   = cg.get("usd")
            cg_change  = cg.get("usd_24h_change")
            cg_vol     = cg.get("usd_24h_vol")
            if cg_price:
                price  = float(cg_price)
                source = "coingecko"
            if cg_change is not None:
                change_24h = round(float(cg_change), 2)
            if cg_vol:
                vol_24h = float(cg_vol)

        if price is None:
            logger.warning(f"[CryptoScan] No data for {sym} — skipping.")
            continue

        sig = _signal(change_24h or 0.0)
        results.append({
            "coin":          sym,
            "emoji":         emoji,
            "price":         price,
            "change_24h_pct": change_24h or 0.0,
            "vol_24h":       vol_24h or 0.0,
            "signal":        sig,
            "source":        source,
        })
        logger.info(f"  {sym:5s}: ${price:>12,.4f}  {change_24h:+.2f}%  {sig}")

    # Post to Discord
    _post_discord(results)
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Discord embed builder
# ─────────────────────────────────────────────────────────────────────────────
def _post_discord(results: list):
    """Post a dark-theme embed with all coin rows to the crypto webhook."""
    if not results:
        return

    now_str = datetime.datetime.now().strftime("%b %d %Y  %I:%M %p ET")

    # Build field rows
    fields = []
    for r in results:
        sig_emoji = _signal_emoji(r["signal"])
        chg_sign  = "+" if r["change_24h_pct"] >= 0 else ""
        vol_str   = f"${r['vol_24h']/1e9:.2f}B" if r["vol_24h"] >= 1e9 else f"${r['vol_24h']/1e6:.1f}M"
        price_str = f"${r['price']:,.4f}" if r["price"] < 1.0 else f"${r['price']:,.2f}"

        fields.append({
            "name": f"{r['emoji']} {r['coin']}",
            "value": (
                f"**Price:** `{price_str}`\n"
                f"**24h:** `{chg_sign}{r['change_24h_pct']:.2f}%`  "
                f"**Vol:** `{vol_str}`\n"
                f"{sig_emoji} **{r['signal']}** · `{r['source']}`"
            ),
            "inline": True,
        })

    # Summary line
    bullish = sum(1 for r in results if r["signal"] == "BULLISH")
    bearish = sum(1 for r in results if r["signal"] == "BEARISH")
    neutral = sum(1 for r in results if r["signal"] == "NEUTRAL")

    embed = {
        "title": "🪙  TRISHULA CRYPTO SCAN",
        "description": (
            f"**{now_str}**\n"
            f"Market: 🟢 `{bullish}` Bullish  🔴 `{bearish}` Bearish  🟡 `{neutral}` Neutral\n"
            f"Threshold: ±{SIGNAL_THRESHOLD}% 24h change"
        ),
        "color": 0x9b59b6,   # Purple — dark crypto theme
        "fields": fields,
        "footer": {"text": "Trishula Sovereign  ·  Crypto Scan  ·  Polygon + CoinGecko"},
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    try:
        resp = requests.post(WEBHOOK_URL, json={"embeds": [embed]}, timeout=20)
        if resp.status_code in (200, 204):
            logger.info(f"[CryptoScan] Discord embed posted OK ({resp.status_code}).")
        else:
            logger.warning(f"[CryptoScan] Discord post failed: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        logger.error(f"[CryptoScan] Discord post error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Self-test
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 60)
    print("  TRISHULA CRYPTO SCAN — SELF TEST")
    print("=" * 60)
    print(f"  Polygon key : {'SET  (' + POLYGON_API_KEY[:8] + '...)' if POLYGON_API_KEY else 'NOT SET — using CoinGecko only'}")
    print(f"  Webhook     : {WEBHOOK_URL[:60]}...")
    print()

    data = run_crypto_scan()

    print(f"\n{'Coin':<6} {'Price':>14} {'24h%':>8} {'Vol':>14} {'Signal'}")
    print("-" * 60)
    for r in data:
        price_str = f"${r['price']:,.4f}" if r["price"] < 1.0 else f"${r['price']:,.2f}"
        vol_str   = f"${r['vol_24h']/1e9:.2f}B" if r["vol_24h"] >= 1e9 else f"${r['vol_24h']/1e6:.1f}M"
        print(f"{r['coin']:<6} {price_str:>14} {r['change_24h_pct']:>+8.2f}% {vol_str:>14}  {r['signal']}")

    print("\n[DONE] — Check Discord crypto channel.")
