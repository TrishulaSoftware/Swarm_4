#!/usr/bin/env python3
"""
=================================================================
TRISHULA Q-MATRIX — HISTORICAL ACCURACY BACKTEST v2
=================================================================
Scores all DB1 snapshots where outcome data is available.
Uses same-day intraday range for May 29 data (Friday pending).
=================================================================
"""
import sys, json, warnings, datetime, requests
from base64 import b64encode
from pathlib import Path
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE     = Path(r"H:\Trishula\Swarm_4_Integration\Salvo_Staging")
ORDS_URL = "https://g275356d1414552-trishulapicks.adb.us-ashburn-1.oraclecloudapps.com/ords/admin"
CREDS    = b64encode(b"ADMIN:C1iffyHu5tl3!!!").decode()
HEADERS  = {"Authorization": f"Basic {CREDS}"}

# ── 1. Fetch all DB1 snapshots ────────────────────────────────
print("\n" + "="*62)
print("  TRISHULA Q-MATRIX — ACCURACY BACKTEST v2")
print("="*62)
print("\n[1/5] Fetching DB1 snapshots...")

all_snaps = []
url = f"{ORDS_URL}/qmatrix_snapshots/?limit=500"
while url:
    r = requests.get(url, headers=HEADERS, verify=False, timeout=20)
    if r.status_code != 200: break
    data = r.json()
    all_snaps.extend(data.get("items", []))
    url = next((l["href"] for l in data.get("links", []) if l["rel"] == "next"), None)

snaps = [s for s in all_snaps
         if s.get("ticker") not in ("TEST", None, "")
         and s.get("spot", 0) > 0
         and s.get("max_pain", 0) > 0]

# Deduplicate: best snapshot per ticker per date (open scan preferred)
from collections import defaultdict
best = {}
for s in sorted(snaps, key=lambda x: x.get("scan_time","09:30")):
    key = (s["scan_date"], s["ticker"])
    if key not in best:
        best[key] = s
snap_list = list(best.values())

dates_in_db = sorted(set(s["scan_date"] for s in snap_list))
tickers_in_db = sorted(set(s["ticker"] for s in snap_list))
print(f"  Snapshots: {len(snap_list)} unique ticker-days")
print(f"  Dates:     {dates_in_db}")
print(f"  Tickers:   {len(tickers_in_db)}")

# ── 2. Fetch price data ───────────────────────────────────────
print("\n[2/5] Fetching price data...")
price_cache = {}
for tkr in tickers_in_db:
    try:
        hist = yf.Ticker(tkr).history(period="45d", interval="1d", auto_adjust=True)
        if not hist.empty:
            hist.index = hist.index.tz_localize(None) if hist.index.tz else hist.index
            hist.index = pd.DatetimeIndex([pd.Timestamp(str(d)[:10]) for d in hist.index])
            price_cache[tkr] = hist
    except Exception as e:
        pass

print(f"  Price data for {len(price_cache)}/{len(tickers_in_db)} tickers")

# ── 3. Score each snapshot ────────────────────────────────────
print("\n[3/5] Scoring accuracy...")

BULLSEYE = 0.003
HIT      = 0.0075
CLOSE    = 0.015

def dist(a, b):
    return abs(a - b) / b if b else 999

def grade(a, predicted):
    d = dist(a, predicted)
    if d <= BULLSEYE: return "BULLSEYE", d
    if d <= HIT:      return "HIT",      d
    if d <= CLOSE:    return "CLOSE",    d
    return "MISS", d

results  = []
pending  = []  # snapshots where future data not yet available

for s in snap_list:
    tkr       = s["ticker"]
    sdate     = pd.Timestamp(s["scan_date"])
    spot      = s.get("spot", 0)
    max_pain  = s.get("max_pain", 0)
    gex_zero  = s.get("gex_zero", 0)
    whale_poc = s.get("whale_poc", 0)
    iv_skew   = s.get("iv_skew_pct", 0)
    whale_bull= s.get("whale_bull_pct", 50)

    if tkr not in price_cache:
        continue

    hist = price_cache[tkr]

    # Same-day row (for intraday range validation)
    same_day = hist[hist.index == sdate]

    # Next trading day
    future = hist[hist.index > sdate].sort_index()

    # Friday of same week
    week_end = sdate + pd.offsets.Week(weekday=4)
    fri_rows = hist[(hist.index > sdate) & (hist.index <= week_end) & (hist.index.dayofweek == 4)]

    if future.empty:
        pending.append(s)
        continue

    next_row   = future.iloc[0]
    next_close = float(next_row["Close"])
    next_high  = float(next_row["High"])
    next_low   = float(next_row["Low"])
    next_date  = str(future.index[0])[:10]

    fri_close = float(fri_rows.iloc[0]["Close"]) if not fri_rows.empty else next_close
    fri_date  = str(fri_rows.index[0])[:10] if not fri_rows.empty else next_date

    # Intraday range check - did any level get TOUCHED?
    if not same_day.empty:
        day_high = float(same_day.iloc[0]["High"])
        day_low  = float(same_day.iloc[0]["Low"])
        gex_touched = gex_zero and (day_low <= gex_zero <= day_high)
        poc_touched  = whale_poc and (day_low <= whale_poc <= day_high)
    else:
        gex_touched = poc_touched = None

    # Max Pain — score against Friday close
    mp_grade, mp_d = grade(fri_close, max_pain) if max_pain else ("N/A", 0)

    # GEX Zero — score against next-day close AND intraday touch
    gz_grade, gz_d = grade(next_close, gex_zero) if gex_zero else ("N/A", 0)

    # Whale POC — score against next-day close
    wp_grade, wp_d = grade(next_close, whale_poc) if whale_poc else ("N/A", 0)

    # IV Skew directional
    move = (next_close - spot) / spot
    iv_dir = None
    if iv_skew and iv_skew != 0:
        iv_dir = (iv_skew < 0 and move < 0) or (iv_skew > 0 and move > 0)

    # Whale Bull directional
    wh_dir = None
    if whale_bull:
        wh_dir = (whale_bull > 50 and move > 0) or (whale_bull < 50 and move < 0)

    results.append({
        "date":       s["scan_date"],
        "ticker":     tkr,
        "spot":       spot,
        "next_date":  next_date,
        "next_close": round(next_close, 2),
        "fri_date":   fri_date,
        "fri_close":  round(fri_close, 2),
        "move_pct":   round(move * 100, 2),
        "max_pain":   max_pain,
        "mp_grade":   mp_grade,
        "mp_dist":    round(mp_d * 100, 2),
        "gex_zero":   gex_zero,
        "gz_grade":   gz_grade,
        "gz_dist":    round(gz_d * 100, 2),
        "gex_touched": gex_touched,
        "whale_poc":  whale_poc,
        "wp_grade":   wp_grade,
        "wp_dist":    round(wp_d * 100, 2),
        "poc_touched": poc_touched,
        "iv_skew":    iv_skew,
        "iv_dir":     iv_dir,
        "whale_bull": whale_bull,
        "wh_dir":     wh_dir,
    })

print(f"  Scored:  {len(results)} ticker-days")
print(f"  Pending: {len(pending)} (May 30 close not yet in yfinance)")

if not results:
    print("\n  No scoreable data yet. All scans are from May 29 —")
    print("  May 30 close settles Monday in yfinance.")
    print("  Run this script Monday after 6 PM ET for full results.")
    sys.exit(0)

# ── 4. Aggregate stats ────────────────────────────────────────
print("\n[4/5] Aggregating stats...")
df = pd.DataFrame(results)

def hit_pct(col, vals=("BULLSEYE","HIT")):
    v = df[col][df[col].notna()]
    return v.isin(vals).sum(), len(v), round(v.isin(vals).mean()*100, 1) if len(v) else 0

def pin_pct(col):
    return hit_pct(col, ("BULLSEYE","HIT","CLOSE"))

def dir_pct(col):
    v = df[col].dropna().astype(bool)
    return v.sum(), len(v), round(v.mean()*100, 1) if len(v) else 0

mp_h,mp_t,mp_r   = hit_pct("mp_grade")
mp_p,_,mp_pr     = pin_pct("mp_grade")
gz_h,gz_t,gz_r   = hit_pct("gz_grade")
gz_p,_,gz_pr     = pin_pct("gz_grade")
wp_h,wp_t,wp_r   = hit_pct("wp_grade")
wp_p,_,wp_pr     = pin_pct("wp_grade")
iv_h,iv_t,iv_r   = dir_pct("iv_dir")
wh_h,wh_t,wh_r   = dir_pct("wh_dir")

# Intraday touch rates
gex_touch_rate = round(df["gex_touched"].dropna().mean()*100, 1) if df["gex_touched"].notna().any() else 0
poc_touch_rate = round(df["poc_touched"].dropna().mean()*100, 1) if df["poc_touched"].notna().any() else 0

# ── Print Full Report ─────────────────────────────────────────
print("\n" + "="*62)
print("  TRISHULA Q-MATRIX ACCURACY REPORT")
print(f"  Scan period: {df['date'].min()} → {df['date'].max()}")
print(f"  Outcome:     next-day close / Friday close")
print(f"  Ticker-days scored: {len(df)} | Pending: {len(pending)}")
print("="*62)

print(f"""
╔══ LEVEL ACCURACY (Bullseye≤0.3% | Hit≤0.75% | Pin≤1.5%) ══╗
║  Max Pain      Hit: {mp_h:3}/{mp_t}={mp_r:5.1f}%  Pin: {mp_p:3}/{mp_t}={mp_pr:5.1f}%  ║
║  GEX Zero      Hit: {gz_h:3}/{gz_t}={gz_r:5.1f}%  Pin: {gz_p:3}/{gz_t}={gz_pr:5.1f}%  ║
║  Whale POC     Hit: {wp_h:3}/{wp_t}={wp_r:5.1f}%  Pin: {wp_p:3}/{wp_t}={wp_pr:5.1f}%  ║
╠══ DIRECTIONAL ACCURACY ════════════════════════════════════╣
║  IV Skew:    {iv_h:3}/{iv_t} correct = {iv_r:5.1f}%                       ║
║  Whale Bull: {wh_h:3}/{wh_t} correct = {wh_r:5.1f}%                       ║
╠══ INTRADAY TOUCH RATES ════════════════════════════════════╣
║  GEX Zero touched intraday: {gex_touch_rate:5.1f}%                       ║
║  Whale POC touched intraday: {poc_touch_rate:5.1f}%                      ║
╚════════════════════════════════════════════════════════════╝
""")

# Per-ticker table
print(f"  {'TICKER':<8} {'DATE':<12} {'SPOT':>7} {'NEXT_CL':>8} {'MOVE%':>6} "
      f"{'MAXPAIN':>8} {'MP':>8} {'GEXZERO':>8} {'GZ':>8} {'POC':>7} {'WP':>8} "
      f"{'IV':>5} {'WH':>5}")
print("  " + "─"*104)
for _, r in df.sort_values(["date","ticker"]).iterrows():
    iv  = "✓" if r["iv_dir"] else ("✗" if r["iv_dir"] is not None else "-")
    wh  = "✓" if r["wh_dir"] else ("✗" if r["wh_dir"] is not None else "-")
    mp  = r["mp_grade"][:4] if r["mp_grade"] != "N/A" else " N/A"
    gz  = r["gz_grade"][:4] if r["gz_grade"] != "N/A" else " N/A"
    wp  = r["wp_grade"][:4] if r["wp_grade"] != "N/A" else " N/A"
    gz_val  = r["gex_zero"]  or 0
    wp_val  = r["whale_poc"] or 0
    print(f"  {r['ticker']:<8} {r['date']:<12} {r['spot']:>7.2f} {r['next_close']:>8.2f} "
          f"{r['move_pct']:>+6.2f}% {r['max_pain']:>8.2f} {mp:>8} "
          f"{gz_val:>8.2f} {gz:>8} {wp_val:>7.2f} {wp:>8} "
          f"{iv:>5} {wh:>5}")

# Pending predictions (May 30 outcome)
if pending:
    print(f"\n  PENDING — {len(pending)} snapshots await May 30 close:")
    print(f"  {'TICKER':<8} {'SPOT':>7} {'MAX_PAIN':>9} {'GEX_ZERO':>9} {'W_POC':>8} {'IV_SKEW':>8} {'BULL%':>6}")
    print("  " + "─"*65)
    for s in sorted(pending, key=lambda x: x["ticker"]):
        print(f"  {s['ticker']:<8} {s['spot'] or 0:>7.2f} {s['max_pain'] or 0:>9.2f} "
              f"{s.get('gex_zero') or 0:>9.2f} {s.get('whale_poc') or 0:>8.2f} "
              f"{s.get('iv_skew_pct') or 0:>8.3f} {s.get('whale_bull_pct') or 0:>6.1f}%")

# ── 5. Chart ──────────────────────────────────────────────────
print("\n[5/5] Generating chart...")
import io
DARK = "#0d1117"; GREEN = "#00ff88"; RED = "#ff4455"; GOLD = "#ffd700"; BLUE = "#4488ff"

fig, axes = plt.subplots(2, 2, figsize=(16, 10), facecolor=DARK)
fig.suptitle("🔱 TRISHULA Q-MATRIX — ACCURACY BACKTEST", color=GOLD, fontsize=14, fontweight="bold")

# Panel 1: Bar chart — level accuracy
ax = axes[0][0]; ax.set_facecolor(DARK)
cats  = ["Max Pain\nHit", "Max Pain\nPin", "GEX Zero\nHit", "GEX Zero\nPin", "Whale POC\nHit", "Whale POC\nPin"]
vals  = [mp_r, mp_pr, gz_r, gz_pr, wp_r, wp_pr]
colors= [GREEN if v>=50 else (GOLD if v>=25 else RED) for v in vals]
b = ax.bar(cats, vals, color=colors, alpha=0.85)
for bar, v in zip(b, vals):
    ax.text(bar.get_x()+bar.get_width()/2, v+1, f"{v:.1f}%", ha="center", color="white", fontsize=9)
ax.set_ylim(0, 100); ax.set_title("Level Accuracy", color=GOLD)
ax.tick_params(colors="white", labelsize=8); ax.set_ylabel("Accuracy %", color="white")
for sp in ax.spines.values(): sp.set_edgecolor("#333")

# Panel 2: Directional accuracy
ax2 = axes[0][1]; ax2.set_facecolor(DARK)
d_cats = ["IV Skew\nDirectional", "Whale Bull%\nDirectional"]
d_vals = [iv_r, wh_r]
d_cols = [GREEN if v>=55 else RED for v in d_vals]
b2 = ax2.bar(d_cats, d_vals, color=d_cols, alpha=0.85, width=0.4)
for bar, v in zip(b2, d_vals):
    ax2.text(bar.get_x()+bar.get_width()/2, v+1, f"{v:.1f}%", ha="center", color="white", fontsize=12, fontweight="bold")
ax2.axhline(50, color=GOLD, ls="--", alpha=0.5, label="50% baseline")
ax2.set_ylim(0, 100); ax2.set_title("Directional Signals", color=GOLD)
ax2.tick_params(colors="white"); ax2.set_ylabel("Accuracy %", color="white")
ax2.legend(facecolor="#1a1a2e", labelcolor="white")
for sp in ax2.spines.values(): sp.set_edgecolor("#333")

# Panel 3: Scatter — Max Pain distance vs actual move
ax3 = axes[1][0]; ax3.set_facecolor(DARK)
ax3.scatter(df["mp_dist"], df["move_pct"].abs(),
            c=[GREEN if v>=0 else RED for v in df["move_pct"]],
            alpha=0.7, s=60, edgecolors="white", linewidths=0.4)
for _, row in df.iterrows():
    ax3.annotate(row["ticker"], (row["mp_dist"], abs(row["move_pct"])),
                 fontsize=6, color="#aaa", textcoords="offset points", xytext=(3,3))
ax3.axvline(0.75, color=GOLD, ls="--", alpha=0.5, label="Hit threshold (0.75%)")
ax3.axvline(1.5,  color=RED,  ls="--", alpha=0.4, label="Pin threshold (1.5%)")
ax3.set_xlabel("Max Pain Distance %", color="white")
ax3.set_ylabel("|Price Move %|", color="white")
ax3.set_title("Max Pain Distance vs Actual Move", color=GOLD)
ax3.tick_params(colors="white")
ax3.legend(facecolor="#1a1a2e", labelcolor="white", fontsize=8)
for sp in ax3.spines.values(): sp.set_edgecolor("#333")

# Panel 4: Pending predictions table visual
ax4 = axes[1][1]; ax4.set_facecolor(DARK); ax4.axis("off")
ax4.set_title(f"Pending — {len(pending)} snapshots\n(May 30 close not yet available)", color=GOLD)
if pending:
    pend_data = sorted(pending, key=lambda x: x["ticker"])[:20]
    col_labels = ["Ticker", "Spot", "MaxPain", "GEX0", "WhalePOC", "Bull%"]
    table_data = []
    for s in pend_data:
        table_data.append([
            s["ticker"],
            f"{s['spot'] or 0:.2f}",
            f"{s['max_pain'] or 0:.2f}",
            f"{s.get('gex_zero') or 0:.2f}",
            f"{s.get('whale_poc') or 0:.2f}",
            f"{s.get('whale_bull_pct') or 0:.1f}%"
        ])
    tbl = ax4.table(cellText=table_data, colLabels=col_labels,
                    loc="center", cellLoc="center")
    tbl.auto_set_font_size(False); tbl.set_fontsize(7.5)
    for (r, c), cell in tbl.get_celld().items():
        cell.set_facecolor("#1a1a2e" if r > 0 else "#0d2040")
        cell.set_text_props(color="white")
        cell.set_edgecolor("#333")

plt.tight_layout(rect=[0, 0, 1, 0.95])
buf = io.BytesIO()
plt.savefig(buf, format="png", dpi=130, facecolor=DARK, bbox_inches="tight")
buf.seek(0)
plt.close()

out_img = BASE / "qmatrix_accuracy_backtest.png"
out_img.write_bytes(buf.getvalue())
print(f"  Chart: {out_img}")

# Save JSON
report = {
    "generated":   datetime.datetime.now().isoformat(),
    "scored":      len(results),
    "pending":     len(pending),
    "accuracy": {
        "max_pain":   {"hit": mp_r, "pin": mp_pr},
        "gex_zero":   {"hit": gz_r, "pin": gz_pr},
        "whale_poc":  {"hit": wp_r, "pin": wp_pr},
        "iv_skew_directional":    iv_r,
        "whale_bull_directional": wh_r,
        "gex_intraday_touch":     gex_touch_rate,
        "poc_intraday_touch":     poc_touch_rate,
    },
    "results":     results,
    "pending_predictions": [
        {"ticker": s["ticker"], "spot": s["spot"], "max_pain": s["max_pain"],
         "gex_zero": s.get("gex_zero"), "whale_poc": s.get("whale_poc"),
         "iv_skew": s.get("iv_skew_pct"), "whale_bull": s.get("whale_bull_pct")}
        for s in pending
    ]
}
(BASE / "qmatrix_accuracy_report.json").write_text(
    json.dumps(report, indent=2, default=str), encoding="utf-8")
print(f"  JSON: {BASE/'qmatrix_accuracy_report.json'}")

print("\n" + "="*62)
print("  BACKTEST COMPLETE")
if pending:
    print(f"  Run again Monday 6PM ET for May 30 outcome scoring")
print("="*62)
