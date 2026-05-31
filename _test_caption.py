import sys, time
sys.path.insert(0, r'H:\Trishula\Swarm_4_Integration\Salvo_Staging')
import sovereign_options_scanner as s

for symbol in ["ORCL", "NVDA"]:
    print(f"\n[{symbol}] Running...")
    tk  = s.yf.Ticker(symbol)
    exp = s.nearest_weekly_expiry(tk)
    d   = s.process_ticker_with_expiry(symbol, exp)
    if d:
        buf = s.build_chart(d)
        s.send_to_discord(d, buf)
        time.sleep(2)
        s.send_enhanced_charts(symbol, d['spot'])
        print(f"[{symbol}] Done.")
    time.sleep(s.DELAY_SECS)
