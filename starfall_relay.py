"""
starfall_relay.py
=================
Receives TradingView webhook alerts from Starfall E.04 Sovereign,
screenshots the live TradingView chart via Playwright (logged in),
and posts the chart image + signal embed to Discord.

Setup:
  1. Add TV_USERNAME and TV_PASSWORD to .env
  2. Add STARFALL_DISCORD_WEBHOOK to .env
  3. Run: python starfall_relay.py
  4. In TradingView Alert settings, set webhook URL to:
       http://<your-cloud-ip>:7411/starfall
  5. Passphrase check: STARFALL_ACTUAL_01

Usage:
  python starfall_relay.py          # production (port 7411)
  python starfall_relay.py --test   # fires a fake BUY signal locally
"""

import os, sys, json, asyncio, io, logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, request, jsonify
import threading, requests
from playwright.async_api import async_playwright

load_dotenv(encoding="latin-1")

# ── Config ─────────────────────────────────────────────────────────────────────
TV_USERNAME        = os.getenv("TV_USERNAME", "")
TV_PASSWORD        = os.getenv("TV_PASSWORD", "")
TV_CHART_URL       = os.getenv("TV_CHART_URL", "https://www.tradingview.com/chart/NR3yo9nj/?symbol=AMEX%3ASPY")
WEBHOOKS = {
    "default": os.getenv("STARFALL_DISCORD_WEBHOOK", "https://discord.com/api/webhooks/1513368284853047448/8fR4M7i3CpZH26bvud-xZ4wEsW_gf5SQ4ktt-X3rKQFI4IHT6lAnUUPBAyXvvOwaNYH3"),
    "forex-10m": os.getenv("STARFALL_DISCORD_WEBHOOK_FOREX_10M", "https://discord.com/api/webhooks/1513341978539200713/dFCiyDgZ5W5PHzKWCxvDMbaYdtDzmXLGglXsomvMRRsTbfY05Lc7p_ZPrfv4531nPdNT"),
    "crypto-10m": os.getenv("STARFALL_DISCORD_WEBHOOK_CRYPTO_10M", "https://discord.com/api/webhooks/1513344609072320544/1PaVBMYqHtd54CTbaziUVzn154DYFpohsCwHsRKNsStOb3Y5CPigGp49sWjWhuWoAAWJ"),
    "rdm-test-30m": os.getenv("STARFALL_DISCORD_WEBHOOK_RDM_TEST_30M", "https://discord.com/api/webhooks/1513369629752430672/onWCBf0liCB4hcG__Blr1SlxSroCcVe4PwDFTR7eOjyJ7pJvTfLRziIID76NF4-OXTRS")
}
SESSION_FILE       = Path("tv_session.json")
PASSPHRASE         = "STARFALL_ACTUAL_01"
PORT               = 7411
SCREENSHOT_PATH    = Path("starfall_chart.png")

# ── Colors per signal type ─────────────────────────────────────────────────────
COLORS = {
    "BUY":  0x08C09B,   # teal/green
    "SELL": 0xCD0202,   # red
    "EXIT": 0x9B59B6,   # purple
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [STARFALL] %(message)s",
    handlers=[
        logging.FileHandler("starfall_relay.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger()

# ── TradingView Screenshot ─────────────────────────────────────────────────────

async def screenshot_tv(symbol: str = None) -> bytes | None:
    """Load saved TV session and screenshot the Starfall chart."""
    session_file = Path("tv_session.json")
    if not session_file.exists():
        log.error("  tv_session.json not found — run tv_session_setup.py first!")
        return None

    # Determine URL dynamically based on symbol
    url = TV_CHART_URL
    if symbol:
        base_url = TV_CHART_URL.split("?")[0]
        # Clean symbol (e.g. EUR_USD -> EURUSD)
        clean_symbol = symbol.replace("_", "")
        url = f"{base_url}?symbol={clean_symbol}"

    log.info(f"  Launching Playwright -> {url}")
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage",
                      "--disable-blink-features=AutomationControlled"]
            )
            # Load the saved session (handles 2FA — no re-login needed)
            ctx = await browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
                storage_state=str(session_file),
            )
            await ctx.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
            )
            page = await ctx.new_page()

            # ── Load the chart ────────────────────────────────────────────────
            log.info("  Loading chart...")
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)

            # Wait for chart to fully render (candles + indicators + table)
            await page.wait_for_timeout(8000)

            # Try to dismiss any popups/overlays
            for dismiss in ["Got it", "Accept", "Close", "×", "Dismiss"]:
                try:
                    el = page.get_by_text(dismiss, exact=True)
                    if await el.count() > 0:
                        await el.first.click(timeout=1000)
                except: pass

            await page.wait_for_timeout(2000)

            # Hide toolbars (left side drawing toolbar and floating favorites toolbar)
            await page.add_style_tag(content="""
                #drawing-toolbar,
                .tv-favorited-drawings-toolbar,
                [class*="favorited-drawings-toolbar"],
                [class*="favoritedDrawingsToolbar"],
                [class*="side-toolbar"],
                [class*="sideToolbar"] {
                    display: none !important;
                }
            """)

            # ── Screenshot ────────────────────────────────────────────────────
            screenshot_bytes = await page.screenshot(
                full_page=False,
                type="png",
                clip={"x": 0, "y": 0, "width": 1440, "height": 900}
            )
            SCREENSHOT_PATH.write_bytes(screenshot_bytes)
            log.info(f"  Screenshot saved -> {SCREENSHOT_PATH}")
            await browser.close()
            return screenshot_bytes

    except Exception as e:
        log.error(f"  Screenshot failed: {e}")
        return None

# ── Dynamic Ticker Classification & Routing ────────────────────────────────────

FOREX_PAIRS = {
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
    "EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "CHFJPY", "CADJPY",
    "EURCHF", "EURCAD", "EURAUD", "GBPCAD", "GBPAUD", "GBPCHF", "EURCHF"
}

CRYPTO_BASES = {
    "BTC", "ETH", "SOL", "XRP", "ZEC", "XLM", "LINK", "HYPE", "SUI", 
    "DOGE", "ADA", "ONDO", "LTC", "TAO", "HBAR", "PENGU", "AVAX", 
    "AERO", "BCH", "ALGO", "SHIB", "FET", "ICP", "DOT", "MON", 
    "AAVE", "FIL", "CRO", "RENDER", "UNI", "DASH", "ATOM", "QNT", 
    "INJ", "FLR"
}

def classify_channel(signal: dict) -> str:
    """Analyze ticker symbol and route dynamically to the proper channel key."""
    explicit_channel = signal.get("channel")
    if explicit_channel and explicit_channel in WEBHOOKS:
        return explicit_channel

    raw_pair = signal.get("pair", "").upper()
    if "COINBASE" in raw_pair:
        return "crypto-10m"

    clean_pair = raw_pair.replace("_", "").split(":")[-1]

    if clean_pair in FOREX_PAIRS:
        return "forex-10m"

    currencies = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"]
    if len(clean_pair) == 6 and any(clean_pair.startswith(c) for c in currencies) and any(clean_pair.endswith(c) for c in currencies):
        return "forex-10m"

    if any(clean_pair.startswith(coin) for coin in CRYPTO_BASES) and (clean_pair.endswith("USD") or clean_pair.endswith("USDT") or clean_pair.endswith("EUR")):
        return "crypto-10m"

    return "default"

# ── Discord Poster ─────────────────────────────────────────────────────────────

def post_to_discord(signal: dict, screenshot: bytes | None):
    """Post signal embed + chart screenshot to Discord."""
    channel_key = classify_channel(signal)
    webhook_url = WEBHOOKS.get(channel_key) or WEBHOOKS["default"]
    if not webhook_url:
        log.warning(f"  No webhook URL found for channel {channel_key} — skipping Discord post.")
        return

    action   = signal.get("action", "SIGNAL")
    pair     = signal.get("pair", "?")
    tf       = signal.get("tf", "?")
    units    = signal.get("units", "?")
    sl       = signal.get("sl", "?")
    tp       = signal.get("tp", "?")
    outcome  = signal.get("outcome", "")
    ts       = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    color = COLORS.get(action, 0xFFFFFF)

    # Build embed
    if channel_key == "rdm-test-30m":
        title = {
            "BUY":  "⚡ RED MAGE — BULLISH ORDER BLOCK",
            "SELL": "🔴 RED MAGE — BEARISH ORDER BLOCK",
            "EXIT": f"🏁 RED MAGE — ORDER BLOCK CLEARED ({outcome})" if outcome else "🏁 RED MAGE — ORDER BLOCK CLEARED",
        }.get(action, f"RED MAGE ORDER BLOCK {action}")
        footer_text = f"Trishula Swarm · Red Mage Order Block · {ts}"
    else:
        title = {
            "BUY":  "⚡ STARFALL L-TRIG — LONG ENTRY",
            "SELL": "🔴 STARFALL S-TRIG — SHORT ENTRY",
            "EXIT": f"🏁 STARFALL EXIT — {outcome}",
        }.get(action, f"STARFALL {action}")
        footer_text = f"Trishula Swarm · Starfall E.04 Sovereign · {ts}"

    fields = []
    if action in ("BUY", "SELL"):
        fields = [
            {"name": "Pair",   "value": f"`{pair}`",  "inline": True},
            {"name": "TF",     "value": f"`{tf}`",    "inline": True},
        ]
    elif action == "EXIT":
        fields = [
            {"name": "Pair",    "value": f"`{pair}`",    "inline": True},
            {"name": "Outcome", "value": f"`{outcome}`", "inline": True},
        ]

    embed = {
        "title":       title,
        "color":       color,
        "fields":      fields,
        "footer":      {"text": footer_text},
        "image":       {"url": "attachment://starfall_chart.png"} if screenshot else {},
    }

    if screenshot:
        # Multipart: embed + image file
        files = {
            "file": ("starfall_chart.png", screenshot, "image/png"),
            "payload_json": (None, json.dumps({"embeds": [embed]}), "application/json"),
        }
        r = requests.post(webhook_url, files=files, timeout=20)
    else:
        r = requests.post(webhook_url, json={"embeds": [embed]}, timeout=10)

    if r.status_code in (200, 204):
        log.info(f"  Posted to Discord ({channel_key}): {action} {pair}")
    else:
        log.warning(f"  Discord post failed ({channel_key}): {r.status_code} {r.text[:100]}")

# ── Signal Handler ─────────────────────────────────────────────────────────────

def handle_signal(signal: dict):
    """Async handler: screenshot then post."""
    log.info(f"  Signal: {signal}")
    symbol = signal.get("pair")
    screenshot = asyncio.run(screenshot_tv(symbol))
    post_to_discord(signal, screenshot)

# ── Flask Webhook Receiver ─────────────────────────────────────────────────────

app = Flask(__name__)

@app.route("/starfall", methods=["POST"])
def starfall_webhook():
    try:
        data = request.get_json(force=True)
        log.info(f"Received webhook: {data}")
    except Exception as e:
        return jsonify({"error": f"JSON parse failed: {e}"}), 400

    if not data or data.get("passphrase") != PASSPHRASE:
        log.warning("  Invalid or missing passphrase.")
        return jsonify({"error": "unauthorized"}), 401

    # Fire the handler in a background thread (don't block the webhook response)
    t = threading.Thread(target=handle_signal, args=(data,), daemon=True)
    t.start()

    return jsonify({"status": "received", "action": data.get("action")}), 200

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "alive", "service": "starfall-relay"}), 200

# ── Pub/Sub Subscriber ─────────────────────────────────────────────────────────

def run_pubsub_subscriber():
    """GCP Pub/Sub Subscription mode - pulls signals from trishula-alerts-sub."""
    try:
        from google.cloud import pubsub_v1
    except ImportError:
        log.error("google-cloud-pubsub package not installed!")
        sys.exit(1)

    key_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", r"H:\Trishula\Swarm_4_Integration\trishula-gcp-key.json")
    if not os.path.exists(key_file):
        # Check alternative location
        alt_key = r"H:\Trishula\Swarm_4_Integration\Swarm_4_SBM_FINAL INTEGRATION\Project-Swarm\trishula-gcp-key.json"
        if os.path.exists(alt_key):
            key_file = alt_key

    log.info(f"Using GCP Key: {key_file}")
    
    project_id = "gcp-swarm-491812"
    sub_name = "trishula-alerts-sub"
    
    subscriber = pubsub_v1.SubscriberClient.from_service_account_file(key_file)
    sub_path = subscriber.subscription_path(project_id, sub_name)
    
    log.info(f"=== Starfall Pub/Sub Subscriber starting ===")
    log.info(f"  Subscription: {sub_path}")
    log.info(f"  TV chart:     {TV_CHART_URL}")
    log.info(f"  Discord Webhooks configured: {list(WEBHOOKS.keys())}")

    def callback(message):
        try:
            payload = json.loads(message.data.decode("utf-8"))
            log.info(f"Received Pub/Sub message: {payload}")
            # Acknowledge immediately so we don't hold the message open during slow screenshotting
            message.ack()
            # Handle the signal in a background thread to allow subscriber thread to keep fetching
            t = threading.Thread(target=handle_signal, args=(payload,), daemon=True)
            t.start()
        except Exception as e:
            log.error(f"Error parsing Pub/Sub message: {e}")
            message.nack()

    streaming_pull_future = subscriber.subscribe(sub_path, callback=callback)
    log.info("Listening for messages... (Ctrl+C to exit)")
    
    try:
        streaming_pull_future.result()
    except KeyboardInterrupt:
        streaming_pull_future.cancel()
        log.info("Subscriber stopped.")

# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--test" in sys.argv:
        # Fire a fake BUY signal for local testing
        log.info("=== TEST MODE: Firing fake BUY signal ===")
        test_signal = {
            "passphrase": PASSPHRASE,
            "action": "BUY",
            "pair": "EUR_USD",
            "tf": "30",
            "units": "15000",
            "sl": "1.08200",
            "tp": "1.08450",
        }
        handle_signal(test_signal)
    elif "--pubsub" in sys.argv:
        run_pubsub_subscriber()
    else:
        log.info(f"=== Starfall Relay starting on port {PORT} ===")
        log.info(f"  Webhook URL: POST http://<your-ip>:{PORT}/starfall")
        log.info(f"  Health:      GET  http://<your-ip>:{PORT}/health")
        log.info(f"  TV chart:    {TV_CHART_URL}")
        log.info(f"  Discord Webhooks configured: {list(WEBHOOKS.keys())}")
        log.info(f"  TV login:    {'SET' if TV_USERNAME else 'NOT SET'}")
        app.run(host="0.0.0.0", port=PORT, debug=False)

