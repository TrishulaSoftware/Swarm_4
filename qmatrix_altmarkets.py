# -*- coding: utf-8 -*-
"""
Q-MATRIX ALT MARKETS  v1.0
===========================
Crypto · Forex · Futures dashboard panels.
Fires to dedicated Discord channels on the 3x daily schedule.
"""

import io, json, datetime, time, requests
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec

try:
    import yfinance as yf
except ImportError:
    raise SystemExit("[ERROR] yfinance not installed.")

# ── Theme ──────────────────────────────────────────────────────────────────────
DARK_BG  = "#0a0a12"
PANEL_BG = "#0f0f1a"
GREEN    = "#00cc88"
RED      = "#ff3344"
GOLD     = "#ffbd15"
CYAN     = "#00e5ff"
WHITE    = "#e2e8f0"
DIM      = "#64748b"
BORDER   = "#1e1e30"

# ── Asset lists ────────────────────────────────────────────────────────────────
CRYPTO_TICKERS = [
    ("BTC-USD",  "Bitcoin",  "BTC",  "#f7931a"),
    ("ETH-USD",  "Ethereum", "ETH",  "#627eea"),
    ("SOL-USD",  "Solana",   "SOL",  "#9945ff"),
    ("BNB-USD",  "BNB",      "BNB",  "#f3ba2f"),
    ("XRP-USD",  "XRP",      "XRP",  "#00aae4"),
    ("ADA-USD",  "Cardano",  "ADA",  "#3399ff"),
    ("DOGE-USD", "Dogecoin", "DOGE", "#c3a634"),
]

FOREX_PAIRS = [
    ("EURUSD=X", "EUR/USD", "Euro"),
    ("USDJPY=X", "USD/JPY", "Yen"),
    ("GBPUSD=X", "GBP/USD", "Cable"),
    ("USDCHF=X", "USD/CHF", "Swissy"),
    ("AUDUSD=X", "AUD/USD", "Aussie"),
    ("USDCAD=X", "USD/CAD", "Loonie"),
    ("NZDUSD=X", "NZD/USD", "Kiwi"),
]

FUTURES_CONTRACTS = [
    ("ES=F", "S&P 500 E-mini",    "ES",  CYAN),
    ("NQ=F", "Nasdaq 100 E-mini", "NQ",  "#aa66ff"),
    ("YM=F", "Dow Jones E-mini",  "YM",  "#ff8844"),
    ("ZN=F", "10Y Treasury Note", "ZN",  GOLD),
    ("CL=F", "Crude Oil (WTI)",   "CL",  "#cc4400"),
    ("GC=F", "Gold Futures",      "GC",  GOLD),
]

# ── Helpers ────────────────────────────────────────────────────────────────────
def _session_label():
    hr = datetime.datetime.now().hour
    if hr < 11:  return "🔔 Market Open"
    if hr < 14:  return "🕛 Midday"
    return "⚡ Power Hour"

def _ts():
    return datetime.datetime.now().strftime("%b %d %Y  %I:%M %p ET")

def _fig_buf(fig):
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, facecolor=DARK_BG, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf

def _ax_dark(ax, bg=PANEL_BG):
    ax.set_facecolor(bg)
    ax.tick_params(colors=WHITE, labelsize=7)
    ax.spines[:].set_color(BORDER)
    for spine in ax.spines.values():
        spine.set_linewidth(0.6)

def _post(webhook, caption, buf, fname):
    buf.seek(0)
    payload = {"content": caption}
    r = requests.post(webhook,
        data={"payload_json": json.dumps(payload)},
        files={"file": (fname, buf, "image/png")},
        timeout=30)
    return r.status_code in (200, 204)

def _fetch_price(ticker, period="30d", interval="1d"):
    try:
        df = yf.download(ticker, period=period, interval=interval,
                         progress=False, auto_adjust=True)
        if df.empty:
            return None
        # Flatten multi-level columns (yfinance >= 0.2 returns MultiIndex)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception:
        return None

def _last_price(df):
    if df is None or df.empty:
        return None
    try:
        c = df["Close"].dropna()
        return float(c.iloc[-1]) if len(c) else None
    except Exception:
        return None

def _pct_change(df, days=1):
    if df is None or df.empty:
        return None
    try:
        c = df["Close"].dropna()
        if len(c) < days + 1:
            return None
        return float((c.iloc[-1] - c.iloc[-(days+1)]) / c.iloc[-(days+1)] * 100)
    except Exception:
        return None

def _fmt_pct(v):
    if v is None: return "N/A"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.2f}%"

def _pct_color(v):
    if v is None: return WHITE
    return GREEN if v >= 0 else RED

# ── Crypto Fear & Greed ────────────────────────────────────────────────────────
def _fetch_fear_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=8)
        d = r.json()["data"][0]
        return int(d["value"]), d["value_classification"]
    except Exception:
        return None, "N/A"

# ── CoinGecko global ───────────────────────────────────────────────────────────
def _fetch_coingecko_global():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/global", timeout=10)
        d = r.json()["data"]
        btc_dom = d["market_cap_percentage"].get("btc", 0)
        eth_dom = d["market_cap_percentage"].get("eth", 0)
        total_mcap = d["total_market_cap"].get("usd", 0)
        return btc_dom, eth_dom, total_mcap
    except Exception:
        return None, None, None

# ── CRYPTO DASHBOARD ───────────────────────────────────────────────────────────
def build_crypto_dashboard():
    rows_data = []
    for ticker, name, sym, color in CRYPTO_TICKERS:
        df = _fetch_price(ticker, period="8d", interval="1d")
        price = _last_price(df)
        chg1d = _pct_change(df, 1)
        chg7d = _pct_change(df, 7)
        vol = float(df["Volume"].iloc[-1]) if df is not None and not df.empty else 0
        sparkline = list(df["Close"].dropna().tail(7)) if df is not None else []
        rows_data.append((sym, name, color, price, chg1d, chg7d, vol, sparkline))

    fg_val, fg_label = _fetch_fear_greed()
    btc_dom, eth_dom, total_mcap = _fetch_coingecko_global()

    fig = plt.figure(figsize=(16, 10), facecolor=DARK_BG)
    gs  = GridSpec(2, 1, figure=fig, height_ratios=[3.5, 1],
                   hspace=0.35, left=0.03, right=0.97, top=0.90, bottom=0.05)

    ax_table = fig.add_subplot(gs[0])
    ax_ctx   = fig.add_subplot(gs[1])

    _ax_dark(ax_table)
    ax_table.set_xlim(0, 1); ax_table.set_ylim(0, 1); ax_table.axis("off")
    ax_table.set_title("CRYPTO MARKET DASHBOARD", color=WHITE, fontsize=11,
                        fontweight="bold", pad=6)

    # Header
    cols_x = [0.01, 0.11, 0.28, 0.42, 0.55, 0.75]
    for cx, label in zip(cols_x, ["SYM", "NAME", "PRICE", "24H", "7D", "SPARKLINE"]):
        ax_table.text(cx, 0.97, label, color=DIM, fontsize=8, fontweight="bold", va="top")
    ax_table.axhline(0.94, color=BORDER, lw=0.8)

    row_h = 0.88 / len(rows_data)
    for ri, (sym, name, color, price, chg1d, chg7d, vol, spark) in enumerate(rows_data):
        y = 0.93 - ri * row_h
        c1 = _pct_color(chg1d); c7 = _pct_color(chg7d)
        price_str = f"${price:,.4f}" if price and price < 1 else (f"${price:,.2f}" if price else "N/A")

        ax_table.text(cols_x[0], y, sym,   color=color,  fontsize=9,  fontweight="bold", va="top")
        ax_table.text(cols_x[1], y, name,  color=WHITE,  fontsize=8,  va="top")
        ax_table.text(cols_x[2], y, price_str, color=WHITE, fontsize=9, fontweight="bold", va="top")
        ax_table.text(cols_x[3], y, _fmt_pct(chg1d), color=c1, fontsize=9, fontweight="bold", va="top")
        ax_table.text(cols_x[4], y, _fmt_pct(chg7d), color=c7, fontsize=8, va="top")

        # Sparkline
        if len(spark) >= 2:
            sp_ax = ax_table.inset_axes([cols_x[5], y - row_h * 0.7,
                                          0.22, row_h * 0.75])
            sp_ax.set_facecolor(PANEL_BG)
            sp_x = range(len(spark))
            sp_col = GREEN if spark[-1] >= spark[0] else RED
            sp_ax.plot(sp_x, spark, color=sp_col, lw=1.2)
            sp_ax.fill_between(sp_x, spark, min(spark), alpha=0.15, color=sp_col)
            sp_ax.axis("off")

        if ri % 2 == 0:
            ax_table.axhspan(y - row_h * 0.7, y + row_h * 0.05,
                             color="#fff", alpha=0.015)

    # Context bar
    _ax_dark(ax_ctx)
    ax_ctx.set_xlim(0, 1); ax_ctx.set_ylim(0, 1); ax_ctx.axis("off")

    fg_color = GREEN if fg_val and fg_val >= 50 else RED
    fg_txt   = f"Fear & Greed: {fg_val} — {fg_label}" if fg_val else "Fear & Greed: N/A"
    ax_ctx.text(0.01, 0.75, fg_txt, color=fg_color, fontsize=10, fontweight="bold", va="top")

    if btc_dom:
        ax_ctx.text(0.30, 0.75, f"BTC Dom: {btc_dom:.1f}%", color=GOLD,
                    fontsize=10, fontweight="bold", va="top")
        ax_ctx.text(0.50, 0.75, f"ETH Dom: {eth_dom:.1f}%", color="#627eea",
                    fontsize=10, fontweight="bold", va="top")
    if total_mcap:
        mcap_t = total_mcap / 1e12
        ax_ctx.text(0.70, 0.75, f"Total MCap: ${mcap_t:.2f}T", color=CYAN,
                    fontsize=10, fontweight="bold", va="top")

    fig.suptitle("Q-MATRIX  |  CRYPTO MARKETS", color=CYAN,
                 fontsize=13, fontweight="bold", y=0.97)
    fig.patch.set_facecolor(DARK_BG)
    return _fig_buf(fig)


# ── CRYPTO PRICE CHART (BTC + ETH) ─────────────────────────────────────────────
def build_crypto_price_chart():
    pairs = [("BTC-USD", "Bitcoin", "#f7931a"), ("ETH-USD", "Ethereum", "#627eea")]
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), facecolor=DARK_BG)
    fig.subplots_adjust(hspace=0.45, left=0.06, right=0.97, top=0.91, bottom=0.06)

    for ax, (ticker, name, color) in zip(axes, pairs):
        df = _fetch_price(ticker, period="30d", interval="1d")
        _ax_dark(ax)
        if df is None or df.empty:
            ax.text(0.5, 0.5, f"{name}: No data", color=DIM, ha="center", va="center",
                    transform=ax.transAxes)
            continue

        closes = df["Close"].dropna()
        vols   = df["Volume"].dropna()
        x = range(len(closes))

        ax.plot(x, closes, color=color, lw=1.8, zorder=3)
        ax.fill_between(x, closes, closes.min(), alpha=0.12, color=color)

        # Volume bars on secondary y
        ax2 = ax.twinx()
        ax2.set_facecolor(PANEL_BG)
        ax2.bar(x, vols, color=color, alpha=0.18, zorder=1)
        ax2.tick_params(colors=DIM, labelsize=6)
        ax2.spines[:].set_color(BORDER)
        ax2.set_ylabel("Volume", color=DIM, fontsize=6)

        # Key levels
        hi = float(closes.max()); lo = float(closes.min())
        last = float(closes.iloc[-1])
        ax.axhline(hi, color=RED,   lw=0.8, ls="--", alpha=0.6, label=f"High ${hi:,.0f}")
        ax.axhline(lo, color=GREEN, lw=0.8, ls="--", alpha=0.6, label=f"Low ${lo:,.0f}")
        ax.axhline(last, color=CYAN, lw=1.2, ls="-", alpha=0.9, label=f"Last ${last:,.2f}")

        ax.set_title(f"{name}  ({ticker})  —  30-Day Price Structure",
                     color=WHITE, fontsize=9, pad=4)
        ax.legend(fontsize=7, facecolor="#0d0d1a", edgecolor=BORDER,
                  labelcolor=WHITE, framealpha=0.9, loc="upper left")
        ax.set_ylabel("Price (USD)", color=DIM, fontsize=7)
        ax.set_xlabel("Sessions", color=DIM, fontsize=7)

    fig.suptitle("Q-MATRIX  |  BTC + ETH  —  Price Structure (30D)",
                 color=CYAN, fontsize=11, fontweight="bold", y=0.97)
    fig.patch.set_facecolor(DARK_BG)
    return _fig_buf(fig)


# ── FOREX DASHBOARD ────────────────────────────────────────────────────────────
def build_forex_dashboard():
    rows_data = []
    for ticker, label, nickname in FOREX_PAIRS:
        df = _fetch_price(ticker, period="8d", interval="1d")
        price = _last_price(df)
        chg1d = _pct_change(df, 1)
        chg5d = _pct_change(df, 5)
        spark = list(df["Close"].dropna().tail(5)) if df is not None else []
        rows_data.append((label, nickname, price, chg1d, chg5d, spark))

    fig = plt.figure(figsize=(14, 7), facecolor=DARK_BG)
    ax = fig.add_subplot(111)
    _ax_dark(ax)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.set_title("FOREX MAJORS  —  Currency Dashboard", color=WHITE,
                 fontsize=10, fontweight="bold", pad=6)

    cols_x = [0.01, 0.18, 0.35, 0.50, 0.64, 0.78]
    for cx, lbl in zip(cols_x, ["PAIR", "NICKNAME", "RATE", "1D", "5D", "TREND"]):
        ax.text(cx, 0.97, lbl, color=DIM, fontsize=8, fontweight="bold", va="top")
    ax.axhline(0.94, color=BORDER, lw=0.8)

    row_h = 0.86 / len(rows_data)
    for ri, (label, nickname, price, chg1d, chg5d, spark) in enumerate(rows_data):
        y = 0.93 - ri * row_h
        c1 = _pct_color(chg1d); c5 = _pct_color(chg5d)
        price_str = f"{price:.4f}" if price else "N/A"
        arrow = "▲" if chg1d and chg1d >= 0 else "▼"
        arr_c = GREEN if chg1d and chg1d >= 0 else RED

        ax.text(cols_x[0], y, label,    color=CYAN,  fontsize=9, fontweight="bold", va="top")
        ax.text(cols_x[1], y, nickname, color=WHITE, fontsize=8, va="top")
        ax.text(cols_x[2], y, price_str,color=WHITE, fontsize=9, fontweight="bold", va="top")
        ax.text(cols_x[3], y, f"{arrow} {_fmt_pct(chg1d)}", color=c1, fontsize=9,
                fontweight="bold", va="top")
        ax.text(cols_x[4], y, _fmt_pct(chg5d), color=c5, fontsize=8, va="top")

        if len(spark) >= 2:
            sp_ax = ax.inset_axes([cols_x[5], y - row_h * 0.7, 0.20, row_h * 0.75])
            sp_ax.set_facecolor(PANEL_BG)
            sp_col = GREEN if spark[-1] >= spark[0] else RED
            sp_ax.plot(range(len(spark)), spark, color=sp_col, lw=1.5)
            sp_ax.fill_between(range(len(spark)), spark, min(spark),
                               alpha=0.15, color=sp_col)
            sp_ax.axis("off")

        if ri % 2 == 0:
            ax.axhspan(y - row_h * 0.7, y + row_h * 0.05,
                       color="#fff", alpha=0.015)

    # DXY note
    try:
        dxy_df = _fetch_price("DX-Y.NYB", period="3d", interval="1d")
        dxy = _last_price(dxy_df)
        dxy_chg = _pct_change(dxy_df, 1)
        if dxy:
            dxy_str = f"DXY (Dollar Index): {dxy:.2f}  {_fmt_pct(dxy_chg)}"
            ax.text(0.01, 0.04, dxy_str, color=GOLD, fontsize=9,
                    fontweight="bold", va="bottom")
    except Exception:
        pass

    fig.suptitle("Q-MATRIX  |  FOREX MAJORS", color=GOLD,
                 fontsize=13, fontweight="bold", y=0.97)
    fig.patch.set_facecolor(DARK_BG)
    return _fig_buf(fig)


# ── FUTURES DASHBOARD ──────────────────────────────────────────────────────────
def build_futures_dashboard():
    rows_data = []
    for ticker, name, sym, color in FUTURES_CONTRACTS:
        df = _fetch_price(ticker, period="8d", interval="1d")
        price = _last_price(df)
        chg1d = _pct_change(df, 1)
        chg5d = _pct_change(df, 5)
        vol   = float(df["Volume"].iloc[-1]) if df is not None and not df.empty else 0
        spark = list(df["Close"].dropna().tail(5)) if df is not None else []
        rows_data.append((sym, name, color, price, chg1d, chg5d, vol, spark))

    fig = plt.figure(figsize=(16, 8), facecolor=DARK_BG)
    ax = fig.add_subplot(111)
    _ax_dark(ax)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.set_title("FUTURES MARKETS  —  High Volume Contracts", color=WHITE,
                 fontsize=10, fontweight="bold", pad=6)

    cols_x = [0.01, 0.08, 0.30, 0.47, 0.61, 0.74, 0.87]
    for cx, lbl in zip(cols_x, ["SYM", "CONTRACT", "PRICE", "1D", "5D", "VOLUME", "TREND"]):
        ax.text(cx, 0.97, lbl, color=DIM, fontsize=8, fontweight="bold", va="top")
    ax.axhline(0.94, color=BORDER, lw=0.8)

    row_h = 0.86 / len(rows_data)
    for ri, (sym, name, color, price, chg1d, chg5d, vol, spark) in enumerate(rows_data):
        y = 0.93 - ri * row_h
        c1 = _pct_color(chg1d); c5 = _pct_color(chg5d)
        price_str = f"{price:,.2f}" if price else "N/A"
        vol_str   = f"{vol/1e3:.0f}K" if vol >= 1000 else f"{vol:.0f}"
        arrow = "▲" if chg1d and chg1d >= 0 else "▼"
        arr_c = GREEN if chg1d and chg1d >= 0 else RED

        ax.text(cols_x[0], y, sym,      color=color, fontsize=9, fontweight="bold", va="top")
        ax.text(cols_x[1], y, name,     color=WHITE, fontsize=8, va="top")
        ax.text(cols_x[2], y, price_str,color=WHITE, fontsize=9, fontweight="bold", va="top")
        ax.text(cols_x[3], y, f"{arrow} {_fmt_pct(chg1d)}", color=arr_c,
                fontsize=9, fontweight="bold", va="top")
        ax.text(cols_x[4], y, _fmt_pct(chg5d), color=c5, fontsize=8, va="top")
        ax.text(cols_x[5], y, vol_str,  color=DIM,  fontsize=8, va="top")

        if len(spark) >= 2:
            sp_ax = ax.inset_axes([cols_x[6], y - row_h * 0.7, 0.12, row_h * 0.75])
            sp_ax.set_facecolor(PANEL_BG)
            sp_col = GREEN if spark[-1] >= spark[0] else RED
            sp_ax.plot(range(len(spark)), spark, color=sp_col, lw=1.5)
            sp_ax.fill_between(range(len(spark)), spark, min(spark),
                               alpha=0.15, color=sp_col)
            sp_ax.axis("off")

        if ri % 2 == 0:
            ax.axhspan(y - row_h * 0.7, y + row_h * 0.05,
                       color="#fff", alpha=0.015)

    fig.suptitle("Q-MATRIX  |  FUTURES MARKETS", color="#ff6622",
                 fontsize=13, fontweight="bold", y=0.97)
    fig.patch.set_facecolor(DARK_BG)
    return _fig_buf(fig)


# ── SWEEP RUNNERS ──────────────────────────────────────────────────────────────
def run_crypto_sweep(webhook_crypto: str):
    sweep = _session_label(); ts = _ts()
    print("[ALT] Running crypto sweep...")

    desc_dash = (
        "Live snapshot of all 7 major crypto assets. "
        "Price, 24H and 7D performance, sparklines, BTC dominance, and Crypto Fear & Greed index. "
        "Green = bullish momentum. Red = selling pressure. Fear & Greed below 25 = extreme fear (contrarian buy signal)."
    )
    buf = build_crypto_dashboard()
    _post(webhook_crypto,
          f"**CRYPTO MARKETS  —  Dashboard**  `{sweep}  ·  {ts}`\n{desc_dash}",
          buf, "crypto_dashboard.png")
    time.sleep(2)

    desc_price = (
        "30-day price structure for Bitcoin and Ethereum. "
        "Volume bars show where institutional activity concentrated. "
        "Gold dashed = 30D high. Green dashed = 30D low. Cyan = current price. "
        "A price holding above the 30D midpoint with rising volume = accumulation. Breakdown below = distribution."
    )
    buf2 = build_crypto_price_chart()
    _post(webhook_crypto,
          f"**CRYPTO  —  BTC + ETH Price Structure (30D)**  `{sweep}  ·  {ts}`\n{desc_price}",
          buf2, "crypto_price.png")

    print("[ALT] Crypto sweep done.")


def run_forex_sweep(webhook_forex: str):
    sweep = _session_label(); ts = _ts()
    print("[ALT] Running forex sweep...")

    desc = (
        "All 7 major USD currency pairs. Rate, 1-day and 5-day change, 5-session sparkline trend. "
        "DXY (Dollar Index) shown at bottom — DXY rising = USD strengthening (bearish for EUR/GBP/AUD). "
        "DXY falling = USD weakening (bullish for risk assets and commodities). "
        "Use trend arrows and sparklines to quickly identify which currencies are gaining vs losing ground."
    )
    buf = build_forex_dashboard()
    _post(webhook_forex,
          f"**FOREX MAJORS  —  Currency Dashboard**  `{sweep}  ·  {ts}`\n{desc}",
          buf, "forex_dashboard.png")

    print("[ALT] Forex sweep done.")


def run_futures_sweep(webhook_futures: str):
    sweep = _session_label(); ts = _ts()
    print("[ALT] Running futures sweep...")

    desc = (
        "High-volume futures contracts across equities, bonds, and commodities. "
        "ES (S&P) and NQ (Nasdaq) show index futures direction — often lead the equity open. "
        "ZN (10Y Treasury) inversely correlated to equities — ZN rising = risk-off. "
        "CL (Crude Oil) reflects energy demand and inflation expectations. "
        "GC (Gold) is the safe-haven read — rising gold + falling equities = institutional fear trade."
    )
    buf = build_futures_dashboard()
    _post(webhook_futures,
          f"**FUTURES MARKETS  —  High Volume Contracts**  `{sweep}  ·  {ts}`\n{desc}",
          buf, "futures_dashboard.png")

    print("[ALT] Futures sweep done.")


def run_altmarkets_sweep(webhook_crypto: str, webhook_forex: str, webhook_futures: str):
    """Master runner — call from sovereign_options_scanner.py."""
    run_crypto_sweep(webhook_crypto)
    time.sleep(3)
    run_forex_sweep(webhook_forex)
    time.sleep(3)
    run_futures_sweep(webhook_futures)
    print("[ALT] All alt markets swept.")


if __name__ == "__main__":
    # Standalone test — import webhooks from main scanner
    import sys
    sys.path.insert(0, r"H:\Trishula\Swarm_4_Integration\Salvo_Staging")
    from sovereign_options_scanner import WEBHOOK_CRYPTO, WEBHOOK_FOREX, WEBHOOK_FUTURES
    run_altmarkets_sweep(WEBHOOK_CRYPTO, WEBHOOK_FOREX, WEBHOOK_FUTURES)
