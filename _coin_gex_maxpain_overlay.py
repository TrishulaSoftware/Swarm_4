"""
COIN — GEX x Max Pain Overlay
Aggregate Net GEX bars with Max Pain level lines overlaid by expiry.
"""

import sys, io, json, datetime, requests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, r'H:\Trishula\Swarm_4_Integration\Salvo_Staging')
sys.path.insert(0, r'H:\Trishula\Swarm_4_Integration\scratch')
import sovereign_options_scanner as s
from options_heatmap_engine import fetch_and_compute

SYMBOL  = "COIN"
DARK_BG = "#0a0a12"
PANEL_BG= "#0f0f1a"
GREEN   = "#00cc88"
RED     = "#ff3344"
GOLD    = "#ffbd15"
CYAN    = "#00e5ff"
WHITE   = "#e2e8f0"
DIM     = "#64748b"
BORDER  = "#1e1e30"

print(f"[COIN] Fetching engine data (6 expirations)...")
eng  = fetch_and_compute(SYMBOL, max_expirations=6)
spot = eng["meta"]["spot"]
print(f"[COIN] Spot: ${spot:.2f}")

# ── Filter strikes to relevant range (spot ± $60) ────────────────────────────
WINDOW = 60
gex_raw    = eng["aggregate_gex"]
all_strikes = sorted(float(k) for k in gex_raw.keys())
strikes     = [k for k in all_strikes if spot - WINDOW <= k <= spot + WINDOW]
gex_vals    = [float(gex_raw[str(k)]) for k in strikes]

# ── Max Pain by expiry ────────────────────────────────────────────────────────
mp_data  = []  # (short_label, max_pain_price, dte)
mp_colors = [GOLD, "#ff8844", "#aa66ff", CYAN, "#88ff44", "#ff44aa"]
for row in eng["expiry_summary"]:
    exp_str = row["expiry"]
    mp      = float(row["max_pain"])
    dte     = int(row["dte"])
    label   = f"{exp_str[5:]}  ({dte}d)"
    mp_data.append((label, mp, dte))

print(f"[COIN] {len(mp_data)} expiry max pain levels loaded.")

# ── Build chart ───────────────────────────────────────────────────────────────
fig, (ax_gex, ax_mp) = plt.subplots(1, 2, figsize=(16, 9),
                                     facecolor=DARK_BG,
                                     gridspec_kw={"width_ratios": [1.6, 1],
                                                  "wspace": 0.38})

# ── Left: Aggregate GEX bars ──────────────────────────────────────────────────
ax_gex.set_facecolor(PANEL_BG)
ax_gex.spines[:].set_color(BORDER)
ax_gex.tick_params(colors=WHITE, labelsize=7)

bar_colors = [GREEN if v >= 0 else RED for v in gex_vals]
bar_h = max(0.4, min(1.8, 120 / max(len(strikes), 1)))
ax_gex.barh(strikes, gex_vals, height=bar_h, color=bar_colors, alpha=0.85, zorder=3)
ax_gex.axvline(0, color=WHITE, lw=0.7, alpha=0.4)
ax_gex.axhline(spot, color=CYAN, lw=1.8, ls='--', alpha=0.95, zorder=5,
               label=f"Spot  ${spot:.2f}")
# Y-axis clamp to relevant range
ax_gex.set_ylim(spot - WINDOW - 2, spot + WINDOW + 2)

# Overlay Max Pain dotted lines — stagger labels vertically to avoid overlap
for i, (label, mp_price, dte) in enumerate(mp_data):
    col = mp_colors[i % len(mp_colors)]
    if spot - WINDOW <= mp_price <= spot + WINDOW:
        ax_gex.axhline(mp_price, color=col, lw=1.2, ls=':', alpha=0.9, zorder=4)
        x_max = max(gex_vals) if max(gex_vals) > 0 else 1
        # Stagger label x position so they don't collide
        x_offset = x_max * (0.55 + 0.12 * (i % 3))
        ax_gex.text(x_offset, mp_price + 0.4, f"MP {label}",
                    color=col, fontsize=6.5, va='bottom', ha='right', zorder=6)

ax_gex.set_xlabel("Net GEX ($M)", color=DIM, fontsize=8)
ax_gex.set_ylabel("Strike Price", color=DIM, fontsize=8)
ax_gex.set_title("Aggregate Net GEX  ×  Max Pain by Expiry",
                 color=WHITE, fontsize=9, pad=8)
ax_gex.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:.0f}"))
ax_gex.legend(fontsize=7.5, facecolor="#0d0d1a", edgecolor=BORDER,
              labelcolor=WHITE, framealpha=0.9, loc="lower right")

# ── Right: Max Pain term structure ────────────────────────────────────────────
ax_mp.set_facecolor(PANEL_BG)
ax_mp.spines[:].set_color(BORDER)
ax_mp.tick_params(colors=WHITE, labelsize=7)

mp_labels = [m[0] for m in mp_data]
mp_prices = [m[1] for m in mp_data]
mp_x      = range(len(mp_labels))

ax_mp.plot(mp_x, mp_prices, color=GOLD, lw=2.2, marker='o',
           markersize=7, zorder=4, label="Max Pain")
ax_mp.axhline(spot, color=CYAN, lw=1.5, ls='--', alpha=0.85,
              label=f"Spot  ${spot:.2f}")

# Shade GEX zones on term structure chart
pos_strikes = [k for k, v in zip(strikes, gex_vals) if v > 0 and k > spot]
neg_hi = min([k for k, v in zip(strikes, gex_vals) if v < 0 and k < spot],
             default=spot - 15)

ax_mp.fill_between([min(mp_x) - 0.5, max(mp_x) + 0.5],
                   spot, max(mp_prices) + 8, color=GREEN, alpha=0.05)
ax_mp.fill_between([min(mp_x) - 0.5, max(mp_x) + 0.5],
                   neg_hi, spot, color=RED, alpha=0.06)

ax_mp.text((max(mp_x)) * 0.5, spot + 2.5,
           "GEX PIN ZONE ▲ (dealer slow/pin)", color=GREEN,
           fontsize=7, ha='center', alpha=0.85)
ax_mp.text((max(mp_x)) * 0.5, spot - 4.5,
           "NEG GEX ZONE ▼ (dealer amplify)", color=RED,
           fontsize=7, ha='center', alpha=0.85)

# Annotate each Max Pain dot
for xi, (lbl, price) in enumerate(zip(mp_labels, mp_prices)):
    col = mp_colors[xi % len(mp_colors)]
    ax_mp.annotate(f"${price:.0f}",
                   xy=(xi, price), xytext=(0, 9),
                   textcoords='offset points',
                   color=col, fontsize=9, fontweight='bold', ha='center')

ax_mp.set_xticks(mp_x)
ax_mp.set_xticklabels([m[0][:7] for m in mp_data],
                      rotation=30, ha='right', color=DIM, fontsize=6.5)
ax_mp.set_ylabel("Strike Price ($)", color=DIM, fontsize=8)
ax_mp.set_title("Max Pain Term Structure  ×  GEX Zones",
                color=WHITE, fontsize=9, pad=8)
ax_mp.legend(fontsize=7.5, facecolor="#0d0d1a", edgecolor=BORDER,
             labelcolor=WHITE, framealpha=0.9)
ax_mp.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:.0f}"))

# ── Suptitle ──────────────────────────────────────────────────────────────────
now   = datetime.datetime.now()
sweep = "🔔 Market Open" if now.hour < 11 else ("🕛 Midday" if now.hour < 14 else "⚡ Power Hour")
ts    = now.strftime("%b %d %Y  %I:%M %p ET")

fig.suptitle(f"Q-MATRIX  |  COIN — GEX × Max Pain Overlay  |  {sweep}  ·  {ts}",
             color=CYAN, fontsize=12, fontweight='bold', y=0.97)
fig.patch.set_facecolor(DARK_BG)

buf = io.BytesIO()
plt.savefig(buf, format='png', dpi=150, facecolor=DARK_BG, bbox_inches='tight')
plt.close(fig)
buf.seek(0)

# ── Post to Discord ───────────────────────────────────────────────────────────
webhook = s.get_webhook(symbol=SYMBOL)
caption = (
    f"**COIN  —  GEX × Max Pain Overlay**  `{sweep}  ·  {ts}`\n"
    "Left: Aggregate Net GEX bars by strike — green = dealer pin zone (price held here), "
    "red = accelerant zone (moves amplify here). Dotted lines = Max Pain for each expiry, "
    "showing where the market wants price to close. "
    "Right: Max Pain term structure across expirations with GEX zones shaded — "
    "green above spot (pin/slow zone), red below spot (acceleration zone). "
    "Each dot is where expiry gravity pulls by that date."
)
payload = {"content": caption}
r = requests.post(webhook,
    data={"payload_json": json.dumps(payload)},
    files={"file": ("coin_gex_maxpain_overlay.png", buf, "image/png")},
    timeout=30)

if r.status_code in (200, 204):
    print(f"[COIN] GEX × Max Pain overlay posted. ✓")
else:
    print(f"[COIN] Discord error {r.status_code}: {r.text[:200]}")
