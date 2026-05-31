# -*- coding: utf-8 -*-
"""
Q-MATRIX MACRO CONTEXT ENGINE
==============================
Fetches session-level macro data and per-ticker fundamentals.
All sources are free / no-auth-required.

Data pulled:
  MACRO (once per sweep):
    - VIX term structure  : ^VIX, ^VIX3M, ^VIX6M  (yfinance)
    - Yield curve         : 13W, 2Y, 5Y, 10Y, 30Y  (yfinance)
    - Fear & Greed Index  : CNN dataviz endpoint    (requests)
    - CBOE total P/C      : CBOE daily JSON         (requests)

  PER-TICKER (appended to existing ticker data):
    - Earnings flag       : date + days until expiry  (yfinance)
    - Short interest      : SI%, days-to-cover        (yfinance info)
    - Insider activity    : last 30d buys vs sells     (yfinance)
    - WSB mentions        : Reddit search API          (requests, no auth)
"""

import io
import sys
import json
import datetime
import requests
import pandas as pd
import numpy as np
import matplotlib
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec

try:
    import yfinance as yf
except ImportError:
    raise SystemExit("[ERROR] yfinance not installed.")

# ── Palette (matches main scanner) ──────────────────────────────────────────
DARK_BG  = "#0a0a12"
PANEL_BG = "#0f0f1a"
GREEN    = "#00cc88"
RED      = "#ff3344"
GOLD     = "#ffbd15"
CYAN     = "#00e5ff"
WHITE    = "#e2e8f0"
DIM      = "#64748b"
BORDER   = "#1e1e30"
PURPLE   = "#aa44ff"
ORANGE   = "#ff8800"

def _ax_dark(ax):
    ax.set_facecolor(PANEL_BG)
    ax.tick_params(colors=DIM, labelsize=7)
    for sp in ax.spines.values():
        sp.set_color(BORDER)

# ─────────────────────────────────────────────────────────────────────────────
# MACRO DATA FETCHERS
# ─────────────────────────────────────────────────────────────────────────────

def fetch_vix_term_structure() -> dict:
    """Pull VIX, VIX3M, VIX6M from yfinance."""
    result = {}
    for label, sym in [("VIX", "^VIX"), ("VIX3M", "^VIX3M"), ("VIX6M", "^VIX6M")]:
        try:
            tk   = yf.Ticker(sym)
            hist = tk.history(period="5d")
            if not hist.empty:
                result[label] = round(float(hist["Close"].iloc[-1]), 2)
        except Exception:
            pass
    return result

def fetch_yield_curve() -> dict:
    """Pull US Treasury yields from yfinance."""
    tenors = {
        "13W": "^IRX",
        "2Y":  "^TYX",   # fallback: use 30Y then scale — but IRX/FVX/TNX work
        "5Y":  "^FVX",
        "10Y": "^TNX",
        "30Y": "^TYX",
    }
    # Correct symbols
    tenors = {
        "13W": "^IRX",
        "5Y":  "^FVX",
        "10Y": "^TNX",
        "30Y": "^TYX",
        "2Y":  "^IRX",   # placeholder; overridden below via Treasury scrape
    }
    result = {}
    for label, sym in tenors.items():
        if label == "2Y":
            continue
        try:
            hist = yf.Ticker(sym).history(period="5d")
            if not hist.empty:
                result[label] = round(float(hist["Close"].iloc[-1]) / 10, 3)
        except Exception:
            pass
    # 2Y: scrape Treasury XML (no auth needed)
    try:
        r2 = requests.get(
            "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
            "?data=daily_treasury_yield_curve&field_tdr_date_value_month="
            + datetime.date.today().strftime("%Y%m"),
            timeout=10, headers={"User-Agent": "Mozilla/5.0"}
        )
        import xml.etree.ElementTree as ET
        root = ET.fromstring(r2.text)
        ns   = {"m": "http://schemas.microsoft.com/ado/2007/08/dataservices"}
        entries = root.findall(".//m:BC_2YEAR", ns)
        if entries:
            result["2Y"] = round(float(entries[-1].text), 3)
    except Exception:
        pass
    return result

def fetch_fear_and_greed() -> dict:
    """Fetch CNN Fear & Greed Index (no auth)."""
    urls = [
        "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
        "https://fear-and-greed-index.p.rapidapi.com/v1/fgi",  # fallback stub
    ]
    try:
        resp = requests.get(
            urls[0], timeout=12,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://edition.cnn.com/markets/fear-and-greed",
            }
        )
        data   = resp.json()
        fg_now = data.get("fear_and_greed", data.get("fgi", {}))
        score  = fg_now.get("score", fg_now.get("now", {}).get("score", None))
        rating = fg_now.get("rating", fg_now.get("now", {}).get("valueText", "N/A"))
        if score is not None:
            return {"score": round(float(score), 1), "rating": str(rating).title()}
    except Exception:
        pass
    return {}

def fetch_cboe_pc_ratio() -> dict:
    """Fetch CBOE total & equity put/call ratio."""
    endpoints = [
        "https://cdn.cboe.com/api/global/us_options_flow/market_statistics/-/options-pcr.json",
        "https://www.cboe.com/data/us-market-statistics/",  # fallback
    ]
    try:
        resp = requests.get(
            endpoints[0], timeout=12,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept": "application/json",
                "Origin": "https://www.cboe.com",
                "Referer": "https://www.cboe.com/",
            }
        )
        data    = resp.json()
        records = data.get("data", [])
        if records:
            latest = records[-1]
            return {
                "total_pc":  round(float(latest.get("totalPCRatio",  latest.get("total",  0))), 2),
                "equity_pc": round(float(latest.get("equityPCRatio", latest.get("equity", 0))), 2),
                "index_pc":  round(float(latest.get("indexPCRatio",  latest.get("index",  0))), 2),
            }
    except Exception:
        pass
    return {}

def fetch_all_macro() -> dict:
    """Bundle all macro fetches."""
    print("  [MACRO] Fetching VIX term structure...")
    vix    = fetch_vix_term_structure()
    print("  [MACRO] Fetching yield curve...")
    yields = fetch_yield_curve()
    print("  [MACRO] Fetching Fear & Greed...")
    fng    = fetch_fear_and_greed()
    print("  [MACRO] Fetching CBOE P/C ratio...")
    cboe   = fetch_cboe_pc_ratio()
    return {"vix": vix, "yields": yields, "fear_greed": fng, "cboe_pc": cboe,
            "fetched_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M ET")}

# ─────────────────────────────────────────────────────────────────────────────
# PER-TICKER FUNDAMENTALS
# ─────────────────────────────────────────────────────────────────────────────

def fetch_ticker_fundamentals(symbol: str, expiry_str: str) -> dict:
    """Earnings flag, short interest, insider activity, WSB mentions."""
    out = {"symbol": symbol}
    tk  = yf.Ticker(symbol)

    # ── Earnings ──
    try:
        cal = tk.calendar
        if cal is not None and not cal.empty:
            # calendar is a DataFrame with index = metric name
            dates = cal.loc["Earnings Date"] if "Earnings Date" in cal.index else None
            if dates is not None:
                ed = dates.iloc[0] if hasattr(dates, "iloc") else dates
                ed = pd.Timestamp(ed).date() if not isinstance(ed, datetime.date) else ed
                exp_dt = datetime.date.fromisoformat(expiry_str)
                out["earnings_date"]    = str(ed)
                out["earnings_in_window"] = (ed <= exp_dt)
                out["earnings_dte"]     = (ed - datetime.date.today()).days
    except Exception:
        pass

    # ── Short Interest ──
    try:
        info = tk.info
        out["short_pct"]   = round(float(info.get("shortPercentOfFloat", 0) or 0) * 100, 2)
        out["short_ratio"] = round(float(info.get("shortRatio", 0) or 0), 1)
    except Exception:
        pass

    # ── Insider Activity (last 30d) ──
    try:
        ins = tk.insider_transactions
        if ins is not None and not ins.empty:
            import pandas as pd
            ins["Start Date"] = pd.to_datetime(ins["Start Date"], errors="coerce")
            cutoff = datetime.datetime.now() - datetime.timedelta(days=30)
            recent = ins[ins["Start Date"] >= cutoff]
            buys  = recent[recent["Transaction"].str.contains("Buy|Purchase", case=False, na=False)]
            sells = recent[recent["Transaction"].str.contains("Sale|Sell",    case=False, na=False)]
            out["insider_buys"]   = len(buys)
            out["insider_sells"]  = len(sells)
            out["insider_signal"] = "BUY" if len(buys) > len(sells) else "SELL" if len(sells) > len(buys) else "NEUTRAL"
    except Exception:
        pass

    # ── WSB Mentions (Reddit, no auth) ──
    try:
        url  = (f"https://www.reddit.com/r/wallstreetbets/search.json"
                f"?q={symbol}&sort=new&limit=50&t=day&restrict_sr=1")
        resp = requests.get(url, timeout=8,
                            headers={"User-Agent": "qmatrix-scanner/2.0"})
        data = resp.json()
        posts = data.get("data", {}).get("children", [])
        out["wsb_mentions"] = len(posts)
        # Crude sentiment: upvote ratio average
        if posts:
            ratios = [p["data"].get("upvote_ratio", 0.5) for p in posts]
            out["wsb_sentiment"] = round(sum(ratios) / len(ratios), 2)
    except Exception:
        out["wsb_mentions"] = 0

    return out

# ─────────────────────────────────────────────────────────────────────────────
# MACRO PANEL CHART
# ─────────────────────────────────────────────────────────────────────────────

def build_macro_panel(macro: dict) -> io.BytesIO:
    """4-panel macro context chart: VIX term | Yield curve | F&G gauge | CBOE P/C."""
    vix    = macro.get("vix", {})
    yields = macro.get("yields", {})
    fng    = macro.get("fear_greed", {})
    cboe   = macro.get("cboe_pc", {})

    fig = plt.figure(figsize=(18, 7), facecolor=DARK_BG)
    gs  = GridSpec(1, 4, figure=fig, wspace=0.30,
                   left=0.05, right=0.97, top=0.88, bottom=0.12)
    ax_vix  = fig.add_subplot(gs[0])
    ax_yld  = fig.add_subplot(gs[1])
    ax_fng  = fig.add_subplot(gs[2])
    ax_pc   = fig.add_subplot(gs[3])

    # ── VIX Term Structure ──
    if vix:
        labels = list(vix.keys())
        vals   = list(vix.values())
        colors = [GREEN if v < 20 else GOLD if v < 30 else RED for v in vals]
        bars   = ax_vix.bar(labels, vals, color=colors, alpha=0.88, width=0.5)
        for bar, val in zip(bars, vals):
            ax_vix.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                        f"{val:.1f}", color=WHITE, ha="center", fontsize=9, fontweight="bold")
        ax_vix.axhline(20, color=GREEN, ls="--", lw=0.8, alpha=0.6, label="Low Vol (20)")
        ax_vix.axhline(30, color=RED,   ls="--", lw=0.8, alpha=0.6, label="High Vol (30)")
        ax_vix.set_title("VIX TERM STRUCTURE", color=WHITE, fontsize=9, pad=5)
        ax_vix.legend(fontsize=6.5, facecolor="#0d0d1a", edgecolor=BORDER, labelcolor=WHITE)
    else:
        ax_vix.text(0.5, 0.5, "VIX unavailable", color=DIM, ha="center", transform=ax_vix.transAxes)
    _ax_dark(ax_vix)
    ax_vix.set_ylabel("Volatility Index", color=DIM, fontsize=7.5)

    # ── Yield Curve ──
    tenor_order = ["13W", "2Y", "5Y", "10Y", "30Y"]
    y_labels = [t for t in tenor_order if t in yields]
    y_vals   = [yields[t] for t in y_labels]
    if y_vals:
        spread_color = GREEN if (y_vals[-1] - y_vals[0]) > 0 else RED
        ax_yld.plot(y_labels, y_vals, color=GOLD, lw=2, marker="o", markersize=6)
        ax_yld.fill_between(range(len(y_labels)), y_vals,
                            min(y_vals), alpha=0.15, color=spread_color)
        for i, (lbl, val) in enumerate(zip(y_labels, y_vals)):
            ax_yld.text(i, val + 0.03, f"{val:.2f}%", color=WHITE,
                        ha="center", fontsize=7.5, fontweight="bold")
        # Inversion flag
        if len(y_vals) >= 2 and y_vals[0] > y_vals[-1]:
            ax_yld.set_title("YIELD CURVE  ⚠ INVERTED", color=RED, fontsize=9, pad=5)
        else:
            ax_yld.set_title("YIELD CURVE", color=WHITE, fontsize=9, pad=5)
        ax_yld.set_xticks(range(len(y_labels)))
        ax_yld.set_xticklabels(y_labels, color=WHITE, fontsize=8)
    else:
        ax_yld.text(0.5, 0.5, "Yields unavailable", color=DIM, ha="center", transform=ax_yld.transAxes)
    _ax_dark(ax_yld)
    ax_yld.set_ylabel("Yield (%)", color=DIM, fontsize=7.5)

    # ── Fear & Greed Gauge ──
    ax_fng.set_xlim(0, 1); ax_fng.set_ylim(0, 1); ax_fng.axis("off")
    ax_fng.set_facecolor(PANEL_BG)
    score  = fng.get("score", None)
    rating = fng.get("rating", "N/A")
    if score is not None:
        # Color by zone
        fg_color = (RED    if score < 25 else
                    ORANGE if score < 45 else
                    GOLD   if score < 55 else
                    GREEN  if score < 75 else
                    "#00ff88")
        ax_fng.text(0.5, 0.72, f"{score:.0f}", color=fg_color,
                    ha="center", va="center", fontsize=42, fontweight="bold")
        ax_fng.text(0.5, 0.45, rating.upper(), color=fg_color,
                    ha="center", va="center", fontsize=11, fontweight="bold")
        # Score bar
        ax_fng.add_patch(mpatches.FancyBboxPatch(
            (0.1, 0.25), 0.8, 0.08, boxstyle="round,pad=0.01",
            facecolor=BORDER, edgecolor=BORDER))
        ax_fng.add_patch(mpatches.FancyBboxPatch(
            (0.1, 0.25), 0.8 * score / 100, 0.08, boxstyle="round,pad=0.01",
            facecolor=fg_color, edgecolor="none", alpha=0.85))
        ax_fng.text(0.5, 0.15, "Extreme Fear ◄──────────► Extreme Greed",
                    color=DIM, ha="center", fontsize=6)
    else:
        ax_fng.text(0.5, 0.5, "F&G unavailable", color=DIM, ha="center")
    ax_fng.set_title("FEAR & GREED INDEX", color=WHITE, fontsize=9, pad=5)

    # ── CBOE P/C Ratio ──
    if cboe:
        pc_labels = ["Total P/C", "Equity P/C", "Index P/C"]
        pc_vals   = [cboe.get("total_pc", 0), cboe.get("equity_pc", 0), cboe.get("index_pc", 0)]
        pc_colors = [GREEN if v < 0.9 else GOLD if v < 1.1 else RED for v in pc_vals]
        bars2 = ax_pc.bar(pc_labels, pc_vals, color=pc_colors, alpha=0.88, width=0.5)
        for bar, val in zip(bars2, pc_vals):
            ax_pc.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                       f"{val:.2f}", color=WHITE, ha="center", fontsize=9, fontweight="bold")
        ax_pc.axhline(1.0, color=WHITE, ls="--", lw=0.8, alpha=0.5, label="Neutral (1.0)")
        ax_pc.set_title("CBOE PUT/CALL RATIO", color=WHITE, fontsize=9, pad=5)
        ax_pc.legend(fontsize=6.5, facecolor="#0d0d1a", edgecolor=BORDER, labelcolor=WHITE)
        ax_pc.set_xticklabels(pc_labels, color=WHITE, fontsize=7.5)
    else:
        ax_pc.text(0.5, 0.5, "CBOE P/C unavailable", color=DIM,
                   ha="center", transform=ax_pc.transAxes)
    _ax_dark(ax_pc)
    ax_pc.set_ylabel("P/C Ratio", color=DIM, fontsize=7.5)

    now_str = datetime.datetime.now().strftime("%A %b %d %Y  %I:%M %p ET")
    fig.suptitle(f"Q-MATRIX  |  MACRO PULSE  ·  {now_str}",
                 color=WHITE, fontsize=11, fontweight="bold", y=0.97)
    fig.patch.set_facecolor(DARK_BG)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=130, facecolor=DARK_BG, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf

# ─────────────────────────────────────────────────────────────────────────────
# MACRO EMBED (text summary fired alongside chart)
# ─────────────────────────────────────────────────────────────────────────────

def build_macro_embed(macro: dict) -> dict:
    vix    = macro.get("vix",        {})
    yields = macro.get("yields",     {})
    fng    = macro.get("fear_greed", {})
    cboe   = macro.get("cboe_pc",    {})

    # Yield curve inversion
    tenors = ["13W","2Y","5Y","10Y","30Y"]
    y_ordered = [(t, yields[t]) for t in tenors if t in yields]
    spread_2_10 = round(yields.get("10Y", 0) - yields.get("2Y", 0), 3) if "10Y" in yields and "2Y" in yields else None
    inversion   = "INVERTED" if spread_2_10 is not None and spread_2_10 < 0 else "Normal"

    # VIX regime
    vix_now = vix.get("VIX", None)
    vix_regime = ("LOW VOL" if vix_now and vix_now < 20 else
                  "ELEVATED" if vix_now and vix_now < 30 else
                  "HIGH VOL" if vix_now else "N/A")

    # F&G
    fg_score  = fng.get("score",  "N/A")
    fg_rating = fng.get("rating", "N/A")

    # CBOE
    tot_pc = cboe.get("total_pc",  "N/A")
    eq_pc  = cboe.get("equity_pc", "N/A")

    fields = [
        {"name": "VIX",     "value": f"`{vix.get('VIX','N/A')}` — {vix_regime}",              "inline": True},
        {"name": "VIX3M",   "value": f"`{vix.get('VIX3M','N/A')}`",                           "inline": True},
        {"name": "VIX6M",   "value": f"`{vix.get('VIX6M','N/A')}`",                           "inline": True},
        {"name": "10Y Yield","value": f"`{yields.get('10Y','N/A')}%`",                         "inline": True},
        {"name": "2/10 Spread","value": f"`{spread_2_10}%` — {inversion}" if spread_2_10 is not None else "`N/A`", "inline": True},
        {"name": "Fear & Greed","value": f"`{fg_score}` — {fg_rating}",                        "inline": True},
        {"name": "CBOE Total P/C", "value": f"`{tot_pc}`",                                     "inline": True},
        {"name": "CBOE Equity P/C","value": f"`{eq_pc}`",                                      "inline": True},
        {"name": "Fetched",  "value": f"`{macro.get('fetched_at','')}`",                       "inline": True},
    ]
    color = (0xff3344 if vix_now and vix_now > 30 else
             0xffbd15 if vix_now and vix_now > 20 else
             0x00cc88)
    return {
        "title": "Q-MATRIX  |  MACRO PULSE",
        "color": color,
        "fields": fields,
        "footer": {"text": "Q-Matrix  ·  Trishula QuantNode"},
        "timestamp": datetime.datetime.utcnow().replace(
            tzinfo=datetime.timezone.utc).isoformat(),
    }
