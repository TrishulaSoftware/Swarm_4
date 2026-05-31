import json, sys
sys.stdout.reconfigure(encoding='utf-8')

data = json.load(open(r'H:\Trishula_SBM\DataMine\MLB\Team Props\05_18_2026\ledger_05_18_2026.json', encoding='utf-8'))
entries = data['entries']

print(f"Total entries: {len(entries)}")
print()
for e in entries:
    print(f"  [{e['id']}] {e.get('game','')} | pick={e.get('pick','')} | result={e.get('result','PENDING')}")
