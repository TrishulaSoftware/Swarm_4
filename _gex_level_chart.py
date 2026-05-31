#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=================================================================
GEX LEVEL CHART — Per-Ticker Discord Embed Attachment
=================================================================
Generates a compact dark-theme matplotlib chart showing:
  - Last 5 days of price bars (OHLC mini bars)
  - Spot price (cyan horizontal line)
  - Max Pain level (dashed gold)
  - GEX Zero line (green = positive, red = negative side)
  - Whale POC (purple dotted)
  - Call Wall (green dash-dot)
  - Put Wall (red dash-dot)

Returns: io.BytesIO PNG buffer (ready to attach to Discord)

Background: #0d1117  (GitHub dark)
=================================================================
"""
import io
import datetime
import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec

try:
    import yfinance as yf
except ImportError:
    yf = None

# ── Theme ──────────────────────────────────────────────────────
BG         = "#0d1117"
PANEL_BG   = "#161b22"
BORDER     = "#30363d"
CYAN       = "#58a6ff"
GOLD       = "#f0c040"
GREEN      = "#3fb950"
RED        = "#f85149"
PURPLE     = "#a371f7"
WHITE      = "#e6edf3"
DIM        = "#8b949e"


def _fetch_price_bars(symbol: str, days: int = 6) -> list:
    """
    Fetch last `days` trading sessions as list of (date, open, high, low, close).
    Returns empty list on failure.
    """
    if yf is None:
        return []
    try:
        tk   = yf.Ticker(symbol)
        hist = tk.history(period=f"{days + 3}d")
        if hist.empty:
            return []
        hist = hist.tail(days)
        bars = []
        for idx, row in hist.iterrows():
            bars.append((
                idx.strftime("%m/%d"),
                float(row["Open"]),
                float(row["High"]),
                float(row["Low"]),
                float(row["Close"]),
            ))
        return bars
    except Exception:
        return []


def build_gex_level_chart(
    symbol: str,
    spot: float,
    max_pain: float,
    net_gex_m: float,
    gex_zero: float | None,
    whale_poc: float | None,
    call_wall: float | None,
    put_wall: float | None,
    expiry: str = "",
) -> io.BytesIO:
    """
    Build and return a dark-theme GEX levels chart as a PNG BytesIO buffer.

    Parameters
    ----------
    symbol     : ticker symbol (e.g. "AMZN")
    spot       : current spot price
    max_pain   : max pain strike
    net_gex_m  : net GEX in $M (positive = long gamma, negative = short gamma)
    gex_zero   : price level where aggregate GEX crosses zero (or None)
    whale_poc  : Whale volume profile Point of Control price (or None)
    call_wall  : top call OI strike (or None)
    put_wall   : top put OI strike (or None)
    expiry     : expiry date string for title label

    Returns
    -------
    io.BytesIO  PNG image buffer seeked to position 0
    """

    bars = _fetch_price_bars(symbol, days=5)

    # ── Figure layout: left=price chart, right=level panel ──
    fig = plt.figure(figsize=(12, 4.8), facecolor=BG)
    if bars:
        gs = GridSpec(1, 2, figure=fig, width_ratios=[1, 1.6],
                      wspace=0.06, left=0.04, right=0.97,
                      top=0.83, bottom=0.14)
        ax_price = fig.add_subplot(gs[0])
        ax_lvl   = fig.add_subplot(gs[1])
    else:
        gs = GridSpec(1, 1, figure=fig, left=0.06, right=0.97,
                      top=0.83, bottom=0.14)
        ax_price = None
        ax_lvl   = fig.add_subplot(gs[0])

    # ── LEFT: Price mini bars (last 5 days) ──
    if ax_price and bars:
        ax_price.set_facecolor(PANEL_BG)
        ax_price.tick_params(colors=DIM, labelsize=6.5)
        for sp in ax_price.spines.values():
            sp.set_color(BORDER)

        xs      = np.arange(len(bars))
        bar_w   = 0.32
        closes  = [b[4] for b in bars]
        opens   = [b[1] for b in bars]

        for i, (date_lbl, o, h, l, c) in enumerate(bars):
            color = GREEN if c >= o else RED
            # Candle body
            body_bot = min(o, c)
            body_top = max(o, c)
            ax_price.bar(i, body_top - body_bot, bar_w,
                         bottom=body_bot, color=color, alpha=0.88, zorder=3)
            # Wick
            ax_price.plot([i, i], [l, h], color=color, lw=0.9, alpha=0.7, zorder=2)

        # Key levels on price chart
        all_prices = [b[2] for b in bars] + [b[3] for b in bars]
        y_min = min(all_prices) * 0.997
        y_max = max(all_prices) * 1.003

        def _hline_price(ax, price, color, ls, lw, label=None):
            if y_min <= price <= y_max:
                ax.axhline(price, color=color, ls=ls, lw=lw, alpha=0.85, zorder=4)
                if label:
                    ax.text(len(bars) - 0.45, price, f" {label}",
                            color=color, fontsize=5.5, va="center", zorder=5)

        _hline_price(ax_price, spot,     CYAN,  "-",  1.5, f"${spot:.2f}")
        _hline_price(ax_price, max_pain, GOLD,  "--", 1.2, f"MP ${max_pain:.0f}")
        if gex_zero:
            gc = GREEN if net_gex_m >= 0 else RED
            _hline_price(ax_price, gex_zero, gc, ":", 1.0, f"GEX0 ${gex_zero:.0f}")
        if whale_poc:
            _hline_price(ax_price, whale_poc, PURPLE, ":", 1.0, f"POC ${whale_poc:.0f}")
        if call_wall:
            _hline_price(ax_price, call_wall, GREEN, "-.", 0.8, f"CW ${call_wall:.0f}")
        if put_wall:
            _hline_price(ax_price, put_wall,  RED,   "-.", 0.8, f"PW ${put_wall:.0f}")

        ax_price.set_ylim(y_min, y_max)
        ax_price.set_xticks(xs)
        ax_price.set_xticklabels([b[0] for b in bars], fontsize=6, color=DIM)
        ax_price.set_ylabel("Price ($)", color=DIM, fontsize=7)
        ax_price.set_title("Last 5 Sessions", color=DIM, fontsize=7.5, pad=4)
        ax_price.yaxis.set_major_formatter(plt.FormatStrFormatter("%.0f"))
        ax_price.tick_params(axis="y", labelsize=6, colors=DIM)

    # ── RIGHT: GEX level ladder ──
    ax_lvl.set_facecolor(PANEL_BG)
    ax_lvl.set_xlim(0, 1)
    ax_lvl.set_ylim(0, 1)
    ax_lvl.axis("off")
    ax_lvl.set_title("KEY LEVELS", color=DIM, fontsize=8, pad=4)

    # Collect all levels in price-sorted order for the ladder
    level_defs = [
        (spot,     CYAN,   "-",  f"SPOT          ${spot:.2f}",         "always"),
        (max_pain, GOLD,   "--", f"MAX PAIN      ${max_pain:.0f}",      "always"),
    ]
    if gex_zero is not None:
        gc = GREEN if net_gex_m >= 0 else RED
        lbl = "GEX ZERO (+γ)" if net_gex_m >= 0 else "GEX ZERO (-γ)"
        level_defs.append((gex_zero, gc, ":", f"{lbl}  ${gex_zero:.0f}", "optional"))
    if whale_poc is not None:
        level_defs.append((whale_poc, PURPLE, ":", f"WHALE POC     ${whale_poc:.0f}", "optional"))
    if call_wall is not None:
        level_defs.append((call_wall, GREEN, "-.", f"CALL WALL     ${call_wall:.0f}", "optional"))
    if put_wall is not None:
        level_defs.append((put_wall,  RED,   "-.", f"PUT WALL      ${put_wall:.0f}", "optional"))

    # Sort by price descending for ladder display
    level_defs.sort(key=lambda x: x[0], reverse=True)

    row_h   = 0.88 / max(len(level_defs), 1)
    pad_top = 0.93

    for ri, (price, color, ls, label_str, _) in enumerate(level_defs):
        yp = pad_top - ri * row_h

        # Color badge on left
        ax_lvl.add_patch(mpatches.FancyBboxPatch(
            (0.01, yp - row_h * 0.55), 0.03, row_h * 0.72,
            boxstyle="round,pad=0.005", facecolor=color, edgecolor="none", alpha=0.90
        ))

        # Distance from spot
        dist_pct = (price - spot) / spot * 100 if spot else 0
        sign     = "+" if dist_pct >= 0 else ""
        dist_str = f"{sign}{dist_pct:.2f}%"
        dist_col = GREEN if dist_pct >= 0 else RED

        ax_lvl.text(0.06, yp, label_str,
                    color=color, fontsize=8.0, fontweight="bold",
                    va="center", fontfamily="monospace")
        ax_lvl.text(0.82, yp, dist_str,
                    color=dist_col, fontsize=7.5, va="center", ha="right",
                    fontfamily="monospace")

        # Separator line
        if ri < len(level_defs) - 1:
            ax_lvl.axhline(yp - row_h * 0.55, color=BORDER, lw=0.5, alpha=0.5)

    # ── GEX net badge ──
    gex_sign  = "+" if net_gex_m >= 0 else ""
    gex_color = GREEN if net_gex_m >= 0 else RED
    gex_label = "LONG GAMMA" if net_gex_m >= 0 else "SHORT GAMMA"
    ax_lvl.text(0.99, 0.03,
                f"NET GEX  {gex_sign}{net_gex_m:.2f}M  ({gex_label})",
                color=gex_color, fontsize=7.5, ha="right", va="bottom",
                fontweight="bold", fontfamily="monospace")

    # ── Main title ──
    exp_str = f" · Exp: {expiry}" if expiry else ""
    gex_mode = "🟢 POSITIVE GEX" if net_gex_m >= 0 else "🔴 NEGATIVE GEX"
    fig.suptitle(
        f"Q-MATRIX  |  {symbol}  —  GEX Level Map{exp_str}  |  {gex_mode}",
        color=WHITE, fontsize=10, fontweight="bold", y=0.97
    )

    # ── Legend ──
    legend_items = [
        mpatches.Patch(color=CYAN,   label="Spot"),
        mpatches.Patch(color=GOLD,   label="Max Pain"),
        mpatches.Patch(color=GREEN,  label="GEX Zero (+) / Call Wall"),
        mpatches.Patch(color=RED,    label="GEX Zero (-) / Put Wall"),
        mpatches.Patch(color=PURPLE, label="Whale POC"),
    ]
    fig.legend(
        handles=legend_items, loc="lower center", ncol=5,
        fontsize=6.5, facecolor=PANEL_BG, edgecolor=BORDER,
        labelcolor=WHITE, framealpha=0.92,
        bbox_to_anchor=(0.5, 0.0)
    )
    fig.patch.set_facecolor(BG)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=130, facecolor=BG, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


# ── Standalone test ──────────────────────────────────────────────
if __name__ == "__main__":
    print("[GEX CHART] Generating test chart for AMZN...")
    buf = build_gex_level_chart(
        symbol="AMZN",
        spot=192.50,
        max_pain=190.00,
        net_gex_m=3.42,
        gex_zero=188.75,
        whale_poc=191.00,
        call_wall=195.00,
        put_wall=185.00,
        expiry="2026-06-06",
    )
    with open("amzn_gex_test.png", "wb") as f:
        f.write(buf.read())
    print("[GEX CHART] Saved to amzn_gex_test.png")
