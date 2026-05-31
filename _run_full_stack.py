import sys, time
sys.path.insert(0, r'H:\Trishula\Swarm_4_Integration\Salvo_Staging')
import sovereign_options_scanner as s
from qmatrix_altmarkets import run_altmarkets_sweep
from qmatrix_earnings import run_earnings_sweep

STACK = [
    # ETFs
    "SPY", "QQQ", "IWM", "SOXL", "SMH", "IBIT", "GDX",
    # Mag-7
    "TSLA", "MSFT", "META", "AMZN", "AAPL", "GOOGL", "NVDA",
    # Mega-cap
    "AVGO", "CRWD", "CRWV", "NFLX", "TSM", "ADBE", "ARM", "NOW", "IBM",
    # Mid-cap
    "PLTR", "AMD", "INTC", "ORCL", "COIN", "MU", "APP", "MSTR", "NET", "RDDT", "DDOG", "ASTS", "IREN",
    # Commodities
    "GLD", "SLV",
    # Low-cap
    "SOFI", "RKLB", "HOOD", "SNAP", "MARA",
]

print(f"Stack: {len(STACK)} tickers")
for symbol in STACK:
    print(f"\n{'='*55}")
    print(f"  [{symbol}] Starting 6-panel run...")
    print(f"{'='*55}")
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
        print(f"  [{symbol}] All 6 panels fired.")
    except Exception as e:
        print(f"  [{symbol}] ERROR: {e}")
    time.sleep(s.DELAY_SECS)

print("\n[DONE] Equity stack complete. Running alt markets...")
run_altmarkets_sweep(s.WEBHOOK_CRYPTO, s.WEBHOOK_FOREX, s.WEBHOOK_FUTURES)
print("[DONE] Full sweep complete.")
