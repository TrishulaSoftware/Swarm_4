# -*- coding: utf-8 -*-
"""
Q-MATRIX EARNINGS CALENDAR  v1.0
==================================
Scans the full Q-Matrix watchlist (+ extended list) for earnings
reporting in the next 7 days. Builds and posts a dashboard to
the #earnings-calendar Discord channel every Monday at Market Open.

Data from yfinance: earnings date, EPS estimate, revenue estimate,
last EPS actual vs estimate (beat/miss), implied move from ATM straddle.
"""

import io, json, datetime, time, requests
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import yfinance as yf

# ── Theme ──────────────────────────────────────────────────────────────────────
DARK_BG  = "#0a0a12"
PANEL_BG = "#0f0f1a"
GREEN    = "#00cc88"
RED      = "#ff3344"
GOLD     = "#ffbd15"
CYAN     = "#00e5ff"
WHITE    = "#e2e8f0"
DIM      = "#64748b"
BORDER   = "#1e1e30"
ORANGE   = "#ff8844"

# ── Full watchlist to scan for earnings ───────────────────────────────────────
# Includes our 38-ticker stack + important extras likely to have earnings
WATCHLIST = [
    # ETFs (skip earnings scan — ETFs don't report)
    # Mag-7
    "TSLA", "MSFT", "META", "AMZN", "AAPL", "GOOGL", "NVDA",
    # Mega-cap
    "AVGO", "CRWD", "NFLX", "TSM", "ADBE", "ARM",
    # Mid-cap
    "PLTR", "AMD", "INTC", "ORCL", "COIN", "MU", "APP",
    "MSTR", "NET", "RDDT", "DDOG",
    # Commodities / ETFs skip
    # Low-cap
    "SOFI", "RKLB", "HOOD", "MARA", "SNAP",
    # Extended important names often in focus
    "PANW", "CRM", "NOW", "SNOW", "INTU", "ADBE", "ZM",
    "SPOT", "TEAM", "OKTA", "GTLB", "MDB", "DOCN",
    "FTNT", "IBM", "GE", "ROKU", "TTWO", "NFLX",
]
WATCHLIST = list(dict.fromkeys(WATCHLIST))  # dedupe

# ── Helpers ────────────────────────────────────────────────────────────────────
def _session_label():
    hr = datetime.datetime.now().hour
    if hr < 11:  return "Market Open"
    if hr < 14:  return "Midday"
    return "Power Hour"

def _ts():
    return datetime.datetime.now().strftime("%b %d %Y  %I:%M %p ET")

def _safe_float(v, default=None):
    try:
        f = float(v)
        return f if not np.isnan(f) else default
    except Exception:
        return default

def _fmt_eps(v):
    if v is None: return "N/A"
    return f"${v:.2f}"

def _fmt_rev(v):
    if v is None: return "N/A"
    if abs(v) >= 1e9:  return f"${v/1e9:.2f}B"
    if abs(v) >= 1e6:  return f"${v/1e6:.1f}M"
    return f"${v:.0f}"

def _beat_str(actual, estimate):
    if actual is None or estimate is None: return ("--", DIM)
    diff = actual - estimate
    pct  = diff / abs(estimate) * 100 if estimate != 0 else 0
    if diff > 0:   return (f"+{pct:.1f}% Beat", GREEN)
    elif diff < 0: return (f"{pct:.1f}% Miss", RED)
    else:          return ("In-Line", GOLD)

def _implied_move(symbol, earnings_date):
    """Estimate implied move from nearest-expiry ATM straddle."""
    try:
        tk = yf.Ticker(symbol)
        spot = tk.fast_info.get("lastPrice") or tk.fast_info.get("regularMarketPrice")
        if not spot: return None
        # Find expiry closest to (but after) earnings date
        opts = tk.options
        earn_dt = pd.Timestamp(earnings_date)
        future_exps = [e for e in sorted(opts) if pd.Timestamp(e) >= earn_dt]
        if not future_exps: return None
        exp = future_exps[0]
        chain = tk.option_chain(exp)
        calls = chain.calls
        puts  = chain.puts
        # ATM strike
        atm = min(calls['strike'].values, key=lambda k: abs(k - spot))
        atm_call = calls[calls['strike'] == atm]['lastPrice'].values
        atm_put  = puts[puts['strike']  == atm]['lastPrice'].values
        if len(atm_call) and len(atm_put):
            straddle = float(atm_call[0]) + float(atm_put[0])
            return straddle / spot * 100
    except Exception:
        pass
    return None

def _get_earnings_this_week(symbols):
    """Return list of dicts for symbols reporting earnings in next 7 days."""
    today  = datetime.date.today()
    cutoff = today + datetime.timedelta(days=7)
    results = []

    for sym in symbols:
        try:
            tk  = yf.Ticker(sym)
            cal = tk.calendar

            # calendar can be a DataFrame or dict depending on yfinance version
            earn_date = None
            if isinstance(cal, pd.DataFrame) and not cal.empty:
                if 'Earnings Date' in cal.index:
                    val = cal.loc['Earnings Date'].values[0]
                    earn_date = pd.Timestamp(val).date()
                elif 'Earnings Date' in cal.columns:
                    val = cal['Earnings Date'].iloc[0]
                    earn_date = pd.Timestamp(val).date()
            elif isinstance(cal, dict):
                val = cal.get('Earnings Date', [None])
                if isinstance(val, list) and val:
                    earn_date = pd.Timestamp(val[0]).date()
                elif val:
                    earn_date = pd.Timestamp(val).date()

            if earn_date is None or not (today <= earn_date <= cutoff):
                continue

            # EPS / Rev estimates
            eps_est = rev_est = None
            if isinstance(cal, pd.DataFrame) and not cal.empty:
                if 'Earnings Average' in cal.index:
                    eps_est = _safe_float(cal.loc['Earnings Average'].values[0])
                if 'Revenue Average' in cal.index:
                    rev_est = _safe_float(cal.loc['Revenue Average'].values[0])
            elif isinstance(cal, dict):
                eps_est = _safe_float(cal.get('Earnings Average'))
                rev_est = _safe_float(cal.get('Revenue Average'))

            # Last EPS actual vs estimate (beat/miss)
            last_actual = last_est = None
            try:
                hist = tk.earnings_history
                if hist is not None and not hist.empty:
                    row = hist.iloc[-1]
                    last_actual = _safe_float(row.get('epsActual'))
                    last_est    = _safe_float(row.get('epsEstimate'))
            except Exception:
                pass

            # Earnings time (BMO / AMC)
            earn_time = "TBD"
            try:
                info = tk.fast_info
                # Some tickers expose earningsTimestamp
            except Exception:
                pass

            # Implied move
            impl_move = _implied_move(sym, earn_date)

            results.append({
                "symbol":      sym,
                "date":        earn_date,
                "eps_est":     eps_est,
                "rev_est":     rev_est,
                "last_actual": last_actual,
                "last_est":    last_est,
                "impl_move":   impl_move,
                "dte":         (earn_date - today).days,
            })
            print(f"  [{sym}] Earnings {earn_date}  EPS est {_fmt_eps(eps_est)}  "
                  f"Impl move {f'{impl_move:.1f}%' if impl_move else 'N/A'}")

        except Exception as e:
            pass  # silently skip tickers with no earnings data

    results.sort(key=lambda x: x['date'])
    return results


def build_earnings_dashboard(earnings_list, week_start, week_end):
    """Build a dark-themed earnings calendar chart."""
    n = len(earnings_list)
    fig_h = max(5, 2.2 + n * 0.52)
    fig = plt.figure(figsize=(16, fig_h), facecolor=DARK_BG)
    ax  = fig.add_subplot(111)
    ax.set_facecolor(PANEL_BG)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.spines[:].set_color(BORDER)

    # ── Column headers ─────────────────────────────────────────────────────────
    COL = [0.02, 0.10, 0.24, 0.38, 0.52, 0.65, 0.80]
    HEADERS = ["TICKER", "DATE", "EPS EST", "REV EST", "IMPL MOVE", "LAST BEAT/MISS", "DTE"]
    for cx, hdr in zip(COL, HEADERS):
        ax.text(cx, 0.97, hdr, color=DIM, fontsize=8, fontweight="bold", va="top")
    ax.axhline(0.94, color=BORDER, lw=1.0)

    if not earnings_list:
        ax.text(0.5, 0.5, "No earnings in the watchlist this week.",
                color=DIM, fontsize=11, ha="center", va="center")
    else:
        row_h = 0.88 / max(n, 1)
        for ri, row in enumerate(earnings_list):
            y = 0.93 - ri * row_h

            sym   = row["symbol"]
            date  = row["date"].strftime("%a %b %d")
            eps   = _fmt_eps(row["eps_est"])
            rev   = _fmt_rev(row["rev_est"])
            impl  = f"{row['impl_move']:.1f}%" if row["impl_move"] else "N/A"
            bs, bc = _beat_str(row["last_actual"], row["last_est"])
            dte_str = f"{row['dte']}d"

            # Highlight today / tomorrow
            day_col = CYAN if row["dte"] == 0 else (GOLD if row["dte"] == 1 else WHITE)
            impl_col = RED if row["impl_move"] and row["impl_move"] > 8 else (ORANGE if row["impl_move"] and row["impl_move"] > 5 else WHITE)

            ax.text(COL[0], y, sym,      color=CYAN,     fontsize=9,  fontweight="bold", va="top")
            ax.text(COL[1], y, date,     color=day_col,  fontsize=8,  va="top")
            ax.text(COL[2], y, eps,      color=WHITE,    fontsize=8,  va="top")
            ax.text(COL[3], y, rev,      color=WHITE,    fontsize=8,  va="top")
            ax.text(COL[4], y, impl,     color=impl_col, fontsize=8,  fontweight="bold", va="top")
            ax.text(COL[5], y, bs,       color=bc,       fontsize=8,  va="top")
            ax.text(COL[6], y, dte_str,  color=DIM,      fontsize=8,  va="top")

            if ri % 2 == 0:
                ax.axhspan(y - row_h * 0.8, y + row_h * 0.1, color="#fff", alpha=0.018)

    # Footer legend
    ax.text(0.02, 0.02,
            "IMPL MOVE = ATM straddle / spot for nearest post-earnings expiry  |  "
            "LAST BEAT/MISS = most recent quarter  |  Cyan = today  |  Gold = tomorrow",
            color=DIM, fontsize=6.5, va="bottom")

    # Title
    week_lbl = f"{week_start.strftime('%b %d')} – {week_end.strftime('%b %d %Y')}"
    fig.suptitle(f"Q-MATRIX  |  EARNINGS CALENDAR  |  Week of {week_lbl}",
                 color=GOLD, fontsize=12, fontweight="bold", y=0.99)
    fig.patch.set_facecolor(DARK_BG)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, facecolor=DARK_BG, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def run_earnings_sweep(webhook_earnings: str, watchlist=None):
    """Scan watchlist for this week's earnings and post to Discord."""
    if watchlist is None:
        watchlist = WATCHLIST

    today      = datetime.date.today()
    week_start = today
    week_end   = today + datetime.timedelta(days=6)
    sweep      = _session_label()
    ts         = _ts()

    print(f"[EARNINGS] Scanning {len(watchlist)} tickers for earnings "
          f"{week_start} – {week_end}...")

    earnings = _get_earnings_this_week(watchlist)
    print(f"[EARNINGS] Found {len(earnings)} earnings this week.")

    buf = build_earnings_dashboard(earnings, week_start, week_end)

    if earnings:
        tickers_str = "  |  ".join(
            f"**{r['symbol']}** {r['date'].strftime('%a %b %d')}" for r in earnings
        )
        desc = (
            f"**EARNINGS THIS WEEK**  `{sweep}  ·  {ts}`\n"
            f"{tickers_str}\n\n"
            "Implied Move = ATM straddle priced into the nearest post-earnings expiry — "
            "the market's expected 1-sigma move. "
            "High implied move (>8%) means expensive options; consider selling premium into earnings. "
            "Low implied move (<4%) means options are cheap; consider buying the straddle. "
            "Last Beat/Miss gives historical context on management's ability to guide and deliver."
        )
    else:
        desc = (
            f"**EARNINGS THIS WEEK**  `{sweep}  ·  {ts}`\n"
            "No earnings from the Q-Matrix watchlist this week. "
            "Check back Monday for next week's calendar."
        )

    payload = {"content": desc}
    buf.seek(0)
    r = requests.post(webhook_earnings,
        data={"payload_json": json.dumps(payload)},
        files={"file": ("earnings_calendar.png", buf, "image/png")},
        timeout=30)

    if r.status_code in (200, 204):
        print(f"[EARNINGS] Dashboard posted. ({len(earnings)} tickers)")
    else:
        print(f"[EARNINGS] Discord error {r.status_code}: {r.text[:200]}")

    return earnings


if __name__ == "__main__":
    import sys
    sys.path.insert(0, r"H:\Trishula\Swarm_4_Integration\Salvo_Staging")
    from sovereign_options_scanner import WEBHOOK_EARNINGS
    run_earnings_sweep(WEBHOOK_EARNINGS)
