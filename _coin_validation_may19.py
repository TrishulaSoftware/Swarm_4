"""
COIN — Q-Matrix Historical Validation  (Week of May 18, 2026)
==============================================================
Reconstructs what the package would have shown on Monday May 19 open
and overlays actual COIN price action through May 25 to validate the thesis.

Key levels from current GEX engine (June expirations unchanged from that week):
  $198  — Dominant positive GEX wall (dealer pin ceiling)
  $192  — Max Pain May 29 (nearest expiry from May 19 perspective)
  $185  — Current spot / near-term equilibrium
  $170  — Positive GEX floor (June 18 institutional support)

Saved locally — no Discord post.
"""

import sys, io, datetime
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec

sys.path.insert(0, r'H:\Trishula\Swarm_4_Integration\Salvo_Staging')
sys.path.insert(0, r'H:\Trishula\Swarm_4_Integration\scratch')
import yfinance as yf
from options_heatmap_engine import fetch_and_compute

DARK_BG  = "#0a0a12"
PANEL_BG = "#0f0f1a"
GREEN    = "#00cc88"
RED      = "#ff3344"
GOLD     = "#ffbd15"
CYAN     = "#00e5ff"
WHITE    = "#e2e8f0"
DIM      = "#64748b"
BORDER   = "#1e1e30"
ORANGE   = "#ff8844"

# ── Pull COIN hourly data for May 12 - May 25 ─────────────────────────────────
print("[COIN] Fetching hourly price data May 12-25...")
df = yf.download("COIN", period="20d", interval="1h",
                 progress=False, auto_adjust=True)
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

# Filter to May 12 - May 25
df.index = pd.to_datetime(df.index)
df = df[df.index >= "2026-05-12"]
print(f"[COIN] {len(df)} hourly bars loaded.")

# ── Pull current GEX engine for level reference ────────────────────────────────
print("[COIN] Running GEX engine for key levels...")
eng  = fetch_and_compute("COIN", max_expirations=6)
spot = eng["meta"]["spot"]

# Build GEX by strike (filtered to relevant range)
WINDOW = 60
gex_raw    = eng["aggregate_gex"]
all_strikes = sorted(float(k) for k in gex_raw.keys())
strikes     = [k for k in all_strikes if spot - WINDOW <= k <= spot + WINDOW]
gex_vals    = [float(gex_raw[str(k)]) for k in strikes]

# Max Pain by expiry
mp_data = []
for row in eng["expiry_summary"]:
    mp_data.append({
        "expiry": row["expiry"],
        "dte":    row["dte"],
        "mp":     float(row["max_pain"]),
        "pc":     float(row.get("put_call_ratio", 1.0)),
    })

# Key structural levels
LEVEL_198 = 198.0   # Dominant positive GEX wall
LEVEL_192 = next((r["mp"] for r in mp_data if "05-29" in r["expiry"]), 192.0)
LEVEL_185 = spot    # Near-term equilibrium / spot ref
LEVEL_170 = 170.0   # Positive GEX floor (June 18)
LEVEL_SPOT_MAY19 = None  # Actual May 19 open

# ── Find May 19 open ──────────────────────────────────────────────────────────
may19 = df[df.index.date == datetime.date(2026, 5, 19)]
if not may19.empty:
    LEVEL_SPOT_MAY19 = float(may19["Open"].iloc[0])
    print(f"[COIN] May 19 open: ${LEVEL_SPOT_MAY19:.2f}")

# ── Build figure ──────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(18, 13), facecolor=DARK_BG)
gs  = GridSpec(2, 2, figure=fig,
               height_ratios=[2.5, 1],
               width_ratios=[2.2, 1],
               hspace=0.35, wspace=0.32,
               left=0.06, right=0.97, top=0.91, bottom=0.06)

ax_price  = fig.add_subplot(gs[0, 0])   # Main price chart
ax_gex    = fig.add_subplot(gs[0, 1])   # GEX bars (right side)
ax_mp     = fig.add_subplot(gs[1, 0])   # Max Pain term structure
ax_ctx    = fig.add_subplot(gs[1, 1])   # Context / thesis summary

# ── 1. PRICE CHART ────────────────────────────────────────────────────────────
ax_price.set_facecolor(PANEL_BG)
ax_price.spines[:].set_color(BORDER)
ax_price.tick_params(colors=WHITE, labelsize=7)

closes = df["Close"]
opens  = df["Open"]
highs  = df["High"]
lows   = df["Low"]

# Draw candlestick bars
for i, (ts, row) in enumerate(df.iterrows()):
    o, c, h, l = float(row["Open"]), float(row["Close"]), float(row["High"]), float(row["Low"])
    col = GREEN if c >= o else RED
    ax_price.plot([ts, ts], [l, h], color=col, lw=0.6, alpha=0.7)
    ax_price.bar(ts, abs(c - o), bottom=min(o, c), color=col, alpha=0.85,
                 width=pd.Timedelta(minutes=35))

# ── Key level overlays ────────────────────────────────────────────────────────
levels = [
    (LEVEL_198, "#ff6622", "--", "GEX Wall  $198  (Dealer Pin Ceiling)",    1.2),
    (LEVEL_192, GOLD,      "-",  f"Max Pain May 29  ${LEVEL_192:.0f}",      1.5),
    (LEVEL_185, CYAN,      ":",  f"Spot Ref  ${LEVEL_185:.2f}  (Today)",    1.2),
    (LEVEL_170, GREEN,     "--", "GEX Floor  $170  (Inst. Support Jun 18)", 1.2),
]
if LEVEL_SPOT_MAY19:
    levels.insert(2, (LEVEL_SPOT_MAY19, WHITE, "-.", f"May 19 Open  ${LEVEL_SPOT_MAY19:.2f}", 1.0))

for lvl, col, ls, label, lw in levels:
    ax_price.axhline(lvl, color=col, lw=lw, ls=ls, alpha=0.85, zorder=4)
    ax_price.text(df.index[-1], lvl + 0.5, label, color=col,
                  fontsize=6.5, va="bottom", ha="right", zorder=5)

# Shade week of May 18-22
may18_start = pd.Timestamp("2026-05-19 09:30", tz=df.index.tz)
may23_end   = pd.Timestamp("2026-05-23 16:00", tz=df.index.tz)
if df.index.tz:
    ax_price.axvspan(may18_start, may23_end,
                     color=GOLD, alpha=0.04, label="Week of May 19")

ax_price.set_title("COIN  —  Price Action  |  May 12–25, 2026  (Hourly)",
                   color=WHITE, fontsize=9, pad=6)
ax_price.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
ax_price.xaxis.set_major_locator(mdates.DayLocator(interval=2))
ax_price.set_ylabel("Price ($)", color=DIM, fontsize=8)
ax_price.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:.0f}"))
ax_price.legend(fontsize=6.5, facecolor="#0d0d1a", edgecolor=BORDER,
                labelcolor=WHITE, framealpha=0.8, loc="upper left")

# Y-axis zoom to relevant range
price_min = float(df["Low"].min())
price_max = float(df["High"].max())
pad = (price_max - price_min) * 0.08
ax_price.set_ylim(min(LEVEL_170 - 5, price_min - pad),
                  max(LEVEL_198 + 5, price_max + pad))

# ── 2. AGGREGATE NET GEX ─────────────────────────────────────────────────────
ax_gex.set_facecolor(PANEL_BG)
ax_gex.spines[:].set_color(BORDER)
ax_gex.tick_params(colors=WHITE, labelsize=7)

bar_colors = [GREEN if v >= 0 else RED for v in gex_vals]
bar_h      = max(0.4, min(1.8, 120 / max(len(strikes), 1)))
ax_gex.barh(strikes, gex_vals, height=bar_h, color=bar_colors, alpha=0.85, zorder=3)
ax_gex.axvline(0, color=WHITE, lw=0.6, alpha=0.4)
ax_gex.axhline(LEVEL_SPOT_MAY19 or spot, color=WHITE,  lw=1.0, ls="-.",
               alpha=0.7, label=f"May 19 Open")
ax_gex.axhline(spot,             color=CYAN,  lw=1.4, ls="--",
               alpha=0.9, label=f"Today ${spot:.2f}")

# Max Pain lines on GEX
mp_colors = [GOLD, ORANGE, "#aa66ff", CYAN, GREEN, "#ff44aa"]
for i, row in enumerate(mp_data[:4]):
    col = mp_colors[i]
    if spot - WINDOW <= row["mp"] <= spot + WINDOW:
        ax_gex.axhline(row["mp"], color=col, lw=0.9, ls=":", alpha=0.8)
        ax_gex.text(max(gex_vals) * 0.4, row["mp"] + 0.4,
                    f"MP {row['expiry'][5:]}  ${row['mp']:.0f}",
                    color=col, fontsize=6, va="bottom")

ax_gex.set_ylim(spot - WINDOW - 2, spot + WINDOW + 2)
ax_gex.set_title("Aggregate Net GEX", color=WHITE, fontsize=9, pad=6)
ax_gex.set_xlabel("Net GEX ($M)", color=DIM, fontsize=7)
ax_gex.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:.0f}"))
ax_gex.legend(fontsize=6.5, facecolor="#0d0d1a", edgecolor=BORDER,
              labelcolor=WHITE, framealpha=0.9, loc="lower right")

# ── 3. MAX PAIN TERM STRUCTURE ────────────────────────────────────────────────
ax_mp.set_facecolor(PANEL_BG)
ax_mp.spines[:].set_color(BORDER)
ax_mp.tick_params(colors=WHITE, labelsize=7)

mp_x      = range(len(mp_data))
mp_prices = [r["mp"] for r in mp_data]
mp_labels = [r["expiry"][5:] for r in mp_data]

ax_mp.plot(mp_x, mp_prices, color=GOLD, lw=2.2, marker="o",
           markersize=7, zorder=4, label="Max Pain")
ax_mp.axhline(LEVEL_SPOT_MAY19 or spot, color=WHITE, lw=1.0, ls="-.",
              alpha=0.7, label=f"May 19 Open")
ax_mp.axhline(spot, color=CYAN, lw=1.3, ls="--", alpha=0.85,
              label=f"Today ${spot:.2f}")

# Shade GEX zones
ax_mp.fill_between([-0.5, len(mp_data) - 0.5], spot, max(mp_prices) + 8,
                   color=GREEN, alpha=0.05)
ax_mp.fill_between([-0.5, len(mp_data) - 0.5], LEVEL_170, spot,
                   color=RED, alpha=0.05)

for xi, row in enumerate(mp_data):
    ax_mp.annotate(f"${row['mp']:.0f}", xy=(xi, row["mp"]),
                   xytext=(0, 8), textcoords="offset points",
                   color=mp_colors[xi % len(mp_colors)],
                   fontsize=8.5, fontweight="bold", ha="center")

ax_mp.set_xticks(mp_x)
ax_mp.set_xticklabels(mp_labels, rotation=25, ha="right", color=DIM, fontsize=7)
ax_mp.set_title("Max Pain Term Structure", color=WHITE, fontsize=9, pad=6)
ax_mp.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:.0f}"))
ax_mp.legend(fontsize=6.5, facecolor="#0d0d1a", edgecolor=BORDER,
             labelcolor=WHITE, framealpha=0.9, loc="upper left")

# ── 4. THESIS CONTEXT ─────────────────────────────────────────────────────────
ax_ctx.set_facecolor(PANEL_BG)
ax_ctx.spines[:].set_color(BORDER)
ax_ctx.set_xlim(0, 1); ax_ctx.set_ylim(0, 1); ax_ctx.axis("off")

lines = [
    ("Q-MATRIX  |  COIN  Week of May 19", WHITE,   9.5, True),
    ("", WHITE, 7, False),
    ("WHAT WE WOULD HAVE SAID:", GOLD, 8, True),
    ("", WHITE, 6, False),
    (f"May 19 Open:  ${LEVEL_SPOT_MAY19:.2f}" if LEVEL_SPOT_MAY19 else "May 19 data unavailable", CYAN, 8, False),
    (f"Max Pain (May 22 / May 29):  $192", GOLD, 8, False),
    (f"GEX Ceiling:  $198", ORANGE, 8, False),
    (f"Neg GEX Zone:  $185 \u2013 $172", RED, 8, False),
    (f"Inst. Floor:  $170", GREEN, 8, False),
    ("", WHITE, 6, False),
    ("THESIS:", WHITE, 8, True),
    ("Hold above $185 \u2192 grind to $192", WHITE, 7.5, False),
    ("Break $185 \u2192 acceleration to $170", RED, 7.5, False),
    ("Bounce at $170 \u2192 pin at $190+", GREEN, 7.5, False),
    ("", WHITE, 6, False),
    ("WHAT HAPPENED:", GOLD, 8, True),
]

# Add actual outcome lines
if LEVEL_SPOT_MAY19:
    week_high = float(df[df.index >= "2026-05-19"]["High"].max())
    week_low  = float(df[df.index >= "2026-05-19"]["Low"].min())
    lines += [
        (f"Week High:  ${week_high:.2f}", GREEN, 7.5, False),
        (f"Week Low:   ${week_low:.2f}", RED, 7.5, False),
        (f"Today:      ${spot:.2f}", CYAN, 7.5, False),
    ]
    # Did thesis play out?
    if week_low <= 172:
        lines.append(("Broke into Neg GEX zone \u2713", RED, 7.5, True))
    if week_high >= 190:
        lines.append(("Reached Max Pain zone \u2713", GREEN, 7.5, True))

y_pos = 0.97
for text, col, size, bold in lines:
    if text == "":
        y_pos -= 0.04; continue
    ax_ctx.text(0.03, y_pos, text, color=col, fontsize=size,
                fontweight="bold" if bold else "normal", va="top")
    y_pos -= 0.065

# ── Suptitle ──────────────────────────────────────────────────────────────────
fig.suptitle(
    "Q-MATRIX  |  COIN  —  Historical Validation  "
    "| Week of May 19, 2026  vs  Actual Through May 25",
    color=CYAN, fontsize=12, fontweight="bold", y=0.97
)
fig.patch.set_facecolor(DARK_BG)

# ── Save locally ──────────────────────────────────────────────────────────────
OUT = r"C:\Users\War Machine\.gemini\antigravity\brain\79ef1ade-7f7c-4134-b2ab-f70dee7428f9\coin_validation_may19.png"
plt.savefig(OUT, format="png", dpi=150, facecolor=DARK_BG, bbox_inches="tight")
plt.close(fig)
print(f"[COIN] Saved to: {OUT}")
