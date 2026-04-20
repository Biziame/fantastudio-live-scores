import tls_client
import json
import os
from datetime import date

test_date_env = os.environ.get("TEST_DATE", "").strip()
DATE = test_date_env if test_date_env else str(date.today())

print(f"Fetching results for: [{DATE}]")

session = tls_client.Session(
    client_identifier="chrome_124",
    random_tls_extension_order=True
)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
}

url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{DATE}"
r = session.get(url, headers=headers)
print(f"Status: {r.status_code}")

data = r.json()
events = data["events"]
print(f"Totale eventi: {len(events)}")

# Trova il primo evento con 'italy' nella categoria e stampalo raw
print("\n=== STRUTTURA RAW PRIMO EVENTO ITALIANO ===")
for e in events:
    cat = str(e.get("tournament", {}).get("category", {}).get("name", "")).lower()
    home = e.get("homeTeam", {}).get("name", "")
    if "italy" in cat or "italia" in cat:
        print(f"Partita trovata: {home}")
        print(json.dumps(e, indent=2)[:3000])  # prime 3000 char
        break
