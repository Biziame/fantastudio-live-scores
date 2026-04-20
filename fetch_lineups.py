import tls_client
import os
import json
import datetime
from supabase import create_client
from datetime import date

# --- CONFIG ---
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

test_date_env = os.environ.get("TEST_DATE", "").strip()
DATE = test_date_env if test_date_env else str(date.today())

print(f"Fetching lineups/stats for: [{DATE}]")

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

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Calcola range unix per il giorno richiesto
day_start = int(datetime.datetime.strptime(DATE, "%Y-%m-%d").replace(hour=0, minute=0, second=0).timestamp())
day_end   = int(datetime.datetime.strptime(DATE, "%Y-%m-%d").replace(hour=23, minute=59, second=59).timestamp())

result = (
    supabase.table("risultati_live")
    .select("id, sofascore_id, home_team, away_team, gameweek, season_year")
    .eq("status_type", "finished")
    .gte("start_timestamp", day_start)
    .lte("start_timestamp", day_end)
    .execute()
)

partite = result.data
print(f"Partite finite trovate: {len(partite)}")

if not partite:
    print("Nessuna partita finita oggi, uscita.")
    exit(0)


def debug_incidents(sofascore_id, home_team, away_team):
    """Scarica e logga TUTTI gli incidents per capire la struttura dati."""
    url = f"https://api.sofascore.com/api/v1/event/{sofascore_id}/incidents"
    r = session.get(url, headers=headers)
    print(f"  Incidents status: {r.status_code}")
    if r.status_code != 200:
        return

    incidents = r.json().get("incidents", [])
    print(f"  Totale incidents: {len(incidents)}")

    # Filtra solo quelli rilevanti per fantacalcio
    interesting_types = {"card", "penalty", "goal", "missedPenalty", "penaltyShootout"}

    print(f"  --- TUTTI I TIPI DI INCIDENT TROVATI ---")
    all_types = set(inc.get("incidentType", "UNKNOWN") for inc in incidents)
    print(f"  Types: {all_types}")

    print(f"  --- INCIDENTS RILEVANTI ---")
    for inc in incidents:
        inc_type = inc.get("incidentType", "")
        if inc_type not in interesting_types:
            continue
        # Stampa il JSON completo dell'incident (senza campi enormi)
        safe = {k: v for k, v in inc.items() if k not in ("text", "description")}
        print(f"  [{inc_type}] {json.dumps(safe, ensure_ascii=False)}")


# --- Per ogni partita, logga solo gli incidents (nessun salvataggio) ---
for partita in partite:
    print(f"\n{'='*60}")
    print(f"PARTITA: {partita['home_team']} vs {partita['away_team']} (sofascore_id={partita['sofascore_id']})")
    print(f"{'='*60}")
    debug_incidents(
        sofascore_id=partita["sofascore_id"],
        home_team=partita["home_team"],
        away_team=partita["away_team"],
    )

print("\nDebug completato. Nessun dato salvato.")
