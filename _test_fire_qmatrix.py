#!/usr/bin/env python3
"""
=============================================================
TRISHULA Q-MATRIX — TEST FIRE RUNNER (INTELLIGENT VOLUME FALLBACK)
=============================================================
Fires a single production-grade ticker run through the options
scanner, generates the structured 6-Panel chart, and pushes
it directly to the Discord webhook map.
=============================================================
"""
import sys
import os
import datetime

# Add staging to system path
sys.path.insert(0, r'H:\Trishula\Swarm_4_Integration\Salvo_Staging')

import yfinance as yf
import sovereign_options_scanner as s

# Target NVDA for a high-confluence Mag-7 test
TEST_TICKER = "NVDA"

print("=" * 65)
print(f"  STARTING Q-MATRIX TEST FIRE — Ticker: {TEST_TICKER}")
print("=" * 65)

try:
    print(f"\n[1/3] Fetching and processing option chain for {TEST_TICKER}...")
    tk = yf.Ticker(TEST_TICKER)
    
    # Smart Expiry Selector: Select the nearest Friday expiry, or at least a future expiry
    selected_expiry = None
    today_dt = datetime.date.today()
    
    for exp_str in tk.options:
        try:
            exp_dt = datetime.date.fromisoformat(exp_str)
            if exp_dt > today_dt:
                chain = tk.option_chain(exp_str)
                total_rows = len(chain.calls) + len(chain.puts)
                if total_rows > 20:
                    selected_expiry = exp_str
                    break
        except Exception:
            continue
            
    if not selected_expiry:
        if len(tk.options) > 1:
            selected_expiry = tk.options[1]
        else:
            selected_expiry = tk.options[0] if tk.options else None
        
    print(f"  Selected Active Expiry: {selected_expiry}")
    
    # Custom Process Ticker that implements Volume Fallback when OI is zero
    def process_ticker_with_fallback(symbol: str):
        print(f"  [{symbol}] Fetching data...")
        tk = yf.Ticker(symbol)

        try:
            spot = float(tk.fast_info.last_price)
        except Exception:
            hist = tk.history(period="1d")
            spot = float(hist["Close"].iloc[-1]) if not hist.empty else None
        if not spot:
            print(f"  [{symbol}] Could not fetch spot — skipping.")
            return None

        # Days to expiry
        exp_dt = datetime.datetime.strptime(selected_expiry, "%Y-%m-%d")
        T = max((exp_dt - datetime.datetime.now()).total_seconds() / (365.25 * 24 * 3600), 1/365)

        # Pull chain
        try:
            chain = tk.option_chain(selected_expiry)
            calls = chain.calls.fillna(0)
            puts  = chain.puts.fillna(0)
        except Exception as e:
            print(f"  [{symbol}] Chain error: {e} — skipping.")
            return None

        # Filter to ±STRIKE_RANGE of spot
        lo = spot * (1 - s.STRIKE_RANGE)
        hi = spot * (1 + s.STRIKE_RANGE)
        calls = calls[(calls["strike"] >= lo) & (calls["strike"] <= hi)].copy()
        puts  = puts[ (puts["strike"]  >= lo) & (puts["strike"]  <= hi)].copy()

        # Check if OI is zero. If so, copy Volume to OpenInterest to simulate a active-day volume sweep!
        if calls["openInterest"].sum() == 0 and puts["openInterest"].sum() == 0:
            print(f"  ⚠️ Warning: Open Interest is zero (after-hours/unpropagated). Falling back to Options Volume for calculations.")
            calls["openInterest"] = calls["volume"]
            puts["openInterest"] = puts["volume"]

        # Build dicts keyed by strike
        all_strikes = sorted(set(calls["strike"].tolist()) | set(puts["strike"].tolist()))

        call_oi  = dict(zip(calls["strike"], calls["openInterest"]))
        put_oi   = dict(zip(puts["strike"],  puts["openInterest"]))
        call_vol = dict(zip(calls["strike"], calls["volume"]))
        put_vol  = dict(zip(puts["strike"],  puts["volume"]))
        call_iv  = dict(zip(calls["strike"], calls["impliedVolatility"]))
        put_iv   = dict(zip(puts["strike"],  puts["impliedVolatility"]))

        # Totals
        tot_call_oi = sum(call_oi.values())
        tot_put_oi  = sum(put_oi.values())
        pc_ratio    = round(tot_put_oi / tot_call_oi, 2) if tot_call_oi > 0 else 0.0

        # Max Pain
        max_pain = s.compute_max_pain(all_strikes, call_oi, put_oi)

        # Net GEX ($M)
        net_gex = 0.0
        for K in all_strikes:
            iv_c = call_iv.get(K, 0.30) or 0.30
            iv_p = put_iv.get(K,  0.30) or 0.30
            g_c  = s.bs_gamma(spot, K, T, s.RFR, iv_c)
            g_p  = s.bs_gamma(spot, K, T, s.RFR, iv_p)
            net_gex += (call_oi.get(K, 0) * g_c - put_oi.get(K, 0) * g_p) * 100 * spot
        net_gex_m = round(net_gex / 1_000_000, 2)

        # Top call / put walls (by OI/Volume proxy)
        top_call_wall = max(call_oi, key=call_oi.get) if call_oi else spot
        top_put_wall  = max(put_oi,  key=put_oi.get)  if put_oi  else spot

        # Flow anomalies
        anomalies = []
        for K in all_strikes:
            for side, oi_d, vol_d in [("CALL", call_oi, call_vol), ("PUT", put_oi, put_vol)]:
                oi_val  = oi_d.get(K, 0)
                vol_val = vol_d.get(K, 0)
                if oi_val > 0 and vol_val > 300 and vol_val / oi_val > 2.0:
                    anomalies.append((side, K, round(vol_val / oi_val, 1), int(vol_val)))
        anomalies.sort(key=lambda x: x[2], reverse=True)

        return {
            "symbol":       symbol,
            "spot":         spot,
            "expiry":       selected_expiry,
            "T":            T,
            "strikes":      all_strikes,
            "call_oi":      call_oi,
            "put_oi":       put_oi,
            "call_vol":     call_vol,
            "put_vol":      put_vol,
            "max_pain":     max_pain,
            "net_gex_m":    net_gex_m,
            "pc_ratio":     pc_ratio,
            "top_call_wall":top_call_wall,
            "top_put_wall": top_put_wall,
            "tot_call_oi":  int(tot_call_oi),
            "tot_put_oi":   int(tot_put_oi),
            "anomalies":    anomalies[:5],
        }

    # Execute custom pipeline with fallback
    data = process_ticker_with_fallback(TEST_TICKER)
    
    if data is None:
        print(f"  ❌ ERROR: Failed to gather data for {TEST_TICKER}. Exiting.")
        sys.exit(1)
        
    print(f"  ✅ Spot Price: ${data['spot']:.2f}")
    print(f"  ✅ Expiry: {data['expiry']}")
    print(f"  ✅ Max Pain: ${data['max_pain']:.0f}")
    print(f"  ✅ Net GEX: {'+' if data['net_gex_m'] >= 0 else ''}{data['net_gex_m']}M")
    print(f"  ✅ P/C Ratio: {data['pc_ratio']}")
    print(f"  ✅ Top Call Wall: ${data['top_call_wall']:.0f}")
    print(f"  ✅ Top Put Wall: ${data['top_put_wall']:.0f}")
    
    if data['anomalies']:
        print(f"  ✅ Anomalies Flagged: {len(data['anomalies'])}")
        for side, K, ratio, vol in data['anomalies']:
            print(f"    • {side} Strike ${K:.0f} | Vol/OI Ratio: {ratio}x | Vol: {vol}")

    print(f"\n[2/3] Building framed 6-panel chart...")
    # Build core heatmap chart
    raw_chart = s.build_chart(data)
    
    # Wrap with beautiful branding header
    meta = s._CHART_META["heatmap"]
    framed_chart = s._add_chart_header(
        raw_chart, 
        symbol=TEST_TICKER, 
        chart_type=meta[0], 
        description=meta[1], 
        accent=meta[2]
    )
    print("  ✅ Chart built and framed successfully.")

    # Get target webhook
    target_webhook = s.get_webhook(symbol=TEST_TICKER)
    obfuscated_webhook = target_webhook[:45] + "..." + target_webhook[-15:]
    print(f"  ✅ Routing to Discord Webhook: {obfuscated_webhook}")

    print(f"\n[3/3] Firing payload to Discord...")
    # Dispatch
    s.send_image_to_discord(
        framed_chart, 
        filename=f"{TEST_TICKER}_heatmap.png", 
        caption=f"⚡ **Q-MATRIX PRODUCTION TEST FIRE (VOLUME FALLBACK ACTIVE)** ⚡\n"
                f"**Ticker:** `{TEST_TICKER}` | **Spot:** `${data['spot']:.2f}`\n"
                f"**Expiry:** `{data['expiry']}`\n"
                f"**Max Pain:** `${data['max_pain']:.0f}` | **Net GEX:** `{'+' if data['net_gex_m'] >= 0 else ''}{data['net_gex_m']}M` | **P/C Ratio:** `{data['pc_ratio']}`\n"
                f"**Top Call Wall:** `${data['top_call_wall']:.0f}` | **Top Put Wall:** `${data['top_put_wall']:.0f}`",
        symbol=TEST_TICKER
    )
    
    print("\n" + "=" * 65)
    print("  🎉 SUCCESS: Test fire completed. Check your Discord channels!")
    print("=" * 65)

except Exception as e:
    print(f"\n  ❌ FATAL ERROR DURING RUN: {e}")
    sys.exit(1)
