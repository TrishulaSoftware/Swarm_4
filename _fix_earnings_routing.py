"""
Patches the routing for earnings tickers (CRM, SNOW, OKTA, MDB)
to use WEBHOOK_EARNINGS instead of their default channels.
Earnings week packages belong in #qm-earnings only.
"""
path = r'H:\Trishula\Swarm_4_Integration\Salvo_Staging\sovereign_options_scanner.py'
src  = open(path, encoding='utf-8').read()

old = '''\n    # ── Earnings watch (week of May 27) ──────────────────────────────────────
    "CRM":  WEBHOOK_MEGACAP,   # Salesforce — reports May 27
    "SNOW": WEBHOOK_MIDCAP,    # Snowflake  — reports May 27
    "OKTA": WEBHOOK_MIDCAP,    # Okta       — reports May 28
    "MDB":  WEBHOOK_MIDCAP,    # MongoDB    — reports May 28'''

new = '''\n    # ── Earnings watch (week of May 27) — routes to #qm-earnings ────────────
    "CRM":  WEBHOOK_EARNINGS,  # Salesforce — reports May 27
    "SNOW": WEBHOOK_EARNINGS,  # Snowflake  — reports May 27
    "OKTA": WEBHOOK_EARNINGS,  # Okta       — reports May 28
    "MDB":  WEBHOOK_EARNINGS,  # MongoDB    — reports May 28'''

if old in src:
    open(path, 'w', encoding='utf-8').write(src.replace(old, new, 1))
    print("Routing fixed: CRM/SNOW/OKTA/MDB -> WEBHOOK_EARNINGS")
else:
    print("Pattern not found — checking current state:")
    for line in src.split('\n'):
        if any(t in line for t in ['"CRM"', '"SNOW"', '"OKTA"', '"MDB"']):
            print(' ', line)
