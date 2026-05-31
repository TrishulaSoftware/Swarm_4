import sys, time
sys.path.insert(0, r'H:\Trishula\Swarm_4_Integration\Salvo_Staging')
import sovereign_options_scanner as s

for symbol in ["GLD", "SLV"]:
    print(f"\n{'='*55}\n  [{symbol}] Starting 6-panel run...\n{'='*55}")
    try:
        tk  = s.yf.Ticker(symbol)
        exp = s.nearest_weekly_expiry(tk)
        if exp is None:
            print(f"  [{symbol}] No expiry — skipping.")
            continue
        print(f"  [{symbol}] Expiry: {exp}")
        d = s.process_ticker_with_expiry(symbol, exp)
        if d is None:
            print(f"  [{symbol}] No data — skipping.")
            continue
        print(f"  [{symbol}] Spot: ${d['spot']:.2f}  MaxPain: ${d['max_pain']:.0f}")
        buf = s.build_chart(d)
        s.send_to_discord(d, buf)
        time.sleep(2)
        s.send_enhanced_charts(symbol, d['spot'])
        print(f"  [{symbol}] ✓ All 6 panels fired.")
    except Exception as e:
        print(f"  [{symbol}] ERROR: {e}")
    time.sleep(s.DELAY_SECS)

print("\n[DONE] GLD + SLV complete.")
