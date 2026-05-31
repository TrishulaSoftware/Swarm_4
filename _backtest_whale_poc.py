#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=================================================================
TRISHULA Q-MATRIX — WHALE LIQUIDITY PROFILE BACKTEST
=================================================================
Uses 6 months of historical OHLCV (yfinance) to backtest whether
price respects Whale POC (Point of Control) levels.

Method:
  For each trading day in lookback window:
    1. Calculate Whale Profile from bars BEFORE that day
    2. Get the POC level and key support/resistance levels
    3. Score whether price touched POC during that day's session
    4. Score whether price closed near POC on expiry Fridays

Scoring:
  BULLSEYE  = price within 0.3% of POC at any point in session
  HIT       = price within 0.75% of POC at any point
  CLOSE     = price within 1.5% of POC
  MISS      = price never within 1.5%
=================================================================
"""
import sys, json, datetime
import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

# ── Config ────────────────────────────────────────────────────
TICKERS       = ['SPY', 'QQQ', 'IWM', 'NVDA', 'TSLA', 'AAPL', 'AMZN', 'MSFT', 'SOXL', 'SMH']
LOOKBACK_DAYS = 60       # days of history to score
WHALE_WINDOW  = 40       # bars used to build each daily whale profile (recent context only)
WHALE_PCT     = 0.97     # top 3% volume = institutional threshold
N_BINS        = 30       # price bins for profile
BULLSEYE_PCT  = 0.003    # 0.3%
HIT_PCT       = 0.0075   # 0.75%
CLOSE_PCT     = 0.015    # 1.5%

DARK_BG  = "#0a0a14"
PANEL_BG = "#0d0d1a"
GREEN    = "#00cc66"
RED      = "#ff3344"
GOLD     = "#ffbd15"
CYAN     = "#00e5ff"
WHITE    = "#e2e8f0"
DIM      = "#64748b"


def calc_whale_poc(bars: pd.DataFrame) -> dict:
    """
    Calculate Whale Liquidity POC from OHLCV bars.
    Returns dict with poc_price, support/resistance levels, bull_pct.
    """
    if bars.empty or len(bars) < 20:
        return {}

    # Whale threshold: top WHALE_PCT volume candles
    vol_threshold = bars['Volume'].quantile(WHALE_PCT)
    whale_bars    = bars[bars['Volume'] >= vol_threshold].copy()

    if whale_bars.empty:
        return {}

    price_min = bars['Low'].min()
    price_max = bars['High'].max()
    if price_min >= price_max:
        return {}

    bins     = np.linspace(price_min, price_max, N_BINS + 1)
    bin_mid  = (bins[:-1] + bins[1:]) / 2
    bull_vol = np.zeros(N_BINS)
    bear_vol = np.zeros(N_BINS)

    for _, row in whale_bars.iterrows():
        is_bull = row['Close'] >= row['Open']
        mid     = (row['High'] + row['Low']) / 2
        idx     = int(np.searchsorted(bins, mid, side='right') - 1)
        idx     = max(0, min(idx, N_BINS - 1))
        if is_bull:
            bull_vol[idx] += row['Volume']
        else:
            bear_vol[idx] += row['Volume']

    total_vol = bull_vol + bear_vol
    poc_idx   = int(np.argmax(total_vol))
    poc_price = float(bin_mid[poc_idx])

    # Bull %
    total_sum = total_vol.sum()
    bull_pct  = float(bull_vol.sum() / total_sum * 100) if total_sum > 0 else 50.0

    # Key support/resistance levels (top 5 high-volume bins excluding POC)
    top_indices = np.argsort(total_vol)[::-1]
    levels = []
    for idx in top_indices[:6]:
        if idx != poc_idx:
            levels.append(float(bin_mid[idx]))
    levels.sort()

    return {
        'poc_price': poc_price,
        'bull_pct':  bull_pct,
        'levels':    levels,
        'bin_mid':   bin_mid.tolist(),
        'bull_vol':  bull_vol.tolist(),
        'bear_vol':  bear_vol.tolist(),
    }


def score_day(poc: float, day_high: float, day_low: float, day_close: float, spot_prev: float) -> str:
    """Score how well price respected the POC level."""
    if poc <= 0:
        return 'NO_DATA'

    # Distance from POC to nearest intraday price
    dist_to_poc = min(abs(day_high - poc), abs(day_low - poc))
    if poc >= day_low and poc <= day_high:
        dist_to_poc = 0  # price passed through POC

    pct_dist = dist_to_poc / poc

    if pct_dist <= BULLSEYE_PCT:
        return 'BULLSEYE'
    elif pct_dist <= HIT_PCT:
        return 'HIT'
    elif pct_dist <= CLOSE_PCT:
        return 'CLOSE'
    else:
        return 'MISS'


def run_backtest(ticker: str) -> dict:
    """Run full Whale POC backtest for one ticker."""
    print(f"\n  [{ticker}] Fetching {WHALE_WINDOW + LOOKBACK_DAYS} bars...")

    tk   = yf.Ticker(ticker)
    hist = tk.history(period="2y", interval="1d", auto_adjust=True)

    if hist.empty or len(hist) < WHALE_WINDOW + LOOKBACK_DAYS:
        print(f"  [{ticker}] Insufficient data ({len(hist)} bars)")
        return {}

    hist = hist.copy()
    hist.index = pd.to_datetime(hist.index).tz_localize(None)

    results  = []
    # Slide over test window
    for i in range(WHALE_WINDOW, len(hist) - 1):
        train_bars = hist.iloc[i - WHALE_WINDOW:i]
        test_bar   = hist.iloc[i]
        test_date  = test_bar.name.date()

        # Only test trading days (not weekends — yfinance already filters these)
        whale_data = calc_whale_poc(train_bars)
        if not whale_data:
            continue

        poc        = whale_data['poc_price']
        day_high   = float(test_bar['High'])
        day_low    = float(test_bar['Low'])
        day_close  = float(test_bar['Close'])
        prev_close = float(hist.iloc[i-1]['Close'])

        # Sanity check: skip if POC is >25% away from spot (stale price regime)
        if abs(poc - prev_close) / prev_close > 0.25:
            continue

        score = score_day(poc, day_high, day_low, day_close, prev_close)

        # Is this expiry Friday?
        is_friday = test_bar.name.weekday() == 4

        results.append({
            'date':       str(test_date),
            'poc':        round(poc, 2),
            'open':       round(float(test_bar['Open']), 2),
            'high':       round(day_high, 2),
            'low':        round(day_low, 2),
            'close':      round(day_close, 2),
            'bull_pct':   round(whale_data['bull_pct'], 1),
            'score':      score,
            'is_friday':  is_friday,
            'poc_dist_pct': round(min(abs(day_high - poc), abs(day_low - poc)) / poc * 100 if poc > 0 else 999, 3)
        })

    if not results:
        return {}

    # ── Score summary ─────────────────────────────────────────
    recent = results[-LOOKBACK_DAYS:]
    score_counts = {'BULLSEYE': 0, 'HIT': 0, 'CLOSE': 0, 'MISS': 0, 'NO_DATA': 0}
    friday_scores = []
    for r in recent:
        score_counts[r['score']] += 1
        if r['is_friday']:
            friday_scores.append(r['score'])

    total    = len(recent)
    hit_rate = (score_counts['BULLSEYE'] + score_counts['HIT']) / total * 100 if total > 0 else 0
    pin_rate = (score_counts['BULLSEYE'] + score_counts['HIT'] + score_counts['CLOSE']) / total * 100 if total > 0 else 0

    friday_hit = (friday_scores.count('BULLSEYE') + friday_scores.count('HIT')) / len(friday_scores) * 100 if friday_scores else 0

    return {
        'ticker':       ticker,
        'days_tested':  total,
        'score_counts': score_counts,
        'hit_rate_pct': round(hit_rate, 1),
        'pin_rate_pct': round(pin_rate, 1),
        'friday_hit_pct': round(friday_hit, 1),
        'friday_days':  len(friday_scores),
        'recent':       recent[-10:]  # last 10 days for detail
    }


def build_report_chart(all_results: list) -> bytes:
    """Build a summary accuracy chart for all tickers."""
    tickers    = [r['ticker'] for r in all_results]
    hit_rates  = [r['hit_rate_pct'] for r in all_results]
    pin_rates  = [r['pin_rate_pct'] for r in all_results]
    fri_rates  = [r['friday_hit_pct'] for r in all_results]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), facecolor=DARK_BG)

    # ── Top: Hit Rate by Ticker ──────────────────────────────
    x = np.arange(len(tickers))
    w = 0.3
    b1 = ax1.bar(x - w, hit_rates,  w, label='BULLSEYE+HIT (≤0.75%)', color=GREEN,  alpha=0.88)
    b2 = ax1.bar(x,     pin_rates,  w, label='Pin Rate (≤1.5%)',       color=CYAN,   alpha=0.70)
    b3 = ax1.bar(x + w, fri_rates,  w, label='Friday Expiry Hit',      color=GOLD,   alpha=0.88)

    ax1.set_facecolor(PANEL_BG)
    ax1.set_xticks(x)
    ax1.set_xticklabels(tickers, color=WHITE, fontsize=10)
    ax1.set_ylabel('Accuracy %', color=DIM)
    ax1.set_ylim(0, 105)
    ax1.axhline(50, color=DIM, lw=0.8, ls='--', alpha=0.5)
    ax1.axhline(70, color=GOLD, lw=0.8, ls='--', alpha=0.4, label='70% target')
    ax1.tick_params(colors=DIM)
    for sp in ax1.spines.values(): sp.set_color('#1e2a3a')
    ax1.legend(fontsize=8, facecolor=DARK_BG, edgecolor='#1e2a3a', labelcolor=WHITE)
    ax1.set_title('WHALE POC ACCURACY — LAST 60 TRADING DAYS', color=WHITE, fontsize=11, pad=8)

    # Bar labels
    for bar in b1:
        h = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, h + 0.5, f'{h:.0f}%',
                 ha='center', va='bottom', fontsize=7, color=GREEN)

    # ── Bottom: Score breakdown stacked ──────────────────────
    bullseye = [r['score_counts']['BULLSEYE'] for r in all_results]
    hits     = [r['score_counts']['HIT']      for r in all_results]
    closes   = [r['score_counts']['CLOSE']    for r in all_results]
    misses   = [r['score_counts']['MISS']     for r in all_results]

    ax2.barh(tickers, bullseye, color='#00ff88', alpha=0.9, label='BULLSEYE (≤0.3%)')
    ax2.barh(tickers, hits,  left=bullseye, color=GREEN, alpha=0.85, label='HIT (≤0.75%)')
    ax2.barh(tickers, closes, left=[b+h for b,h in zip(bullseye,hits)], color=CYAN, alpha=0.65, label='CLOSE (≤1.5%)')
    ax2.barh(tickers, misses, left=[b+h+c for b,h,c in zip(bullseye,hits,closes)], color=RED, alpha=0.70, label='MISS')

    ax2.set_facecolor(PANEL_BG)
    ax2.tick_params(colors=WHITE, labelsize=9)
    for sp in ax2.spines.values(): sp.set_color('#1e2a3a')
    ax2.set_xlabel('Days', color=DIM)
    ax2.set_title('SCORE DISTRIBUTION BY TICKER (60 Days)', color=WHITE, fontsize=11, pad=8)
    ax2.legend(fontsize=8, facecolor=DARK_BG, edgecolor='#1e2a3a', labelcolor=WHITE, loc='lower right')

    fig.suptitle('🔱 TRISHULA Q-MATRIX — WHALE LIQUIDITY POC BACKTEST',
                 color=WHITE, fontsize=13, fontweight='bold', y=0.98)
    fig.patch.set_facecolor(DARK_BG)
    plt.tight_layout(rect=[0, 0, 1, 0.96])

    import io
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=130, facecolor=DARK_BG, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def main():
    print("=" * 65)
    print("  TRISHULA Q-MATRIX — WHALE LIQUIDITY POC BACKTEST")
    print(f"  Lookback: {LOOKBACK_DAYS} days | Whale Window: {WHALE_WINDOW} bars")
    print(f"  Tickers:  {', '.join(TICKERS)}")
    print("=" * 65)

    all_results = []

    for ticker in TICKERS:
        r = run_backtest(ticker)
        if not r:
            continue
        all_results.append(r)

        print(f"\n  [{ticker}] {'─' * 40}")
        print(f"    Days tested:      {r['days_tested']}")
        print(f"    BULLSEYE (≤0.3%): {r['score_counts']['BULLSEYE']} days")
        print(f"    HIT      (≤0.75%): {r['score_counts']['HIT']} days")
        print(f"    CLOSE    (≤1.5%): {r['score_counts']['CLOSE']} days")
        print(f"    MISS:             {r['score_counts']['MISS']} days")
        print(f"    Hit Rate:         {r['hit_rate_pct']}%  (BULLSEYE+HIT)")
        print(f"    Pin Rate:         {r['pin_rate_pct']}%  (within 1.5%)")
        print(f"    Friday Expiry:    {r['friday_hit_pct']}% hit  ({r['friday_days']} Fridays)")

        print(f"\n    Last 10 days:")
        print(f"    {'Date':<12} {'POC':>8} {'Low':>8} {'High':>8} {'Close':>8}  Score")
        print(f"    {'─'*58}")
        for day in r['recent'][-10:]:
            fri = ' [FRI]' if day['is_friday'] else ''
            score_emoji = {'BULLSEYE':'🎯','HIT':'✅','CLOSE':'🟡','MISS':'❌','NO_DATA':'⚪'}.get(day['score'],'?')
            print(f"    {day['date']:<12} ${day['poc']:>7.2f} ${day['low']:>7.2f} ${day['high']:>7.2f} ${day['close']:>7.2f}  {score_emoji} {day['score']}{fri}")

    if not all_results:
        print("\n[ERROR] No results generated")
        return

    # ── Aggregate stats ────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  AGGREGATE RESULTS")
    print("=" * 65)
    avg_hit = sum(r['hit_rate_pct'] for r in all_results) / len(all_results)
    avg_pin = sum(r['pin_rate_pct'] for r in all_results) / len(all_results)
    avg_fri = sum(r['friday_hit_pct'] for r in all_results) / len(all_results)

    print(f"  Average Hit Rate (BULLSEYE+HIT):  {avg_hit:.1f}%")
    print(f"  Average Pin Rate (within 1.5%):   {avg_pin:.1f}%")
    print(f"  Average Friday Expiry Hit Rate:   {avg_fri:.1f}%")

    verdict = "STRONG" if avg_hit >= 60 else ("MODERATE" if avg_hit >= 45 else "NEEDS CALIBRATION")
    print(f"\n  VERDICT: {verdict}")
    if avg_hit >= 60:
        print("  Whale POC is a reliable intraday gravity level.")
    elif avg_hit >= 45:
        print("  Whale POC has moderate predictive power — use with confluence.")
    else:
        print("  Whale POC needs parameter tuning (try different WHALE_PCT or N_BINS).")

    # ── Save results ──────────────────────────────────────────
    out_path = Path(__file__).parent / 'whale_backtest_results.json'
    with open(out_path, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n  Results saved: {out_path}")

    # ── Build chart ───────────────────────────────────────────
    chart_bytes = build_report_chart(all_results)
    chart_path  = Path(__file__).parent / 'whale_backtest_chart.png'
    with open(chart_path, 'wb') as f:
        f.write(chart_bytes)
    print(f"  Chart saved:   {chart_path}")

    # ── Post to Discord ───────────────────────────────────────
    try:
        import requests as _req
        WEBHOOK = "https://discord.com/api/webhooks/1508273976558882906/Scvp9yK6mmfrEJ7hMu38fJn24Fa7TljEeSs4tL0xHwfOIs_0P26mhrbaFuzwoxEgy5F5"
        summary_lines = []
        for r in sorted(all_results, key=lambda x: x['hit_rate_pct'], reverse=True):
            verdict_emoji = '🎯' if r['hit_rate_pct'] >= 60 else ('✅' if r['hit_rate_pct'] >= 45 else '🟡')
            summary_lines.append(
                f"{verdict_emoji} `{r['ticker']:<5}` Hit:`{r['hit_rate_pct']}%` Pin:`{r['pin_rate_pct']}%` Fri:`{r['friday_hit_pct']}%`"
            )
        embed = {
            "title": "🔱 WHALE POC BACKTEST — 60 Day Results",
            "description": "\n".join(summary_lines),
            "color": 0x00ddaa,
            "fields": [
                {"name": "Avg Hit Rate", "value": f"`{avg_hit:.1f}%`", "inline": True},
                {"name": "Avg Pin Rate", "value": f"`{avg_pin:.1f}%`", "inline": True},
                {"name": "Verdict",      "value": f"`{verdict}`",       "inline": True},
            ],
            "footer": {"text": "Q-Matrix Backtest Engine  ·  Trishula QuantNode"},
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        with open(chart_path, 'rb') as cf:
            _req.post(
                WEBHOOK,
                data={"payload_json": json.dumps({"embeds": [embed]})},
                files={"file": ("whale_backtest.png", cf, "image/png")},
                timeout=30
            )
        print("  Chart + results posted to Discord.")
    except Exception as e:
        print(f"  Discord post skipped: {e}")

    print("=" * 65)


if __name__ == "__main__":
    main()
