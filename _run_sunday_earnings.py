"""
Q-MATRIX SUNDAY EARNINGS SWEEP
================================
Runs every Sunday at 12:00 PM.
1. Scans full watchlist for this week's earnings reporters
2. Posts earnings calendar dashboard to #qm-earnings
3. Fires full 6-panel Q-Matrix package for each reporter -> #qm-earnings
"""
import sys, time
sys.path.insert(0, r'H:\Trishula\Swarm_4_Integration\Salvo_Staging')
import sovereign_options_scanner as s
from qmatrix_earnings import run_earnings_sweep, WATCHLIST

WEBHOOK_EARNINGS = s.WEBHOOK_EARNINGS

# ── Step 1: Scan + post earnings calendar dashboard ───────────────────────────
print("[SUNDAY] Running earnings calendar scan...")
earnings_list = run_earnings_sweep(WEBHOOK_EARNINGS, WATCHLIST)

if not earnings_list:
    print("[SUNDAY] No earnings this week in watchlist. Done.")
    sys.exit(0)

# ── Step 2: Full 6-panel Q-Matrix package for each reporter ───────────────────
print(f"\n[SUNDAY] Firing 6-panel package for {len(earnings_list)} earnings tickers...")
time.sleep(3)

for item in earnings_list:
    symbol = item["symbol"]
    earn_date = item["date"]
    print(f"\n{'='*55}")
    print(f"  [{symbol}] EARNINGS {earn_date} — Starting 6-panel run...")
    print(f"{'='*55}")
    try:
        # Temporarily override webhook to EARNINGS channel
        original_map = s._TICKER_WEBHOOK_MAP.copy()
        s._TICKER_WEBHOOK_MAP[symbol] = WEBHOOK_EARNINGS

        tk  = s.yf.Ticker(symbol)
        exp = s.nearest_weekly_expiry(tk)
        if exp is None:
            print(f"  [{symbol}] No expiry — skipping.")
            s._TICKER_WEBHOOK_MAP = original_map
            continue
        print(f"  [{symbol}] Expiry: {exp}  |  Reports: {earn_date}")
        d = s.process_ticker_with_expiry(symbol, exp)
        if d is None:
            print(f"  [{symbol}] No data — skipping.")
            s._TICKER_WEBHOOK_MAP = original_map
            continue
        print(f"  [{symbol}] Spot: ${d['spot']:.2f}  MaxPain: ${d['max_pain']:.0f}")
        buf = s.build_chart(d)
        s.send_to_discord(d, buf)
        time.sleep(2)
        s.send_enhanced_charts(symbol, d['spot'])
        print(f"  [{symbol}] All 6 panels fired -> #qm-earnings")

        # Restore original map
        s._TICKER_WEBHOOK_MAP = original_map

    except Exception as e:
        print(f"  [{symbol}] ERROR: {e}")
    time.sleep(s.DELAY_SECS)

print("\n[SUNDAY] Earnings sweep complete.")
