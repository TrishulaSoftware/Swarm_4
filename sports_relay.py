#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=================================================================
TRISHULA SPORTS RELAY — MIDNIGHT INTERFACE
=================================================================
Accepts picks in multiple formats, normalizes them, writes to
Oracle DB1, posts to Discord, and prints a confirmation summary.

USAGE:
  python sports_relay.py                  # interactive prompt
  python sports_relay.py --file picks.json
  python sports_relay.py --text "LAL -5.5 (-110) 2u HIGH"
  python sports_relay.py --csv picks.csv

FORMAT EXAMPLES:
  JSON:  [{"sport":"NBA","game":"LAL vs GSW","pick_side":"LAL",
           "pick_type":"SPREAD","line_value":-5.5,"odds":-110,
           "confidence":"HIGH","units":2.0}]

  TEXT (quick entry):
    'LAL -5.5 (-110) 2u HIGH'            → SPREAD
    'KC ML (-130) 1.5u LOCK'             → ML
    'OVER 225.5 (-110) 1u MEDIUM NFL'    → TOTAL
    Each line = one pick. Sport auto-detected or specify at end.

  CSV:
    sport,game,pick_side,pick_type,line_value,odds,confidence,units,notes
    NBA,LAL vs GSW,LAL,SPREAD,-5.5,-110,HIGH,2.0,Strong fade spot

INTERACTIVE:
  Paste JSON, TEXT lines, or CSV. End with blank line (or Ctrl+Z on Windows).
  Type 'quit' to exit without posting.
=================================================================
"""

import sys, os, json, re, csv, io, argparse, datetime, time

# Add parent dir to path so we can import siblings
_BASE = os.path.dirname(os.path.abspath(__file__))
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)

from _sports_ingestion import ingest_picks_batch, get_record_summary
from _sports_discord   import post_picks_batch, post_daily_record


# ── Constants ────────────────────────────────────────────────

VALID_SPORTS  = {"NFL","NBA","MLB","NHL","NCAAF","NCAAB","SOCCER","MMA"}
VALID_TYPES   = {"ML","SPREAD","TOTAL","PROP","PARLAY"}
VALID_CONF    = {"HIGH","MEDIUM","LOW","LOCK"}

# Common team abbreviations → sport mapping for auto-detect
_SPORT_HINTS = {
    "NFL": {"KC","BUF","DAL","PHI","GB","SF","LAR","SEA","MIA","NE","PIT","BAL","CIN","CLE",
            "DEN","LV","LAC","HOU","TEN","IND","JAX","NYJ","NYG","WAS","CHI","DET","MIN",
            "ATL","NO","TB","CAR","ARI","LAR"},
    "NBA": {"LAL","GSW","BOS","MIA","PHX","DEN","MIL","BKN","NYK","CHI","CLE","PHI","TOR",
            "ATL","IND","WAS","CHA","ORL","DET","SAC","POR","UTA","OKC","MEM","NOP","HOU",
            "SAS","MIN","DAL","LAC"},
    "MLB": {"NYY","BOS","LAD","SF","CHC","ATL","HOU","OAK","ATH","SEA","TB","TOR","BAL",
            "CLE","DET","MIN","KC","CWS","TEX","LAA","ARI","SD","COL","MIL","STL","CHC",
            "CIN","PIT","NYM","PHI","WSH","MIA","ATL"},
    "NHL": {"TOR","MTL","BOS","NYR","PIT","WSH","EDM","CGY","VAN","LAK","VGK","COL","MIN",
            "STL","CHI","DET","BUF","OTT","TBL","FLA","CAR","NJD","NYI","PHI","ARI","CBJ",
            "SJS","ANA","NSH","WPG"},
}


# ── Parsers ──────────────────────────────────────────────────

def _detect_sport(text: str, pick_side: str = "") -> str:
    """Try to detect sport from text or pick_side team abbreviation."""
    upper_text = text.upper()
    for sport, teams in _SPORT_HINTS.items():
        for team in teams:
            if team in upper_text or (pick_side and team == pick_side.upper()):
                return sport
    # Check explicit sport mentions
    for sport in VALID_SPORTS:
        if sport in upper_text:
            return sport
    return "NBA"  # safe default


def _parse_odds(s: str):
    """Parse odds string like '-110' or '+150' → int."""
    s = s.strip().replace("(","").replace(")","")
    try:
        return int(s)
    except ValueError:
        return None


def _parse_units(s: str):
    """Parse units string like '2u' or '2.5u' → float."""
    s = s.strip().lower().replace("u","")
    try:
        return float(s)
    except ValueError:
        return 1.0


def parse_text_line(line: str, default_sport: str = None) -> dict | None:
    """
    Parse a free-text pick line into a normalized pick dict.

    Formats:
      'LAL -5.5 (-110) 2u HIGH'
      'KC ML (-130) 1.5u LOCK'
      'OVER 225.5 (-110) 1u MEDIUM NBA'
      'BOS vs MIA BOS -3.5 (-110) 2u HIGH NFL'

    Returns dict or None if unparseable.
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    tokens = line.split()
    pick = {
        "sport":      default_sport or "",
        "game":       "",
        "pick_side":  "",
        "pick_type":  "ML",
        "line_value": None,
        "odds":       None,
        "confidence": "MEDIUM",
        "units":      1.0,
        "notes":      line,
        "source":     "relay_text",
    }

    # Extract confidence level (HIGH/MEDIUM/LOW/LOCK) — usually last
    for tok in reversed(tokens):
        if tok.upper() in VALID_CONF:
            pick["confidence"] = tok.upper()
            tokens.remove(tok)
            break

    # Extract sport (if present)
    for tok in reversed(tokens):
        if tok.upper() in VALID_SPORTS:
            pick["sport"] = tok.upper()
            tokens.remove(tok)
            break

    # Extract units (e.g. '2u', '1.5u')
    for tok in tokens[:]:
        if re.match(r"^\d+(\.\d+)?u$", tok.lower()):
            pick["units"] = _parse_units(tok)
            tokens.remove(tok)
            break

    # Extract odds (e.g. '-110', '(+150)', '-130')
    for tok in tokens[:]:
        clean = tok.replace("(","").replace(")","")
        if re.match(r"^[+-]?\d{2,4}$", clean):
            v = _parse_odds(clean)
            if v is not None and abs(v) >= 100:
                pick["odds"] = v
                tokens.remove(tok)
                break

    # Detect OVER/UNDER
    for tok in tokens[:]:
        if tok.upper() in ("OVER", "UNDER", "O", "U"):
            pick["pick_type"] = "TOTAL"
            pick["pick_side"] = "OVER" if tok.upper() in ("OVER","O") else "UNDER"
            tokens.remove(tok)
            break

    # Extract line value (spread or total number like '-5.5', '225.5')
    for tok in tokens[:]:
        m = re.match(r"^([+-]?\d+\.?\d*)$", tok)
        if m:
            try:
                pick["line_value"] = float(m.group(1))
                tokens.remove(tok)
                break
            except ValueError:
                pass

    # Detect 'ML' keyword
    for tok in tokens[:]:
        if tok.upper() == "ML":
            pick["pick_type"] = "ML"
            tokens.remove(tok)
            break

    # Detect game format 'TEAM vs TEAM' or 'TEAM @ TEAM'
    game_match = re.search(r"([A-Z]{2,6})\s+(?:vs\.?|@)\s+([A-Z]{2,6})", line.upper())
    if game_match:
        t1, t2 = game_match.group(1), game_match.group(2)
        pick["game"] = f"{t1} vs {t2}"
        # Remove game tokens
        for tok in tokens[:]:
            if tok.upper() in (t1, t2, "VS", "VS.", "@"):
                tokens.remove(tok)

    # Remaining tokens: first should be pick_side
    if not pick["pick_side"] and tokens:
        pick["pick_side"] = tokens[0].upper()
        tokens = tokens[1:]

    # If no game set, use pick_side as team
    if not pick["game"] and pick["pick_side"]:
        pick["game"] = pick["pick_side"]

    # Auto-detect sport if not set
    if not pick["sport"]:
        pick["sport"] = _detect_sport(line, pick["pick_side"])

    # Infer pick_type from line_value if not set
    if pick["pick_type"] == "ML" and pick["line_value"] is not None:
        pick["pick_type"] = "SPREAD"

    return pick


def parse_json_input(raw: str) -> list:
    """Parse a JSON array or single JSON object into list of pick dicts."""
    data = json.loads(raw)
    if isinstance(data, dict):
        data = [data]
    return data


def parse_csv_input(raw: str) -> list:
    """Parse CSV string into list of pick dicts."""
    picks = []
    reader = csv.DictReader(io.StringIO(raw.strip()))
    for row in reader:
        p = {k.strip(): v.strip() for k, v in row.items()}
        # Normalize numeric fields
        for field in ("line_value", "odds", "units", "profit_loss"):
            if field in p and p[field]:
                try:
                    p[field] = float(p[field])
                except ValueError:
                    pass
        picks.append(p)
    return picks


def parse_text_block(raw: str, default_sport: str = None) -> list:
    """Parse multi-line text block — one pick per line."""
    picks = []
    for line in raw.splitlines():
        p = parse_text_line(line, default_sport=default_sport)
        if p:
            picks.append(p)
    return picks


def detect_format(raw: str) -> str:
    """Auto-detect input format: 'json', 'csv', or 'text'."""
    stripped = raw.strip()
    if stripped.startswith("[") or stripped.startswith("{"):
        return "json"
    # CSV: first line has commas and contains column names
    first_line = stripped.splitlines()[0] if stripped else ""
    if "," in first_line and any(kw in first_line.lower() for kw in ("sport","game","pick","odds")):
        return "csv"
    return "text"


# ── Normalizer ───────────────────────────────────────────────

def normalize_pick(p: dict) -> dict:
    """Normalize and validate a pick dict. Returns cleaned dict."""
    n = dict(p)

    # Sport
    sport = str(n.get("sport", "")).upper().strip()
    if sport not in VALID_SPORTS:
        sport = _detect_sport(str(n), str(n.get("pick_side","")))
    n["sport"] = sport

    # Pick type
    pt = str(n.get("pick_type", "ML")).upper().strip()
    n["pick_type"] = pt if pt in VALID_TYPES else "ML"

    # Confidence
    conf = str(n.get("confidence", "MEDIUM")).upper().strip()
    n["confidence"] = conf if conf in VALID_CONF else "MEDIUM"

    # Numerics
    for field in ("line_value", "odds", "units", "profit_loss"):
        v = n.get(field)
        if v is not None and str(v).strip() not in ("", "None"):
            try:
                n[field] = float(v)
            except (ValueError, TypeError):
                n[field] = None

    # Strings
    for field in ("game", "pick_side", "notes", "source"):
        n[field] = str(n.get(field, "") or "").strip()

    n.setdefault("source", "relay")
    n.setdefault("result", "PENDING")

    return n


# ── Main Relay ───────────────────────────────────────────────

def relay(
    raw: str,
    sport_hint: str = None,
    post_discord: bool = True,
    dry_run: bool = False,
) -> dict:
    """
    Full relay pipeline:
      1. Detect format
      2. Parse → normalize picks
      3. Write to DB1
      4. Post to Discord
      5. Return summary

    Returns: {
      "picks":     list of normalized dicts,
      "db_results": list of {ok, id, error},
      "discord_ok": bool,
      "summary":   str
    }
    """
    # ── Parse ────────────────────────────────────────────────
    fmt = detect_format(raw)
    print(f"\n  [RELAY] Detected format: {fmt.upper()}")

    try:
        if fmt == "json":
            picks = parse_json_input(raw)
        elif fmt == "csv":
            picks = parse_csv_input(raw)
        else:
            picks = parse_text_block(raw, default_sport=sport_hint)
    except Exception as e:
        print(f"  [RELAY] Parse error: {e}")
        return {"picks": [], "db_results": [], "discord_ok": False, "summary": f"Parse error: {e}"}

    if not picks:
        print("  [RELAY] No picks parsed.")
        return {"picks": [], "db_results": [], "discord_ok": False, "summary": "No picks parsed"}

    # ── Normalize ────────────────────────────────────────────
    picks = [normalize_pick(p) for p in picks]
    print(f"  [RELAY] {len(picks)} pick(s) parsed and normalized")

    # ── Preview ──────────────────────────────────────────────
    print("\n  ┌── Pick Preview " + "─" * 40)
    for i, p in enumerate(picks, 1):
        line_str = f" {p['line_value']:+g}" if p.get("line_value") is not None else ""
        odds_str = f" ({'+' if (p.get('odds') or 0) > 0 else ''}{p.get('odds', '?')})" if p.get("odds") else ""
        print(f"  │ #{i} {p['sport']:6} | {p.get('game','?')[:25]:25} | {p['pick_side']:12} | "
              f"{p['pick_type']:7}{line_str}{odds_str} | {p.get('units',1)}u | {p['confidence']}")
    print("  └" + "─" * 55)

    if dry_run:
        print("\n  [DRY RUN] Skipping DB write and Discord post.")
        return {"picks": picks, "db_results": [], "discord_ok": False,
                "summary": f"DRY RUN — {len(picks)} picks parsed OK"}

    # ── Write to DB1 ─────────────────────────────────────────
    print(f"\n  [RELAY] Writing {len(picks)} pick(s) to Oracle DB1...")
    db_results = ingest_picks_batch(picks)
    saved_count = sum(1 for r in db_results if r.get("ok"))
    failed_count = len(db_results) - saved_count
    print(f"  [RELAY] DB1: {saved_count} saved, {failed_count} failed")

    # ── Post to Discord ──────────────────────────────────────
    discord_ok = False
    if post_discord:
        print(f"\n  [RELAY] Posting to Discord...")
        if len(picks) == 1:
            from _sports_discord import post_pick
            discord_ok = post_pick(picks[0])
        else:
            discord_ok = post_picks_batch(picks)
        time.sleep(1)
        # Also post updated daily record
        post_daily_record()

    # ── Summary ──────────────────────────────────────────────
    summary_lines = [
        f"",
        f"  ╔══ RELAY COMPLETE ══╗",
        f"  ║ Picks parsed :  {len(picks)}",
        f"  ║ DB1 saved    :  {saved_count}/{len(picks)}",
        f"  ║ Discord      :  {'✅ OK' if discord_ok else '⚠️  skipped/failed'}",
        f"  ╚{'═' * 20}╝",
        f"",
    ]
    for line in summary_lines:
        print(line)

    return {
        "picks":      picks,
        "db_results": db_results,
        "discord_ok": discord_ok,
        "summary":    "\n".join(summary_lines),
    }


# ── CLI Entry Point ──────────────────────────────────────────

def _read_stdin_block() -> str:
    """Read multi-line input from stdin until blank line or EOF."""
    print("\n  Paste your picks (JSON, text lines, or CSV).")
    print("  End with a blank line or Ctrl+Z (Windows) / Ctrl+D (Unix).")
    print("  Type 'quit' to exit.\n")
    lines = []
    try:
        while True:
            line = input()
            if line.strip().lower() == "quit":
                sys.exit(0)
            if line.strip() == "" and lines:
                break
            lines.append(line)
    except EOFError:
        pass
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Trishula Sports Relay — midnight pick ingestion interface"
    )
    parser.add_argument("--file",    type=str, help="Path to JSON or CSV file")
    parser.add_argument("--text",    type=str, help="Quick text pick(s)")
    parser.add_argument("--sport",   type=str, help="Sport hint for text parsing")
    parser.add_argument("--dry-run", action="store_true", help="Parse only, skip DB+Discord")
    parser.add_argument("--no-discord", action="store_true", help="Skip Discord post")
    args = parser.parse_args()

    print("\n" + "="*55)
    print("  🎯 TRISHULA SPORTS RELAY — MIDNIGHT INTERFACE")
    print(f"  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*55)

    # Get raw input
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            raw = f.read()
        print(f"  [RELAY] Loaded from file: {args.file}")
    elif args.text:
        raw = args.text
    else:
        raw = _read_stdin_block()

    if not raw.strip():
        print("  [RELAY] No input provided. Exiting.")
        sys.exit(0)

    result = relay(
        raw,
        sport_hint   = args.sport,
        post_discord = not args.no_discord,
        dry_run      = args.dry_run,
    )

    sys.exit(0 if result["db_results"] else 1)


if __name__ == "__main__":
    main()
