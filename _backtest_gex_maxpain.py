#!/usr/bin/env python3
"""
Pull Q-Matrix snapshots from Oracle DB1 + actual prices
Backtest GEX / MaxPain accuracy for May 22-23, 2026
"""
import os, json, requests
import yfinance as yf
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv(r'H:\Trishula\Swarm_4_Integration\Swarm_4_SBM_FINAL INTEGRATION\Project-Swarm\trishula-market-data\.env')

ORDS_BASE = os.getenv('ORDS_BASE_URL', '').rstrip('/')
DB1_USER  = os.getenv('ORACLE_DB1_USER', 'admin')
DB1_PASS  = os.getenv('ORACLE_DB1_PASSWORD', '')
WALLET    = r'H:\Trishula\Swarm_4_Integration\Salvo_Staging\oracle_wallet'

TARGET_DATES = ['2026-05-22', '2026-05-23']
TICKERS = ['SPY', 'QQQ', 'IWM', 'NVDA', 'TSLA', 'AAPL', 'AMZN', 'MSFT', 'SOXL', 'TNA']

print("=" * 65)
print("  TRISHULA Q-MATRIX BACKTEST — MAY 22-23, 2026")
print("=" * 65)

# ── Step 1: Pull stored snapshots from Oracle DB1 ──────────────
print("\n[1] Querying Oracle DB1 for stored snapshots...")
stored_data = {}

if ORDS_BASE:
    for d in TARGET_DATES:
        try:
            url = f"{ORDS_BASE}/qmatrix_snapshots/"
            params = {'q': json.dumps({"scan_date": d}), 'limit': 100}
            r = requests.get(url, auth=(DB1_USER, DB1_PASS), params=params, timeout=15)
            if r.status_code == 200:
                items = r.json().get('items', [])
                stored_data[d] = items
                print(f"  {d}: {len(items)} snapshots found in DB1")
            else:
                print(f"  {d}: ORDS returned {r.status_code} — {r.text[:80]}")
        except Exception as e:
            print(f"  {d}: {str(e)[:80]}")
else:
    print("  [WARN] ORDS_BASE_URL not set — checking log files instead")

# ── Step 2: Pull from scanner logs as fallback ─────────────────
print("\n[2] Scanning local log files for May 22-23 outputs...")
LOG_DIR = r'H:\Trishula\Swarm_4_Integration\Salvo_Staging\logs'
log_data = {}

import glob
for log_file in glob.glob(f'{LOG_DIR}/*.log'):
    try:
        lines = open(log_file, encoding='utf-8', errors='ignore').readlines()
        for i, line in enumerate(lines):
            if '2026-05-22' in line or '2026-05-23' in line or 'MaxPain' in line or 'GEX' in line:
                key = os.path.basename(log_file)
                if key not in log_data:
                    log_data[key] = []
                log_data[key].append(line.strip())
    except Exception:
        pass

if log_data:
    for fname, lines in log_data.items():
        print(f"  {fname}: {len(lines)} relevant lines")
        for line in lines[:5]:
            print(f"    {line[:100]}")
else:
    print("  No matching log lines found locally")

# ── Step 3: Pull actual OHLCV for May 22-23 ───────────────────
print("\n[3] Fetching actual price data (May 22-23)...")
price_data = {}

for ticker in TICKERS:
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(start='2026-05-22', end='2026-05-24', interval='1d')
        if not hist.empty:
            price_data[ticker] = {}
            for idx, row in hist.iterrows():
                d = idx.strftime('%Y-%m-%d')
                price_data[ticker][d] = {
                    'open':  round(row['Open'],  2),
                    'high':  round(row['High'],  2),
                    'low':   round(row['Low'],   2),
                    'close': round(row['Close'], 2),
                    'range': round(row['High'] - row['Low'], 2)
                }
    except Exception as e:
        price_data[ticker] = {'error': str(e)[:50]}

print(f"\n  {'Ticker':<8} {'Date':<12} {'Open':>7} {'High':>7} {'Low':>7} {'Close':>7} {'Range':>6}")
print("  " + "-" * 55)
for ticker in TICKERS:
    if ticker in price_data and isinstance(price_data[ticker], dict):
        for d, p in sorted(price_data[ticker].items()):
            if 'close' in p:
                print(f"  {ticker:<8} {d:<12} {p['open']:>7.2f} {p['high']:>7.2f} {p['low']:>7.2f} {p['close']:>7.2f} {p['range']:>6.2f}")

# ── Step 4: Intraday data for GEX/MaxPain pin analysis ────────
print("\n[4] Intraday analysis (did price pin to MaxPain?)...")
for ticker in ['SPY', 'QQQ', 'IWM']:
    try:
        tk = yf.Ticker(ticker)
        intra = tk.history(start='2026-05-22', end='2026-05-24', interval='5m')
        if not intra.empty:
            for d in TARGET_DATES:
                day_data = intra[intra.index.strftime('%Y-%m-%d') == d]
                if not day_data.empty:
                    open_p  = round(day_data.iloc[0]['Open'], 2)
                    close_p = round(day_data.iloc[-1]['Close'], 2)
                    high_p  = round(day_data['High'].max(), 2)
                    low_p   = round(day_data['Low'].min(), 2)
                    move    = round(((close_p - open_p) / open_p) * 100, 3)
                    print(f"\n  {ticker} {d}:")
                    print(f"    Open: {open_p}  High: {high_p}  Low: {low_p}  Close: {close_p}")
                    print(f"    Day move: {move:+.3f}%")
    except Exception as e:
        print(f"  {ticker}: {str(e)[:60]}")

# ── Step 5: Save for manual analysis ──────────────────────────
output = {'price_data': price_data, 'log_data': log_data, 'stored_snapshots': stored_data}
with open('backtest_may22_23.json', 'w') as f:
    json.dump(output, f, indent=2, default=str)
print("\n[OK] Saved: backtest_may22_23.json")
print("=" * 65)
print("  NOTE: GEX/MaxPain levels from Discord needed for accuracy score.")
print("  Pull those values from Discord history and I'll score them against actuals.")
print("=" * 65)
