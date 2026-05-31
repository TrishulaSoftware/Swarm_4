#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=================================================================
TRISHULA SPORTS INGESTION MODULE
=================================================================
Handles all DB1 read/write for sports_picks table.
Table: sports_picks (Oracle DB1 — trishulapicks)
ORDS REST endpoint auto-enabled.

Functions:
  ingest_pick(...)         — write single pick
  ingest_picks_batch(...)  — write list of pick dicts
  get_picks(...)           — query picks with filters
  update_result(...)       — mark WIN/LOSS/PUSH + PnL
  get_record_summary()     — W/L/P/ROI/units_profit
=================================================================
"""
import os, requests, datetime
from pathlib import Path

# ── ORDS Config ──────────────────────────────────────────────
_ORDS_BASE = "https://g275356d1414552-trishulapicks.adb.us-ashburn-1.oraclecloudapps.com/ords/admin"
_ORDS_USER = "ADMIN"
_ORDS_PASS = "C1iffyHu5tl3!!!"
_TABLE     = "sports_picks"

VALID_SPORTS    = {"NFL", "NBA", "MLB", "NHL", "NCAAF", "NCAAB", "SOCCER", "MMA"}
VALID_TYPES     = {"ML", "SPREAD", "TOTAL", "PROP", "PARLAY"}
VALID_CONF      = {"HIGH", "MEDIUM", "LOW", "LOCK"}
VALID_RESULTS   = {"WIN", "LOSS", "PUSH", "PENDING"}


# ── Internal Helpers ─────────────────────────────────────────

def _auth():
    return (_ORDS_USER, _ORDS_PASS)


def _sql_exec(stmt: str) -> tuple:
    """Execute SQL via ORDS /_/sql. Returns (ok: bool, error: str)."""
    try:
        r = requests.post(
            f"{_ORDS_BASE}/_/sql",
            auth=_auth(),
            json={"statementText": stmt.strip()},
            timeout=20,
        )
        if r.status_code in (200, 201):
            body = r.json()
            for item in body.get("items", []):
                err = item.get("errorDetails", "")
                if err:
                    return False, err[:200]
            return True, ""
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)[:120]


def _safe(v) -> str:
    """Escape a string for SQL single-quote embedding."""
    return str(v).replace("'", "''") if v is not None else ""


def _n(v) -> str:
    """Return SQL numeric literal or NULL."""
    try:
        return str(float(v)) if v is not None and str(v).strip() != "" else "NULL"
    except (ValueError, TypeError):
        return "NULL"


# ── Write Operations ─────────────────────────────────────────

def ingest_pick(
    sport: str,
    game: str,
    pick_side: str,
    pick_type: str,
    odds,
    confidence: str,
    units,
    line_value=None,
    pick_date: datetime.date = None,
    pick_time: str = None,
    notes: str = "",
    source: str = "manual",
    result: str = "PENDING",
    profit_loss=None,
) -> dict:
    """
    Write a single sports pick to DB1.

    Returns: {"ok": bool, "id": int or None, "error": str}

    sport       — 'NFL', 'NBA', 'MLB', 'NHL', 'NCAAF', 'NCAAB', 'SOCCER', 'MMA'
    game        — 'LAL vs GSW'
    pick_side   — team name, 'OVER', 'UNDER'
    pick_type   — 'ML', 'SPREAD', 'TOTAL', 'PROP', 'PARLAY'
    odds        — American odds: -110, +150, etc.
    confidence  — 'HIGH', 'MEDIUM', 'LOW', 'LOCK'
    units       — bet size e.g. 2.0
    line_value  — spread or total number (optional)
    """
    try:
        sport      = str(sport).upper().strip()
        pick_type  = str(pick_type).upper().strip()
        confidence = str(confidence).upper().strip()
        result     = str(result).upper().strip()

        pick_date  = pick_date or datetime.date.today()
        pick_time  = pick_time or datetime.datetime.now().strftime("%H:%M")
        date_str   = pick_date.strftime("%Y-%m-%d")

        stmt = (
            f"INSERT INTO {_TABLE} "
            f"(pick_date, pick_time, sport, game, pick_side, pick_type, "
            f" line_value, odds, confidence, units, result, profit_loss, notes, source) "
            f"VALUES ("
            f"TO_DATE('{date_str}', 'YYYY-MM-DD'), "
            f"'{_safe(pick_time)}', "
            f"'{_safe(sport)}', "
            f"'{_safe(game)}', "
            f"'{_safe(pick_side)}', "
            f"'{_safe(pick_type)}', "
            f"{_n(line_value)}, "
            f"{_n(odds)}, "
            f"'{_safe(confidence)}', "
            f"{_n(units)}, "
            f"'{_safe(result)}', "
            f"{_n(profit_loss)}, "
            f"'{_safe(notes)}', "
            f"'{_safe(source)}'"
            f")"
        )

        ok, err = _sql_exec(stmt)
        if not ok:
            print(f"  [SPORTS] ingest_pick failed: {err}")
            return {"ok": False, "id": None, "error": err}

        # Commit
        _sql_exec("COMMIT")

        # Fetch the new row's ID
        fetch_stmt = (
            f"SELECT MAX(id) AS new_id FROM {_TABLE} "
            f"WHERE sport='{_safe(sport)}' AND game='{_safe(game)}' "
            f"AND pick_side='{_safe(pick_side)}' "
            f"AND TO_CHAR(pick_date,'YYYY-MM-DD')='{date_str}'"
        )
        r = requests.post(
            f"{_ORDS_BASE}/_/sql",
            auth=_auth(),
            json={"statementText": fetch_stmt.strip()},
            timeout=15,
        )
        new_id = None
        if r.status_code == 200:
            items = r.json().get("items", [])
            if items:
                rows = items[0].get("resultSet", {}).get("items", [])
                if rows:
                    new_id = rows[0].get("new_id")

        print(f"  [SPORTS] Pick saved — {sport} | {game} | {pick_side} (id={new_id})")
        return {"ok": True, "id": new_id, "error": ""}

    except Exception as e:
        err = str(e)[:120]
        print(f"  [SPORTS] ingest_pick exception: {err}")
        return {"ok": False, "id": None, "error": err}


def ingest_picks_batch(picks_list: list) -> list:
    """
    Write a list of pick dicts to DB1.

    Each dict must contain:
        sport, game, pick_side, pick_type, odds, confidence, units
    Optional:
        line_value, pick_date, pick_time, notes, source, result, profit_loss

    Returns list of result dicts (same order as input).
    """
    results = []
    for i, p in enumerate(picks_list):
        try:
            res = ingest_pick(
                sport       = p.get("sport", ""),
                game        = p.get("game", ""),
                pick_side   = p.get("pick_side", ""),
                pick_type   = p.get("pick_type", "ML"),
                odds        = p.get("odds"),
                confidence  = p.get("confidence", "MEDIUM"),
                units       = p.get("units", 1.0),
                line_value  = p.get("line_value"),
                pick_date   = p.get("pick_date"),
                pick_time   = p.get("pick_time"),
                notes       = p.get("notes", ""),
                source      = p.get("source", "batch"),
                result      = p.get("result", "PENDING"),
                profit_loss = p.get("profit_loss"),
            )
            results.append(res)
        except Exception as e:
            results.append({"ok": False, "id": None, "error": str(e)[:80]})
            print(f"  [SPORTS] batch pick #{i+1} error: {e}")
    return results


# ── Read Operations ──────────────────────────────────────────

def get_picks(
    sport: str = None,
    date: str = None,           # 'YYYY-MM-DD'
    result: str = None,
    limit: int = 50,
) -> list:
    """
    Query sports_picks with optional filters.
    Returns list of pick dicts (newest first).

    sport   — 'NFL', 'NBA', etc.
    date    — exact date string 'YYYY-MM-DD'
    result  — 'WIN', 'LOSS', 'PUSH', 'PENDING'
    """
    try:
        url = f"{_ORDS_BASE}/{_TABLE}/"
        q_parts = []
        if sport:
            q_parts.append(f'"sport":"{sport.upper()}"')
        if result:
            q_parts.append(f'"result":"{result.upper()}"')

        params = {"limit": limit}
        if q_parts:
            params["q"] = "{" + ",".join(q_parts) + "}"

        r = requests.get(url, auth=_auth(), params=params, timeout=15)
        if r.status_code == 200:
            items = r.json().get("items", [])
            # Client-side date filter (ORDS doesn't easily filter DATE columns via q=)
            if date:
                items = [
                    row for row in items
                    if row.get("pick_date", "").startswith(date)
                ]
            return items
        print(f"  [SPORTS] get_picks HTTP {r.status_code}")
        return []
    except Exception as e:
        print(f"  [SPORTS] get_picks error: {e}")
        return []


def update_result(pick_id: int, result: str, profit_loss: float = None) -> bool:
    """
    Update a pick's result and profit/loss.

    pick_id     — the ID of the pick row
    result      — 'WIN', 'LOSS', 'PUSH'
    profit_loss — units won/lost (positive = win, negative = loss)
    """
    try:
        result = str(result).upper().strip()
        pl_sql = f", profit_loss={_n(profit_loss)}" if profit_loss is not None else ""
        stmt = (
            f"UPDATE {_TABLE} "
            f"SET result='{result}'{pl_sql} "
            f"WHERE id={int(pick_id)}"
        )
        ok, err = _sql_exec(stmt)
        if ok:
            _sql_exec("COMMIT")
            print(f"  [SPORTS] Pick #{pick_id} updated -> {result} (PnL: {profit_loss})")
        else:
            print(f"  [SPORTS] update_result failed: {err}")
        return ok
    except Exception as e:
        print(f"  [SPORTS] update_result error: {e}")
        return False


# ── Summary / Analytics ──────────────────────────────────────

def get_record_summary(sport: str = None, date_from: str = None) -> dict:
    """
    Return aggregate record stats.

    Returns:
    {
      "wins": int, "losses": int, "pushes": int, "pending": int,
      "total": int, "win_pct": float, "roi_pct": float,
      "units_profit": float, "units_wagered": float,
      "sport": str or "ALL"
    }
    """
    try:
        picks = get_picks(sport=sport, limit=1000)

        wins     = sum(1 for p in picks if p.get("result") == "WIN")
        losses   = sum(1 for p in picks if p.get("result") == "LOSS")
        pushes   = sum(1 for p in picks if p.get("result") == "PUSH")
        pending  = sum(1 for p in picks if p.get("result") == "PENDING")
        total    = len(picks)

        # Only settled picks for ROI math
        settled  = wins + losses + pushes
        win_pct  = round(wins / settled * 100, 1) if settled > 0 else 0.0

        units_wagered = sum(
            float(p.get("units") or 0)
            for p in picks
            if p.get("result") != "PENDING"
        )
        units_profit = sum(
            float(p.get("profit_loss") or 0)
            for p in picks
            if p.get("profit_loss") is not None
        )
        roi_pct = round(units_profit / units_wagered * 100, 1) if units_wagered > 0 else 0.0

        return {
            "wins":          wins,
            "losses":        losses,
            "pushes":        pushes,
            "pending":       pending,
            "total":         total,
            "settled":       settled,
            "win_pct":       win_pct,
            "roi_pct":       roi_pct,
            "units_profit":  round(units_profit, 2),
            "units_wagered": round(units_wagered, 2),
            "sport":         sport.upper() if sport else "ALL",
        }
    except Exception as e:
        print(f"  [SPORTS] get_record_summary error: {e}")
        return {
            "wins": 0, "losses": 0, "pushes": 0, "pending": 0,
            "total": 0, "settled": 0, "win_pct": 0.0, "roi_pct": 0.0,
            "units_profit": 0.0, "units_wagered": 0.0, "sport": sport or "ALL",
        }


# ── Self-test ────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  SPORTS INGESTION — Self Test")
    print("=" * 50)

    test_pick = {
        "sport":      "NBA",
        "game":       "LAL vs GSW",
        "pick_side":  "LAL",
        "pick_type":  "SPREAD",
        "line_value": -5.5,
        "odds":       -110,
        "confidence": "HIGH",
        "units":      2.0,
        "notes":      "Test pick — self test run",
        "source":     "self_test",
    }

    print("\n[1] ingest_pick...")
    res = ingest_pick(**test_pick)
    print(f"    Result: {res}")

    print("\n[2] get_picks(sport='NBA')...")
    picks = get_picks(sport="NBA", limit=5)
    for p in picks:
        print(f"    #{p.get('id')} | {p.get('game')} | {p.get('pick_side')} | {p.get('result')}")

    print("\n[3] get_record_summary()...")
    summary = get_record_summary()
    print(f"    {summary}")

    print("\n[DONE]")
