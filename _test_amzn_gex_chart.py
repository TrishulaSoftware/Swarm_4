#!/usr/bin/env python3
"""
Test: Post AMZN GEX level chart to Discord (live data from yfinance).
"""
import sys
sys.path.insert(0, r"H:\Trishula\Swarm_4_Integration\Salvo_Staging")
import io, json, requests, datetime
import yfinance as yf
from _gex_level_chart import build_gex_level_chart

WEBHOOK = "https://discord.com/api/webhooks/1508274221644517446/_MDRuliSQdtgqsCCNRJcSq7PSbVP-t1eSWxZQGs27XomPNb53tMCXDVFL80OIBnDH0hz"
SYMBOL  = "AMZN"

print(f"[TEST] Fetching live data for {SYMBOL}...")
tk  = yf.Ticker(SYMBOL)
try:
    spot = float(tk.fast_info.last_price)
except Exception:
    hist = tk.history(period="1d")
    spot = float(hist["Close"].iloc[-1]) if not hist.empty else 195.00

# Options chain for Max Pain + Walls
expiry = None
try:
    from sovereign_options_scanner import nearest_weekly_expiry, process_ticker_with_expiry
    expiry = nearest_weekly_expiry(tk)
    d = process_ticker_with_expiry(SYMBOL, expiry) if expiry else None
    max_pain  = d["max_pain"]  if d else spot * 0.99
    call_wall = d["top_call_wall"] if d else spot * 1.02
    put_wall  = d["top_put_wall"]  if d else spot * 0.97
except Exception as e:
    print(f"  Scanner error: {e} — using estimates")
    max_pain  = round(spot * 0.992, 2)
    call_wall = round(spot * 1.025, 2)
    put_wall  = round(spot * 0.975, 2)
    expiry    = (datetime.date.today() + datetime.timedelta(days=5)).isoformat()

# Estimated GEX zero (slightly below spot — common in negative GEX regime)
gex_zero  = round(spot * 0.988, 2)
whale_poc = round(spot * 0.994, 2)
net_gex_m = -2.14  # negative GEX example

print(f"[TEST] Spot={spot:.2f} MaxPain={max_pain:.0f} CallWall={call_wall:.0f} PutWall={put_wall:.0f}")
print(f"[TEST] Generating GEX chart...")

buf = build_gex_level_chart(
    symbol    = SYMBOL,
    spot      = spot,
    max_pain  = max_pain,
    net_gex_m = net_gex_m,
    gex_zero  = gex_zero,
    whale_poc = whale_poc,
    call_wall = call_wall,
    put_wall  = put_wall,
    expiry    = expiry or "",
)

print(f"[TEST] Chart generated — {buf.getbuffer().nbytes:,} bytes")

# Post to Discord
buf.seek(0)
ts  = datetime.datetime.now().strftime("%b %d %Y  %I:%M %p ET")
caption = f"`AMZN` — GEX Level Map Test  ·  Live Chart  ·  {ts}"

r = requests.post(
    WEBHOOK,
    data={"payload_json": json.dumps({"content": caption})},
    files={"file": ("AMZN_gex_levels_test.png", buf, "image/png")},
    timeout=30,
)

if r.status_code in (200, 204):
    print(f"[TEST] ✅ Successfully posted AMZN GEX chart to Discord  (status={r.status_code})")
else:
    print(f"[TEST] ❌ Discord error {r.status_code}: {r.text[:200]}")

# Also save locally
buf.seek(0)
with open(r"H:\Trishula\Swarm_4_Integration\Salvo_Staging\amzn_gex_live_test.png", "wb") as f:
    f.write(buf.read())
print("[TEST] Saved locally: amzn_gex_live_test.png")
print("[TEST] Done.")
