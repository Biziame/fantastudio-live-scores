import os
import datetime
import json
import subprocess
from supabase import create_client

# --- CONFIG ---
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

GAMEWEEK_ENV = os.environ.get("GAMEWEEK", "").strip()
SKIP_TIME_CHECK = os.environ.get("SKIP_TIME_CHECK", "false").strip().lower() == "true"

MESI = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4,
    "maggio": 5, "giugno": 6, "luglio": 7, "agosto": 8,
    "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12
}

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 1. Determina gameweek ---
if GAMEWEEK_ENV:
    current_gameweek = int(GAMEWEEK_ENV)
    print(f"Gameweek manuale: {current_gameweek}")
else:
    res = supabase.table("probabili_formazioni").select("gameweek").order("gameweek", desc=True).limit(1).execute()
    if not res.data:
        print("Nessun dato in probabili_formazioni, uscita.")
        exit(0)
    current_gameweek = res.data[0]["gameweek"]
    print(f"Gameweek corrente (auto): {current_gameweek}")

# --- 2. Prendi tutte le partite di quel gameweek ---
partite_db = supabase.table("probabili_formazioni") \
    .select("home_team, away_team, match_date, match_time, gameweek, season") \
    .eq("gameweek", current_gameweek) \
    .execute().data

if not partite_db:
    print(f"Nessuna partita trovata per giornata {current_gameweek}, uscita.")
    exit(0)

print(f"Partite nella giornata {current_gameweek}: {len(partite_db)}")

# --- 3. Controlla la finestra orario ---
def parse_match_datetime(match_date: str, match_time: str) -> datetime.datetime | None:
    try:
        parts = match_date.strip().lower().split()
        giorno = int(parts[0])
        mese = MESI.get(parts[1], 0)
        if not mese:
            return None
        anno = datetime.datetime.now().year
        ora, minuto = map(int, match_time.strip().split(":"))
        return datetime.datetime(anno, mese, giorno, ora, minuto)
    except Exception as e:
        print(f"  Errore parsing data '{match_date} {match_time}': {e}")
        return None

now = datetime.datetime.now()
orari = []
for p in partite_db:
    dt = parse_match_datetime(p["match_date"], p["match_time"])
    if dt:
        orari.append(dt)

if not orari:
    print("Impossibile determinare gli orari delle partite, uscita.")
    exit(0)

prima_partita = min(orari)
ultima_partita = max(orari)
finestra_start = prima_partita - datetime.timedelta(minutes=30)
finestra_end   = ultima_partita + datetime.timedelta(minutes=90)

print(f"Finestra attiva: {finestra_start.strftime('%H:%M')} - {finestra_end.strftime('%H:%M')} ({finestra_start.date()})")
print(f"Ora attuale:     {now.strftime('%H:%M')}")

if SKIP_TIME_CHECK:
    print("SKIP_TIME_CHECK=true, salto il controllo finestra orario.")
elif not (finestra_start <= now <= finestra_end):
    print("Fuori dalla finestra orario, uscita.")
    exit(0)

print("Dentro la finestra, procedo con fetch lineups/stats...")

# --- 4. Prendi le partite finished/inprogress da risultati_live per questo gameweek ---
result = supabase.table("risultati_live") \
    .select("id, sofascore_id, home_team, away_team, gameweek, season_year") \
    .eq("gameweek", current_gameweek) \
    .in_("status_type", ["finished", "inprogress"]) \
    .execute()

partite = result.data
print(f"Partite trovate (finished + inprogress): {len(partite)}")

if not partite:
    print("Nessuna partita in corso o finita per questa giornata, uscita.")
    exit(0)

# --- 5. Sessione SofaScore ---
def get_incidents(sofascore_id):
    result = subprocess.run(
        ["node", "fetch_sofascore.js", "incidents", str(sofascore_id)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  Errore incidents {sofascore_id}: {result.returncode}")
        return {}

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"  Errore parsing incidents {sofascore_id}")
        return {}

    incidents_map = {}

    def ensure(pid):
        if pid not in incidents_map:
            incidents_map[pid] = {
                "goals": 0, "goals_penalty": 0,
                "penalty_miss": 0, "penalty_save": 0,
                "yellow_card": 0, "red_card": 0,
            }

    for inc in data.get("incidents", []):
        inc_type  = inc.get("incidentType", "")
        inc_class = inc.get("incidentClass", "")
        from_type = inc.get("from", "")
        player    = inc.get("player")
        pid       = player.get("id") if player else None

        if inc_type == "card" and pid:
            ensure(pid)
            if inc_class == "yellow":
                incidents_map[pid]["yellow_card"] += 1
            elif inc_class in ("red", "yellowRed"):
                incidents_map[pid]["red_card"] += 1

        elif inc_type == "goal" and inc_class != "ownGoal":
            if from_type == "penalty":
                if inc_class == "saved":
                    if pid:
                        ensure(pid)
                        incidents_map[pid]["penalty_miss"] += 1
                    gk = inc.get("goalkeeper")
                    if gk and gk.get("id"):
                        ensure(gk["id"])
                        incidents_map[gk["id"]]["penalty_save"] += 1
                elif inc_class == "missed" and pid:
                    ensure(pid)
                    incidents_map[pid]["penalty_miss"] += 1
                else:
                    if pid:
                        ensure(pid)
                        incidents_map[pid]["goals"] += 1
                        incidents_map[pid]["goals_penalty"] += 1
            else:
                if pid:
                    ensure(pid)
                    incidents_map[pid]["goals"] += 1

    return incidents_map


def get_player_rows(match_db_id, sofascore_id, gameweek, season_year):
    result = subprocess.run(
        ["node", "fetch_sofascore.js", "lineups", str(sofascore_id)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  Errore lineups {sofascore_id}: {result.returncode}")
        return []

    try:
        lineups_data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"  Errore parsing lineups {sofascore_id}")
        return []

    incidents = get_incidents(sofascore_id)
    rows = []

    for side in ["home", "away"]:
        team_data = lineups_data.get(side, {})
        team_name = team_data.get("team", {}).get("name", "")
        is_home   = (side == "home")

        for p in team_data.get("players", []):
            player = p.get("player", {})
            stats  = p.get("statistics", {})
            pid    = player.get("id")
            inc    = incidents.get(pid, {})

            rows.append({
                "match_id":       match_db_id,
                "sofascore_id":   sofascore_id,
                "gameweek":       gameweek,
                "season_year":    season_year,
                "player_id":      pid,
                "player_name":    player.get("name"),
                "team_name":      team_name,
                "is_home":        is_home,
                "goals":          inc.get("goals", 0),
                "goals_penalty":  inc.get("goals_penalty", 0),
                "penalty_miss":   inc.get("penalty_miss", 0),
                "penalty_save":   inc.get("penalty_save", 0),
                "yellow_card":    inc.get("yellow_card", 0),
                "red_card":       inc.get("red_card", 0),
                "minutes_played": stats.get("minutesPlayed", 0) or 0,
            })

    return rows


# --- 6. Processa ogni partita ---
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

    marcatori = [f"{r['player_name']} ({r['goals']} gol)" for r in rows if r["goals"] > 0]
    ammoniti  = [r["player_name"] for r in rows if r["yellow_card"] > 0]
    espulsi   = [r["player_name"] for r in rows if r["red_card"] > 0]

    if marcatori: print(f"  Marcatori:  {marcatori}")
    if ammoniti:  print(f"  Ammoniti:   {ammoniti}")
    if espulsi:   print(f"  Espulsi:    {espulsi}")

    supabase.table("player_stats").upsert(rows, on_conflict="sofascore_id,player_id").execute()
    total_rows += len(rows)
    print(f"  Salvati {len(rows)} giocatori ✅")

print(f"\nTotale righe upsert: {total_rows} ✅")
