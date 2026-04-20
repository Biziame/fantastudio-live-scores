import tls_client
import os
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


def get_incidents(sofascore_id):
    """
    Ritorna un dict { player_id: { yellow_card, red_card, penalty_miss, penalty_save } }
    parsando gli incidents della partita.
    """
    url = f"https://api.sofascore.com/api/v1/event/{sofascore_id}/incidents"
    r = session.get(url, headers=headers)
    if r.status_code != 200:
        print(f"  Errore incidents {sofascore_id}: {r.status_code}")
        return {}

    incidents = r.json().get("incidents", [])
    data = {}

    for inc in incidents:
        inc_type = inc.get("incidentType", "")
        player   = inc.get("player") or inc.get("goalkeeper")
        if not player:
            continue
        pid = player.get("id")
        if not pid:
            continue

        if pid not in data:
            data[pid] = {"yellow_card": 0, "red_card": 0, "penalty_miss": 0, "penalty_save": 0}

        if inc_type == "card":
            card_type = inc.get("incidentClass", "")
            if card_type == "yellow":
                data[pid]["yellow_card"] += 1
            elif card_type in ("red", "yellowRed"):
                data[pid]["red_card"] += 1

        elif inc_type == "penalty":
            penalty_class = inc.get("incidentClass", "")
            if penalty_class == "missed":
                # chi ha sbagliato
                data[pid]["penalty_miss"] += 1
            elif penalty_class == "saved":
                # chi ha sbagliato (il tiratore)
                data[pid]["penalty_miss"] += 1
                # il portiere che ha parato
                gk = inc.get("goalkeeper")
                if gk:
                    gkid = gk.get("id")
                    if gkid not in data:
                        data[gkid] = {"yellow_card": 0, "red_card": 0, "penalty_miss": 0, "penalty_save": 0}
                    data[gkid]["penalty_save"] += 1

    return data


def get_player_rows(match_db_id, sofascore_id, gameweek, season_year):
    """Chiama /lineups + /incidents e restituisce lista di righe player_stats."""
    # 1. Lineups
    url = f"https://api.sofascore.com/api/v1/event/{sofascore_id}/lineups"
    r = session.get(url, headers=headers)
    if r.status_code != 200:
        print(f"  Errore lineups {sofascore_id}: {r.status_code}")
        return []

    lineup_data = r.json()

    # 2. Incidents (cartellini, rigori)
    incidents = get_incidents(sofascore_id)

    rows = []
    for side in ["home", "away"]:
        team_data = lineup_data.get(side, {})
        team_name = team_data.get("team", {}).get("name", "")
        is_home = (side == "home")

        players = team_data.get("players", [])
        for p in players:
            player = p.get("player", {})
            stats  = p.get("statistics", {})
            pid    = player.get("id")

            # Dati da incidents (cartellini/rigori)
            inc = incidents.get(pid, {})

            rows.append({
                "match_id":       match_db_id,
                "sofascore_id":   sofascore_id,
                "player_id":      pid,
                "player_name":    player.get("name"),
                "team_name":      team_name,
                "is_home":        is_home,
                "goals":          stats.get("goals", 0) or 0,
                "goals_penalty":  stats.get("goalsPenalty", 0) or 0,
                "penalty_miss":   inc.get("penalty_miss", 0),
                "penalty_save":   inc.get("penalty_save", 0),
                "yellow_card":    inc.get("yellow_card", 0),
                "red_card":       inc.get("red_card", 0),
                "minutes_played": stats.get("minutesPlayed", 0) or 0,
                "gameweek":       gameweek,
                "season_year":    season_year,
            })

    return rows


# --- Itera le partite e salva ---
total_rows = 0
for partita in partite:
    print(f"\nProcesso: {partita['home_team']} vs {partita['away_team']} (id={partita['sofascore_id']})")
    rows = get_player_rows(
        match_db_id=partita["id"],
        sofascore_id=partita["sofascore_id"],
        gameweek=partita["gameweek"],
        season_year=partita["season_year"],
    )

    if not rows:
        continue

    supabase.table("player_stats").upsert(rows, on_conflict="sofascore_id,player_id").execute()
    total_rows += len(rows)
    print(f"  Salvati {len(rows)} giocatori ✅")

print(f"\nTotale righe upsert: {total_rows} ✅")
