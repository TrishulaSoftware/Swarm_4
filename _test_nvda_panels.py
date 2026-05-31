import sys
sys.path.insert(0, r'H:\Trishula\Swarm_4_Integration\Salvo_Staging')
import time
import sovereign_options_scanner as s

tk  = s.yf.Ticker('NVDA')
exp = s.nearest_weekly_expiry(tk)
print(f'Expiry: {exp}')

d = s.process_ticker_with_expiry('NVDA', exp)
if d:
    print(f'Spot: {d["spot"]}  MaxPain: {d["max_pain"]}')
    buf = s.build_chart(d)
    s.send_to_discord(d, buf)
    time.sleep(2)
    s.send_enhanced_charts('NVDA', d['spot'])
    print('All 5 panels fired.')
else:
    print('No data returned.')
