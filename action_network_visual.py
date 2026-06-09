"""
action_network_visual.py  v3
==============================
Clean best-line-only dashboard.
Per game shows: Best ML Away, Best ML Home, Best Spread, Best Over, Best Under
with which book has it. No full book tables.
"""

import json
from datetime import date
from pathlib import Path

DATE_STR  = date.today().strftime("%Y%m%d")
JSON_FILE = f"action_network_{DATE_STR}.json"

BOOK_NAMES = {
    15:"bet365", 30:"DraftKings", 79:"FanDuel", 1368:"BetMGM",
    1963:"Caesars", 1964:"PointsBet", 1968:"Barstool", 1969:"Unibet",
    2401:"WynnBET", 2988:"ESPN Bet", 4523:"Fanatics",
}
PERIODS = {"event":"Game", "firstfive":"First 5", "firstinning":"First Inn"}

# ── Helpers ───────────────────────────────────────────────────────────────────

def fo(v):
    """Format American odds."""
    if v is None: return "—"
    try:
        i = int(v)
        return f"+{i}" if i > 0 else str(i)
    except: return "—"

def fs(v):
    """Format spread value."""
    if v is None: return "—"
    try:
        f = float(v)
        return f"+{f:.1f}" if f > 0 else f"{f:.1f}"
    except: return "—"

def ft(v):
    """Format total."""
    if v is None: return "—"
    try: return f"{float(v):.1f}"
    except: return "—"

def best(books: dict, field: str, limit: int = 800):
    """Best (highest) odds for a field across all books. Returns (odds, book_id)."""
    bv = None
    bb = None
    for bid, b in books.items():
        v = b.get(field)
        if v is None: continue
        try:
            if abs(int(v)) > limit: continue
            if bv is None or int(v) > int(bv):
                bv, bb = v, bid
        except: continue
    return bv, bb

def avg_pct(books: dict, field: str):
    """Average percentage across books that have it."""
    vals = [b[field] for b in books.values() if b.get(field)]
    return round(sum(vals)/len(vals)) if vals else None

def signal(tkt, mny):
    if tkt is None or mny is None: return None, None
    diff = (mny or 0) - (tkt or 0)
    if diff >= 15:     return "sharp",  f"⚡ Sharp money on this side (+{diff}% vs tickets)"
    if diff <= -15:    return "fade",   f"🔴 Public far ahead of sharp money ({diff}%)"
    if (tkt or 0) >= 75: return "steam", f"🔥 Heavy public consensus ({int(tkt)}% of tickets)"
    return None, None

def book_name(bid):
    try: return BOOK_NAMES.get(int(bid), f"Book {bid}")
    except: return str(bid)

# ── Build bet card (single best-line item) ────────────────────────────────────

def bet_card(label, icon, odds_val, extra_val, book_id, cls=""):
    bn   = book_name(book_id) if book_id else "—"
    odds = fo(odds_val)
    extra = f"<span class='bet-extra'>{extra_val}</span>" if extra_val and extra_val != "—" else ""
    return f"""<div class="bet-card {cls}">
      <div class="bet-label">{icon} {label}</div>
      <div class="bet-odds">{extra}{odds}</div>
      <div class="bet-book">{bn}</div>
    </div>"""

# ── Build period section ───────────────────────────────────────────────────────

def build_period(books: dict, away: str, home: str) -> str:
    if not books:
        return '<p class="no-data">No odds yet — check back pre-game</p>'

    # Best lines
    ml_a_val,  ml_a_book  = best(books, "ml_away")
    ml_h_val,  ml_h_book  = best(books, "ml_home")
    spd_val,   spd_book   = best(books, "spread_away_odds")
    ov_val,    ov_book    = best(books, "over_odds")
    un_val,    un_book    = best(books, "under_odds")

    # Get the spread line value from the best-odds book
    spd_line = "—"
    if spd_book and spd_book in books:
        spd_line = fs(books[spd_book].get("spread_away_val"))

    # Get the total line value
    tot_line = "—"
    for b in books.values():
        if b.get("total_val") is not None:
            tot_line = ft(b["total_val"])
            break

    # Public/money consensus (average across books)
    avg_tkt = avg_pct(books, "ml_away_tickets")
    avg_mny = avg_pct(books, "ml_away_money")
    sig_type, sig_msg = signal(avg_tkt, avg_mny)

    sig_html = ""
    if sig_type:
        sig_html = f'<div class="signal-bar sig-{sig_type}">{sig_msg}</div>'

    # Consensus bar
    tkt_w = max(3, min(int(avg_tkt or 0), 100))
    mny_w = max(3, min(int(avg_mny or 0), 100))
    pub_html = ""
    if avg_tkt or avg_mny:
        pub_html = f"""<div class="consensus">
          <div class="con-row">
            <span class="con-label">🎟 Tickets ({away})</span>
            <div class="con-bar-wrap">
              <div class="con-bar" style="width:{tkt_w}%;background:#4f8ef7"></div>
              <span class="con-val">{int(avg_tkt)}%</span>
            </div>
          </div>
          <div class="con-row">
            <span class="con-label">💵 Money ({away})</span>
            <div class="con-bar-wrap">
              <div class="con-bar" style="width:{mny_w}%;background:#f7a94f"></div>
              <span class="con-val">{int(avg_mny)}%</span>
            </div>
          </div>
        </div>"""

    return f"""
    {sig_html}
    <div class="bets-grid">
      {bet_card(f'{away} ML',   '🏠', ml_a_val, None,     ml_a_book, 'away')}
      {bet_card(f'{home} ML',   '🏠', ml_h_val, None,     ml_h_book, 'home')}
      {bet_card('Spread',       '📐', spd_val,  spd_line, spd_book)}
      {bet_card('Over',         '⬆️', ov_val,   f'O{tot_line}', ov_book,  'over')}
      {bet_card('Under',        '⬇️', un_val,   f'U{tot_line}', un_book,  'under')}
    </div>
    {pub_html}"""

# ── Build game card ────────────────────────────────────────────────────────────

def build_game_card(g: dict) -> str:
    away, home = g["away"], g["home"]
    start      = g["start"]
    status     = g.get("status") or "scheduled"
    status_cls = "scheduled" if status in ("scheduled","None","") or not status else "live"
    time_str   = start[11:16] + " ET" if len(start) > 11 else start
    pd         = g["period_data"]

    tabs = panels = ""
    first = True
    for p_key, p_label in PERIODS.items():
        books  = pd.get(p_key, {})
        pid    = f"{away}{home}{p_key}".replace(" ","")
        active = "active" if first else ""
        tabs  += f'<button class="tab-btn {active}" onclick="switchTab(this,\'{pid}\')">{p_label}</button>'
        panels += f'<div class="tab-panel {active}" id="{pid}">{build_period(books, away, home)}</div>'
        first   = False

    return f"""<div class="game-card">
      <div class="game-header">
        <div class="matchup">
          <span class="team away">{away}</span>
          <span class="vs">@</span>
          <span class="team home">{home}</span>
        </div>
        <div class="meta">
          <span class="game-time">{time_str}</span>
          <span class="status {status_cls}">{status}</span>
        </div>
      </div>
      <div class="tabs">{tabs}</div>
      <div class="panels">{panels}</div>
    </div>"""

# ── Generate HTML ─────────────────────────────────────────────────────────────

def generate():
    with open(JSON_FILE, encoding="utf-8") as f:
        data = json.load(f)
    parsed = data.get("parsed", [])
    cards  = "\n".join(build_game_card(g) for g in parsed)
    today  = date.today().strftime("%A, %B %d, %Y")
    n_live = sum(1 for g in parsed if g.get("status") and g["status"] not in ("scheduled","None",""))

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Trishula — MLB Best Lines {today}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:#080b12;--surface:#0f1623;--surface2:#141d2c;--border:#1a2740;
  --accent:#3b82f6;--text:#e2e8f0;--muted:#4b6180;
  --away:#93c5fd;--home:#c4b5fd;--gold:#f59e0b;--green:#22c55e;--red:#ef4444;
}}
body{{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;padding:28px 16px 80px}}

/* HEADER */
.page-header{{text-align:center;margin-bottom:36px;padding:36px 20px;background:linear-gradient(160deg,rgba(59,130,246,.08),rgba(167,139,250,.05),transparent);border:1px solid var(--border);border-radius:20px}}
.page-header h1{{font-size:2.4rem;font-weight:900;background:linear-gradient(135deg,#60a5fa 30%,#a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:-1.5px}}
.sub{{color:var(--muted);font-size:.82rem;margin-top:8px;letter-spacing:.4px}}
.stats-row{{display:flex;justify-content:center;gap:40px;margin-top:24px;flex-wrap:wrap}}
.stat .val{{font-size:2rem;font-weight:900;background:linear-gradient(135deg,#60a5fa,#a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.stat .lbl{{font-size:.65rem;color:var(--muted);letter-spacing:.8px;text-transform:uppercase;margin-top:2px}}
.pulse{{display:inline-block;width:7px;height:7px;border-radius:50%;background:#22c55e;margin-right:5px;animation:pulse 1.5s infinite}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.4}}}}

/* GRID */
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(480px,1fr));gap:16px;max-width:1600px;margin:0 auto}}

/* GAME CARD */
.game-card{{background:var(--surface);border:1px solid var(--border);border-radius:16px;overflow:hidden;transition:transform .2s,box-shadow .2s}}
.game-card:hover{{transform:translateY(-2px);box-shadow:0 10px 40px rgba(59,130,246,.12)}}

.game-header{{display:flex;justify-content:space-between;align-items:center;padding:16px 20px;background:var(--surface2);border-bottom:1px solid var(--border)}}
.matchup{{display:flex;align-items:center;gap:10px}}
.team{{font-size:1.3rem;font-weight:900;letter-spacing:-.5px}}
.team.away{{color:var(--away)}}.team.home{{color:var(--home)}}
.vs{{color:var(--muted);font-size:.85rem}}
.meta{{display:flex;flex-direction:column;align-items:flex-end;gap:4px}}
.game-time{{font-size:.72rem;color:var(--muted);font-weight:600;letter-spacing:.3px}}
.status{{font-size:.62rem;font-weight:800;padding:2px 9px;border-radius:99px;letter-spacing:.8px;text-transform:uppercase}}
.status.live{{background:rgba(239,68,68,.15);color:#f87171;border:1px solid rgba(239,68,68,.25)}}
.status.scheduled{{background:rgba(34,197,94,.10);color:#4ade80;border:1px solid rgba(34,197,94,.2)}}

/* TABS */
.tabs{{display:flex;gap:2px;padding:10px 16px 0;border-bottom:1px solid var(--border)}}
.tab-btn{{background:transparent;border:none;color:var(--muted);font-family:inherit;font-size:.7rem;font-weight:700;padding:5px 12px 8px;border-radius:6px 6px 0 0;cursor:pointer;transition:all .15s;border-bottom:2px solid transparent;letter-spacing:.5px;text-transform:uppercase}}
.tab-btn:hover{{color:var(--text)}}
.tab-btn.active{{color:var(--accent);border-bottom-color:var(--accent);background:rgba(59,130,246,.07)}}

/* PANELS */
.tab-panel{{display:none;padding:16px}}.tab-panel.active{{display:block}}

/* SIGNAL BAR */
.signal-bar{{padding:8px 14px;border-radius:8px;font-size:.75rem;font-weight:600;margin-bottom:14px;letter-spacing:.2px}}
.sig-sharp{{background:rgba(59,130,246,.12);border:1px solid rgba(59,130,246,.25);color:#93c5fd}}
.sig-steam{{background:rgba(245,158,11,.10);border:1px solid rgba(245,158,11,.25);color:#fbbf24}}
.sig-fade{{background:rgba(239,68,68,.10);border:1px solid rgba(239,68,68,.25);color:#f87171}}

/* BET CARDS GRID */
.bets-grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:16px}}

/* INDIVIDUAL BET CARD */
.bet-card{{background:var(--surface2);border:1px solid var(--border);border-radius:10px;padding:12px 10px;text-align:center;transition:border-color .2s}}
.bet-card:hover{{border-color:var(--accent)}}
.bet-label{{font-size:.63rem;font-weight:700;color:var(--muted);letter-spacing:.6px;text-transform:uppercase;margin-bottom:8px}}
.bet-odds{{font-size:1.2rem;font-weight:900;letter-spacing:-.5px;line-height:1.2}}
.bet-extra{{font-size:.75rem;font-weight:600;color:var(--gold);display:block;margin-bottom:2px}}
.bet-book{{font-size:.65rem;color:var(--muted);margin-top:6px;font-weight:500}}

.bet-card.away .bet-odds{{color:var(--away)}}
.bet-card.home .bet-odds{{color:var(--home)}}
.bet-card.over .bet-odds{{color:#4ade80}}
.bet-card.under .bet-odds{{color:#f87171}}
.bet-card:not(.away):not(.home):not(.over):not(.under) .bet-odds{{color:var(--gold)}}

/* CONSENSUS BARS */
.consensus{{display:flex;flex-direction:column;gap:8px;padding:12px 14px;background:rgba(255,255,255,.02);border:1px solid var(--border);border-radius:10px}}
.con-row{{display:flex;align-items:center;gap:10px}}
.con-label{{font-size:.67rem;color:var(--muted);font-weight:600;min-width:130px;letter-spacing:.2px}}
.con-bar-wrap{{flex:1;display:flex;align-items:center;gap:8px}}
.con-bar{{height:6px;border-radius:3px;min-width:3px;max-width:180px;transition:width .4s}}
.con-val{{font-size:.72rem;font-weight:700;color:var(--text);min-width:28px}}

.no-data{{color:var(--muted);font-size:.8rem;text-align:center;padding:20px 0}}
</style>
</head>
<body>

<div class="page-header">
  <h1>⚾ MLB Best Lines</h1>
  <p class="sub"><span class="pulse"></span>{today} &nbsp;·&nbsp; Best odds across 11 books &nbsp;·&nbsp; Action Network</p>
  <div class="stats-row">
    <div class="stat"><div class="val">{len(parsed)}</div><div class="lbl">Games</div></div>
    <div class="stat"><div class="val">{n_live}</div><div class="lbl">Live</div></div>
    <div class="stat"><div class="val">11</div><div class="lbl">Books</div></div>
    <div class="stat"><div class="val">3</div><div class="lbl">Markets</div></div>
  </div>
</div>

<div class="grid">
{cards}
</div>

<script>
function switchTab(btn,id){{
  const c=btn.closest('.game-card');
  c.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
  c.querySelectorAll('.tab-panel').forEach(p=>p.classList.remove('active'));
  btn.classList.add('active');
  const el=document.getElementById(id);
  if(el) el.classList.add('active');
}}
</script>
</body></html>"""

    out = "action_network_dashboard.html"
    Path(out).write_text(html, encoding="utf-8")
    print(f"[DONE] -> {out}  ({len(parsed)} games, {n_live} live)")

if __name__ == "__main__":
    generate()
