#!/usr/bin/env python3
from _db1_persistence import count_snapshots, save_snapshot

print('[DB1] Testing connection...')
n = count_snapshots()
print(f'[DB1] Snapshots stored: {n}')

test_d = {
    'symbol': 'SPY',
    'spot': 750.0,
    'expiry': '2026-05-30',
    'max_pain': 749.0,
    'top_call_wall': 755.0,
    'top_put_wall': 745.0,
    'net_gex_m': 12.5,
    'pc_ratio': 0.87,
    'anomalies': []
}
ok = save_snapshot(test_d)
result = 'OK' if ok else 'FAILED'
print(f'[DB1] Test write: {result}')

n2 = count_snapshots()
print(f'[DB1] Snapshots after write: {n2}')
