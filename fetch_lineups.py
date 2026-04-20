import tls_client
import os
from supabase import create_client
from datetime import date

# --- CONFIG ---
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SERIE_A_ID = 23

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

# --- Prendi le partite finite oggi dalla tabella risultati_live ---
result = (
    supabase.table("risultati_live")
    .select("id, sofascore_id, home_team, away_team, gameweek, season_year")
    .eq("status_type", "finished")
    .like("start_timestamp::text", f"%")  # tutte le finite
    .execute()
)

# Filtra per data: start_timestamp è unix, converti
import datetime
day_start = int(datetime.datetime.strptime(DATE, "%Y-%m-%d").replace(hour=0, minute=0).timestamp())
day_end   = int(datetime.datetime.strptime(DATE, "%Y-%m-%d").replace(hour=23, minute=59).timestamp())

# Ri-query con filtro timestamp
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


def get_player_rows(match_db_id, sofascore_id, gameweek, season_year):
    """Chiama /lineups e restituisce lista di righe player_stats."""
    url = f"https://api.sofascore.com/api/v1/event/{sofascore_id}/lineups"
    r = session.get(url, headers=headers)
    if r.status_code != 200:
        print(f"  Errore lineups {sofascore_id}: {r.status_code}")
        return []

    data = r.json()
    rows = []

    for side in ["home", "away"]:
        team_data = data.get(side, {})
        team_name = team_data.get("team", {}).get("name", "")
        is_home = (side == "home")

        players = team_data.get("players", [])
        for p in players:
            player = p.get("player", {})
            stats  = p.get("statistics", {})

            rows.append({
                "match_id":       match_db_id,
                "sofascore_id":   sofascore_id,
                "player_id":      player.get("id"),
                "player_name":    player.get("name"),
                "team_name":      team_name,
                "is_home":        is_home,
                "goals":          stats.get("goals", 0) or 0,
                "goals_penalty":  stats.get("goalsPenalty", 0) or 0,
                "penalty_miss":   stats.get("penaltyMiss", 0) or 0,
                "penalty_save":   stats.get("penaltySave", 0) or 0,
                "yellow_card":    stats.get("yellowCard", 0) or 0,
                "red_card":       (stats.get("redCard", 0) or 0) + (stats.get("yellowRedCard", 0) or 0),
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

    res = (
        supabase.table("player_stats")
        .upsert(rows, on_conflict="sofascore_id,player_id")
        .execute()
    )
    total_rows += len(rows)
    print(f"  Salvati {len(rows)} giocatori ✅")

print(f"\nTotale righe upsert: {total_rows} ✅")
