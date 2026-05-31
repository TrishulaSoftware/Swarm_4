#!/usr/bin/env python3
"""
=============================================================
TRISHULA Q-MATRIX — PRODUCTION SCANNER INTEGRATION CHECK
=============================================================
Fires the native production process_ticker and send_to_discord
followed by the full enhanced charts pipeline to verify the
delivery of the complete 6-panel options package on TSLA.
=============================================================
"""
import sys
import os
import time

# Add staging and scratch directories to system paths
sys.path.insert(0, r'H:\Trishula\Swarm_4_Integration\Salvo_Staging')
sys.path.insert(0, r'H:\Trishula\Swarm_4_Integration\scratch')

import yfinance as yf
import sovereign_options_scanner as s

TEST_TICKER = "TSLA"

print("=" * 70)
print(f"  RUNNING COMPLETE 6-PANEL SWEEP TEST FIRE — Ticker: {TEST_TICKER}")
print("=" * 70)

try:
    print(f"\n[1/4] Processing ticker via native process_ticker...")
    data = s.process_ticker(TEST_TICKER)
    
    if data is None:
        print("  ❌ ERROR: process_ticker returned None")
        sys.exit(1)
        
    print(f"  ✅ Spot Price: ${data['spot']:.2f}")
    print(f"  ✅ Expiry: {data['expiry']}")
    print(f"  ✅ Max Pain: ${data['max_pain']:.0f}")
    print(f"  ✅ Net GEX: {'+' if data['net_gex_m'] >= 0 else ''}{data['net_gex_m']}M")
    
    print("\n[2/4] Building framed Master Options Heatmap chart (Panel 1)...")
    chart_buf = s.build_chart(data)
    print(f"  ✅ Chart buffer successfully generated ({len(chart_buf.getvalue())} bytes).")
    
    print("\n[3/4] Firing Panel 1 Master Embed & Chart directly to Discord...")
    s.send_to_discord(data, chart_buf)
    
    print("\n[4/4] Executing enhanced multi-expiry charts pipeline (Panels 2-6)...")
    # This fires GEX, IV Skew, Max Pain, Smart Flow, and Whale Profile images
    s.send_enhanced_charts(TEST_TICKER, data["spot"])
    
    print("\n" + "=" * 70)
    print("  🎉 SUCCESS: Complete 6-panel visual package successfully delivered to Discord!")
    print("=" * 70)

except Exception as e:
    print(f"\n  ❌ FATAL ERROR DURING RUN: {e}")
    sys.exit(1)
