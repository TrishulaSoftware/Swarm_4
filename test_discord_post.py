import requests, json
from pathlib import Path
from datetime import datetime

WEBHOOK = "https://discord.com/api/webhooks/1513311419330723973/YDdPSHbdfidMK-wZtpMvQ0R94Dlxck_TJBJvTWUGIVihHvpGC31BYfsNW1lf1LJd3LX3"

screenshot = Path("tv_session_test.png").read_bytes()
ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

embed = {
    "title": "⚡ STARFALL L-TRIG — LONG ENTRY",
    "color": 0x08C09B,
    "fields": [
        {"name": "Pair",  "value": "`EUR_USD`",  "inline": True},
        {"name": "TF",    "value": "`30m`",       "inline": True},
        {"name": "Units", "value": "`15,000`",    "inline": True},
        {"name": "SL",    "value": "`1.08200`",   "inline": True},
        {"name": "TP",    "value": "`1.08450`",   "inline": True},
    ],
    "image": {"url": "attachment://starfall_chart.png"},
    "footer": {"text": f"Trishula Swarm · Starfall E.04 Sovereign · {ts}"},
}

files = {
    "file": ("starfall_chart.png", screenshot, "image/png"),
    "payload_json": (None, json.dumps({"embeds": [embed]}), "application/json"),
}

r = requests.post(WEBHOOK, files=files, timeout=20)
print(f"Status: {r.status_code}")
if r.status_code not in (200, 204):
    print(r.text)
else:
    print("Posted to Discord!")
