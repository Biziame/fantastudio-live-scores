import tls_client
import json
import os
from supabase import create_client
from datetime import date

# --- CONFIG DA SECRETS ---
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

# Leggi TEST_DATE da env
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
print(f"URL: {url}")
r = session.get(url, headers=headers)
print(f"SofaScore status: {r.status_code}")

if r.status_code != 200:
    print(f"Errore: {r.text[:300]}")
    exit(1)

data = r.json()
events = data["events"]
print(f"Totale eventi: {len(events)}")

# Stampa tutti i tornei unici presenti
tornei = {}
for e in events:
    ut = e.get("uniqueTournament", {})
    tid = ut.get("id")
    tname = ut.get("name", "?")
    cat = e.get("tournament", {}).get("category", {}).get("name", "?")
    if tid not in tornei:
        tornei[tid] = f"{tname} (cat: {cat})"

print("\n=== TORNEI TROVATI ===")
for tid, tname in sorted(tornei.items(), key=lambda x: str(x[0])):
    print(f"  ID {tid}: {tname}")

# Cerca Serie A per nome
print("\n=== CERCA 'serie' o 'italy' nei nomi ===")
for e in events:
    ut = e.get("uniqueTournament", {})
    tname = ut.get("name", "").lower()
    cat = e.get("tournament", {}).get("category", {}).get("name", "").lower()
    if "serie" in tname or "italy" in cat or "italia" in cat:
        print(f"  ID {ut.get('id')}: {ut.get('name')} | cat: {cat} | {e['homeTeam']['name']} vs {e['awayTeam']['name']}")
        break  # basta uno per confermare l'ID
