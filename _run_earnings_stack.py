"""Add CRM, SNOW, OKTA, MDB to routing map and fire full 6-panel suite."""
import sys, time
sys.path.insert(0, r'H:\Trishula\Swarm_4_Integration\Salvo_Staging')

# ── Patch routing map for earnings tickers ─────────────────────────────────
path = r'H:\Trishula\Swarm_4_Integration\Salvo_Staging\sovereign_options_scanner.py'
src  = open(path, encoding='utf-8').read()

ANCHOR = '"SNAP": WEBHOOK_LOWCAP,'
ADDITIONS = '''
    # ── Earnings watch (week of May 27) ──────────────────────────────────────
    "CRM":  WEBHOOK_MEGACAP,   # Salesforce — reports May 27
    "SNOW": WEBHOOK_MIDCAP,    # Snowflake  — reports May 27
    "OKTA": WEBHOOK_MIDCAP,    # Okta       — reports May 28
    "MDB":  WEBHOOK_MIDCAP,    # MongoDB    — reports May 28'''

if '"CRM"' not in src:
    src = src.replace(ANCHOR, ANCHOR + ADDITIONS)
    open(path, 'w', encoding='utf-8').write(src)
    print("Routing map updated: CRM, SNOW, OKTA, MDB added.")
else:
    print("Already in routing map.")

# ── Fire full 6-panel suite for each ──────────────────────────────────────────
import sovereign_options_scanner as s

EARNINGS_STACK = ["CRM", "SNOW", "OKTA", "MDB"]

for symbol in EARNINGS_STACK:
    print(f"\n{'='*55}")
    print(f"  [{symbol}] EARNINGS WEEK — Starting 6-panel run...")
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

print("\n[DONE] Earnings stack complete.")
