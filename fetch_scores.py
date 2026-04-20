import tls_client
import json
import os
from supabase import create_client
from datetime import date

# --- CONFIG DA SECRETS ---
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SERIE_A_ID = 23
DATE = str(date.today())

print(f"Fetching Serie A results for {DATE}...")

# --- SOFASCORE con tls_client ---
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
print(f"SofaScore status: {r.status_code}")

if r.status_code != 200:
    print(f"Errore SofaScore: {r.text[:300]}")
    exit(1)

data = r.json()
partite = [e for e in data["events"] if e.get("uniqueTournament", {}).get("id") == SERIE_A_ID]
print(f"Partite Serie A trovate: {len(partite)}")

if not partite:
    print("Nessuna partita oggi, uscita.")
    exit(0)

# --- SUPABASE ---
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

rows = []
for e in partite:
    rows.append({
        "sofascore_id": e["id"],
        "home_team": e["homeTeam"]["name"],
        "home_team_id": e["homeTeam"]["id"],
        "home_team_code": e["homeTeam"]["nameCode"],
        "away_team": e["awayTeam"]["name"],
        "away_team_id": e["awayTeam"]["id"],
        "away_team_code": e["awayTeam"]["nameCode"],
        "home_score": e.get("homeScore", {}).get("current"),
        "away_score": e.get("awayScore", {}).get("current"),
        "home_score_p1": e.get("homeScore", {}).get("period1"),
        "away_score_p1": e.get("awayScore", {}).get("period1"),
        "status_code": e["status"]["code"],
        "status_type": e["status"]["type"],
        "winner_code": e.get("winnerCode"),
        "start_timestamp": e["startTimestamp"],
        "tournament_name": e["tournament"]["name"],
        "tournament_id": e["uniqueTournament"]["id"],
        "season_year": e["season"]["year"],
        "gameweek": e.get("roundInfo", {}).get("round"),
    })

result = supabase.table("risultati_live").upsert(rows, on_conflict="sofascore_id").execute()
print(f"Upsert completato: {len(rows)} righe ✅")
for row in rows:
    hs = row['home_score'] if row['home_score'] is not None else '-'
    as_ = row['away_score'] if row['away_score'] is not None else '-'
    print(f"  {row['home_team']} {hs} - {as_} {row['away_team']} [{row['status_type']}]")
