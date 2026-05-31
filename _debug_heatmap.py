import sys, io, json, datetime, requests
sys.path.insert(0, r'H:\Trishula\Swarm_4_Integration\Salvo_Staging')
import sovereign_options_scanner as s

tk  = s.yf.Ticker('NVDA')
exp = s.nearest_weekly_expiry(tk)
d   = s.process_ticker_with_expiry('NVDA', exp)

label, desc, _ = s._CHART_META['heatmap']
now   = datetime.datetime.now()
hr    = now.hour
sweep = "🔔 Market Open" if hr < 11 else ("🕛 Midday" if hr < 14 else "⚡ Power Hour")
ts    = now.strftime("%b %d %Y  %I:%M %p ET")
caption = f"**{d['symbol']}  —  {label}**  `{sweep}  ·  {ts}`\n{desc}"

print(f"Caption length: {len(caption)}")
print(f"Caption: {caption[:200]}")

webhook = s.get_webhook(symbol='NVDA')
buf = s.build_chart(d)
buf.seek(0)
payload = {"content": caption}
r = requests.post(webhook,
    data={"payload_json": json.dumps(payload)},
    files={"file": ("test_heatmap.png", buf, "image/png")},
    timeout=30)
print(f"Status: {r.status_code}")
if r.status_code not in (200, 204):
    print(f"Error body: {r.text[:500]}")
else:
    print("OK — caption should appear above image in #mag-7")
