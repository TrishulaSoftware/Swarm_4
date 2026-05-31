# -*- coding: utf-8 -*-
"""
TRISHULA SWARM -- PARLAY GENERATOR
Builds and dispatches 3 structured parlays from the daily pick pool.
"""

import requests, time
from config import WEBHOOKS, SWARM_IDENTITY, COLORS
from datetime import date

SLATE_DATE = date.today().strftime("%B %d, %Y")
WEBHOOK = WEBHOOKS["mlb_parlays"]

# ============================================================
# Odds Conversion Utilities
# ============================================================
def american_to_decimal(american):
    a = int(str(american).replace("+", ""))
    if american > 0:
        return round((a / 100) + 1, 4)
    else:
        return round((100 / abs(a)) + 1, 4)

def decimal_to_american(decimal):
    if decimal >= 2.0:
        return f"+{round((decimal - 1) * 100)}"
    else:
        return f"{round(-100 / (decimal - 1))}"

def parlay_odds(legs):
    """Takes list of american odds ints, returns combined american odds string."""
    product = 1.0
    for leg in legs:
        product *= american_to_decimal(leg)
    return decimal_to_american(product), round(product, 2)

# ============================================================
# PARLAY DEFINITIONS
# ============================================================

PARLAYS = [
    {
        "name": "LOCK PARLAY",
        "tag": "PARLAY 1 -- LOCK TIER (3-LEG)",
        "description": "3-leg high-conviction parlay. Every pick 88%+ confidence. The three clearest dominant edges on the board.",
        "color": COLORS["lock"],
        "legs": [
            {"game": "TOR @ NYY",  "pick": "NYY Run Line (-1.5)", "odds": -200, "conf": "92%", "note": "LOCK. NYY dominant at home, TOR bats completely silent."},
            {"game": "CIN @ PHI",  "pick": "PHI Moneyline",       "odds": -120, "conf": "88%", "note": "Sharp money flowing in + elite home environment at Citizens Bank."},
            {"game": "CWS @ SEA",  "pick": "SEA Run Line (-1.5)", "odds": -174, "conf": "88%", "note": "Complete mismatch. SEA controls this game from the first pitch."},
        ]
    },
    {
        "name": "VALUE PARLAY",
        "tag": "PARLAY 2 -- VALUE DOGS (2-LEG)",
        "description": "2-leg plus-money value parlay. Two undervalued dogs the system has conviction on. Clean, disciplined, big upside.",
        "color": COLORS["alt_props"],
        "legs": [
            {"game": "CLE @ DET",  "pick": "CLE Moneyline", "odds": +130, "conf": "72%", "note": "H2H edge massive. Plus-money value vs an overvalued DET home price."},
            {"game": "NYM @ WSH",  "pick": "WSH Moneyline", "odds": +120, "conf": "65%", "note": "System dog. NYM severely overvalued on the road against this lineup."},
        ]
    },
    {
        "name": "NRFI/YRFI PROP PARLAY",
        "tag": "PARLAY 3 -- 1ST INNING PROPS (3-LEG)",
        "description": "3-leg 1st Inning prop parlay. Coors YRFI lock + Wrigley NRFI + MIN dome YRFI. Pure pitcher and park factor intelligence.",
        "color": 3066993,
        "legs": [
            {"game": "TEX @ COL", "pick": "YRFI (o0.5)", "odds": -166, "conf": "92%", "note": "LOCK. Coors Field. Breaking balls have zero bite in the thin air."},
            {"game": "MIL @ CHC", "pick": "NRFI (u0.5)", "odds": -128, "conf": "88%", "note": "Wind howling straight in at Wrigley. Two elite K-artists in frame 1."},
            {"game": "HOU @ MIN", "pick": "YRFI (o0.5)", "odds": -142, "conf": "85%", "note": "Both SPs carry bloated 1st-inning ERA. Dome. Runs expected early."},
        ]
    }
]


# ============================================================
# Build Discord Embeds
# ============================================================
def build_parlay_embed(p):
    leg_odds = [leg["odds"] for leg in p["legs"]]
    combined_american, combined_decimal = parlay_odds(leg_odds)

    fields = []
    for i, leg in enumerate(p["legs"]):
        dec = american_to_decimal(leg["odds"])
        fields.append({
            "name": f"Leg {i+1} -- {leg['game']}",
            "value": (
                f"**Pick:** {leg['pick']}\n"
                f"**Odds:** `{'+' + str(leg['odds']) if leg['odds'] > 0 else leg['odds']}` "
                f"(Decimal: {dec})\n"
                f"**Conf:** {leg['conf']}\n"
                f"_{leg['note']}_"
            ),
            "inline": False
        })

    fields.append({
        "name": "COMBINED PARLAY ODDS",
        "value": (
            f"**American:** `{combined_american}`\n"
            f"**Decimal:** `{combined_decimal}x`\n"
            f"**$100 bet returns:** `${round(100 * combined_decimal, 2)}`\n"
            f"**$50 bet returns:** `${round(50 * combined_decimal, 2)}`"
        ),
        "inline": False
    })

    return {
        "title": f"[TRISHULA] {p['tag']} -- {SLATE_DATE}",
        "description": p["description"],
        "color": p["color"],
        "fields": fields,
        "footer": {"text": f"Trishula Sovereign Swarm | Parlays | {SLATE_DATE}"}
    }

# ============================================================
# HTML Generation
# ============================================================
def export_html():
    file_path = fr"H:\Trishula_SBM\DataMine\MLB\Team Props\mlb_parlays_{date.today().strftime('%m%d%Y')}.html"
    
    html_content = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Trishula Parlays — {SLATE_DATE}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0d1117;color:#e6edf3;font-family:'Inter',sans-serif;padding:32px;min-height:100vh}}
h1{{font-size:2.2rem;font-weight:900;margin-bottom:6px;text-transform:uppercase;letter-spacing:1px;background:-webkit-linear-gradient(45deg,#f0c040,#ff7b72);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.meta{{color:#8b949e;font-size:.9rem;margin-bottom:28px;font-weight:600}}
.parlay-container{{display:flex;flex-direction:column;gap:28px}}
.pcard{{background:rgba(22,27,34,0.8);border:1px solid rgba(255,255,255,0.05);border-radius:12px;padding:24px;display:flex;flex-direction:column;gap:16px;}}
.pcard.lock{{border:1px solid rgba(240,192,64,0.3); background:rgba(240,192,64,0.02);}}
.pcard.value{{border:1px solid rgba(63,185,80,0.3); background:rgba(63,185,80,0.02);}}
.pcard.props{{border:1px solid rgba(56,139,253,0.3); background:rgba(56,139,253,0.02);}}
.p-header{{display:flex;justify-content:space-between;align-items:flex-start}}
.p-title{{font-size:1.2rem;font-weight:900;text-transform:uppercase;letter-spacing:.5px}}
.pcard.lock .p-title{{color:#f0c040}}
.pcard.value .p-title{{color:#3fb950}}
.pcard.props .p-title{{color:#58a6ff}}
.p-desc{{font-size:.8rem;color:#8b949e;line-height:1.5;margin-bottom:8px;}}
table{{width:100%;border-collapse:collapse;margin-bottom:12px;}}
th{{text-align:left;padding:8px 12px;color:#8b949e;font-size:0.7rem;text-transform:uppercase;border-bottom:1px solid rgba(255,255,255,0.1);}}
td{{padding:12px;border-bottom:1px solid rgba(255,255,255,0.05);vertical-align:top;}}
.leg-num{{font-size:0.65rem;font-weight:900;color:#8b949e;text-transform:uppercase;}}
.leg-game{{font-size:0.8rem;color:#c9d1d9;font-weight:600;margin-top:2px;}}
.leg-pick{{font-size:0.95rem;font-weight:800;color:#ffffff;}}
.leg-odds{{font-size:0.85rem;font-weight:900;padding:2px 6px;border-radius:4px;background:rgba(255,255,255,0.1);margin-left:6px;}}
.leg-conf{{font-size:0.75rem;color:#3fb950;font-weight:700;display:block;margin-top:2px;}}
.leg-note{{font-size:0.75rem;color:#8b949e;font-style:italic;line-height:1.4;}}
.payout-box{{background:rgba(0,0,0,0.2);border-radius:8px;padding:16px;border:1px solid rgba(255,255,255,0.05);display:flex;justify-content:space-between;align-items:center;}}
.payout-title{{font-size:0.7rem;font-weight:900;text-transform:uppercase;color:#8b949e;}}
.payout-odds{{font-size:1.8rem;font-weight:900;margin-top:4px;}}
.pcard.lock .payout-odds{{color:#f0c040}}
.pcard.value .payout-odds{{color:#3fb950}}
.pcard.props .payout-odds{{color:#58a6ff}}
.payout-dec{{font-size:0.75rem;color:#8b949e;font-weight:600;}}
.payout-grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px;min-width:200px;}}
.payout-row{{background:rgba(255,255,255,0.04);border-radius:6px;padding:8px 12px;display:flex;justify-content:space-between;align-items:center;}}
.payout-label{{font-size:0.65rem;color:#8b949e;font-weight:700;text-transform:uppercase;}}
.payout-val{{font-size:0.95rem;font-weight:900;color:#e6edf3;}}
.ledger-tag{{display:flex;align-items:center;gap:8px;padding:10px 12px;background:rgba(138,43,226,0.08);border:1px solid rgba(138,43,226,0.2);border-radius:8px}}
.ledger-dot{{width:8px;height:8px;border-radius:50%;background:#d2a8ff;flex-shrink:0;animation:pulse 2s infinite}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.4}}}}
.ledger-text{{font-size:.75rem;color:#d2a8ff;font-weight:700}}
.ledger-result{{margin-left:auto;font-size:.7rem;background:rgba(255,255,255,0.05);border-radius:4px;padding:2px 8px;color:#8b949e;font-weight:700}}
</style></head><body>
<h1>Trishula Parlay Board</h1>
<p class="meta">3 Structured Parlays · {SLATE_DATE} · Ledger Tracked</p>
<div class="parlay-container">
"""
    for i, p in enumerate(PARLAYS):
        leg_odds = [leg["odds"] for leg in p["legs"]]
        combined_american, combined_decimal = parlay_odds(leg_odds)
        
        type_class = "lock" if i == 0 else ("value" if i == 1 else "props")
        
        legs_html = "<table><thead><tr><th>Leg / Matchup</th><th>The Pick</th><th>Analysis</th></tr></thead><tbody>"
        for j, leg in enumerate(p["legs"]):
            legs_html += f"""
            <tr>
              <td style="width:25%">
                <div class="leg-num">LEG {j+1}</div>
                <div class="leg-game">{leg['game']}</div>
              </td>
              <td style="width:35%">
                <span class="leg-pick">{leg['pick']}</span><span class="leg-odds">{'+'+str(leg['odds']) if leg['odds']>0 else leg['odds']}</span>
                <span class="leg-conf">Confidence: {leg['conf']}</span>
              </td>
              <td style="width:40%">
                <div class="leg-note">{leg['note']}</div>
              </td>
            </tr>"""
        legs_html += "</tbody></table>"

        html_content += f"""
        <div class="pcard {type_class}">
          <div class="p-header">
            <div class="p-title">{p['name']}</div>
          </div>
          <div class="p-desc">{p['description']}</div>
          {legs_html}
          <div class="payout-box">
            <div>
                <div class="payout-title">Combined Odds & Payout</div>
                <div class="payout-odds">{combined_american}</div>
                <div class="payout-dec">Decimal Multiplier: {combined_decimal}x</div>
            </div>
            <div class="payout-grid">
              <div class="payout-row"><span class="payout-label">$50 Bet</span><span class="payout-val">${round(50 * combined_decimal, 2)}</span></div>
              <div class="payout-row"><span class="payout-label">$100 Bet</span><span class="payout-val">${round(100 * combined_decimal, 2)}</span></div>
            </div>
          </div>
          <div class="ledger-tag">
            <div class="ledger-dot"></div>
            <div class="ledger-text">TRISHULA LEDGER — Tracking Active</div>
            <div class="ledger-result">PENDING</div>
          </div>
        </div>"""

    html_content += "</div></body></html>"
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"[OK] Generated HTML: {file_path}")
    
    return file_path

# ============================================================
# Playwright Screenshot & Discord Image Upload
# ============================================================
def post_html_screenshot(html_path):
    import time
    from playwright.sync_api import sync_playwright
    
    png_path = html_path.replace(".html", ".png")
    
    print("  [WAIT] Booting Headless Browser to screenshot HTML...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 850, "height": 1000})
        # using file:// protocol to render local HTML
        page.goto(f"file:///{html_path.replace(chr(92), '/')}") 
        # Wait a moment for fonts/CSS to load
        time.sleep(1)
        page.screenshot(path=png_path, full_page=True)
        browser.close()
        
    print(f"  [OK] Saved PNG: {png_path}")
    
    print("  [WAIT] Uploading Image to Discord Webhook...")
    with open(png_path, "rb") as f:
        files = {"file": (png_path.split("\\")[-1], f, "image/png")}
        payload = {"content": f"**SOCIAL MEDIA ASSET READY**\nGenerated `{png_path.split(chr(92))[-1]}`"}
        r = requests.post(WEBHOOK, data=payload, files=files)
        
        if r.status_code in [200, 204]:
            print("  [OK] Image uploaded to Discord successfully.")
        else:
            print(f"  [ERR] Failed to upload image: {r.status_code} {r.text}")


# ============================================================
# Dispatch
# ============================================================
def dispatch_parlays():
    print("\n" + "="*55)
    print("  TRISHULA SWARM -- PARLAY DISPATCH")
    print(f"  {SLATE_DATE}")
    print("="*55 + "\n")

    # embeds = [build_parlay_embed(p) for p in PARLAYS]

    # payload = {
    #     **SWARM_IDENTITY,
    #     "content": f"**[TRISHULA PARLAYS] -- {SLATE_DATE.upper()}**\n3 Structured Parlays | Lock + Value + Alt Props",
    #     "embeds": embeds
    # }

    # r = requests.post(WEBHOOK, json=payload)
    # if r.status_code == 204:
    #     print("[OK] All 3 parlays dispatched successfully.")
    # else:
    #     print(f"[ERR] {r.status_code}: {r.text}")

    # Print summary to console
    print("\n--- PARLAY SUMMARY ---")
    for p in PARLAYS:
        leg_odds = [leg["odds"] for leg in p["legs"]]
        combined, decimal = parlay_odds(leg_odds)
        legs_str = " + ".join([l["pick"] for l in p["legs"]])
        print(f"\n{p['name']} ({len(p['legs'])} legs)")
        print(f"  Legs: {legs_str}")
        print(f"  Combined Odds: {combined} ({decimal}x)")
        print(f"  $100 wins: ${round(100 * decimal, 2)}")

    # Generate HTML automatically
    html_file = export_html()
    
    # Render and post the screenshot to Discord
    post_html_screenshot(html_file)

if __name__ == "__main__":
    dispatch_parlays()
