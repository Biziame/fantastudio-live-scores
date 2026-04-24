import os
import datetime
import json
import subprocess
import zoneinfo
from supabase import create_client

# --- CONFIG ---
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SERIE_A_ID = 23

GAMEWEEK_ENV = os.environ.get("GAMEWEEK", "").strip()
SKIP_TIME_CHECK = os.environ.get("SKIP_TIME_CHECK", "false").strip().lower() == "true"

MESI = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4,
    "maggio": 5, "giugno": 6, "luglio": 7, "agosto": 8,
    "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12
}

ROMA = zoneinfo.ZoneInfo("Europe/Rome")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def now_it() -> datetime.datetime:
    """Ora corrente nel fuso orario italiano, naive (senza tzinfo) per confronti uniformi."""
    return datetime.datetime.now(ROMA).replace(tzinfo=None)


# --- UTILITY: parsing data/ora partita ---
def parse_match_datetime(match_date: str, match_time: str) -> datetime.datetime | None:
    try:
        parts = match_date.strip().lower().split()
        giorno = int(parts[0])
        mese = MESI.get(parts[1], 0)
        if not mese:
            return None
        anno = now_it().year
        ora, minuto = map(int, match_time.strip().split(":"))
        return datetime.datetime(anno, mese, giorno, ora, minuto)
    except Exception as e:
        print(f"  Errore parsing data '{match_date} {match_time}': {e}")
        return None


def get_finestra(partite: list) -> tuple[datetime.datetime, datetime.datetime] | None:
    orari = [parse_match_datetime(p["match_date"], p["match_time"]) for p in partite]
    orari = [dt for dt in orari if dt]
    if not orari:
        return None
    return min(orari) - datetime.timedelta(minutes=30), max(orari) + datetime.timedelta(minutes=120)


# --- 1. Determina gameweek ---
if GAMEWEEK_ENV:
    current_gameweek = int(GAMEWEEK_ENV)
    print(f"Gameweek manuale: {current_gameweek}")
else:
    res = supabase.table("probabili_formazioni").select("gameweek").order("gameweek", desc=True).limit(2).execute()
    if not res.data:
        print("Nessun dato in probabili_formazioni, uscita.")
        exit(0)

    gameweeks_disponibili = sorted(set(r["gameweek"] for r in res.data), reverse=True)
    current_gameweek = gameweeks_disponibili[0]  # default: la più recente

    if len(gameweeks_disponibili) >= 2:
        gw_precedente = gameweeks_disponibili[1]
        partite_prec = supabase.table("probabili_formazioni") \
            .select("match_date, match_time") \
            .eq("gameweek", gw_precedente) \
            .execute().data

        finestra_prec = get_finestra(partite_prec)
        if finestra_prec:
            now = now_it()
            fin_start, fin_end = finestra_prec
            if fin_start <= now <= fin_end:
                current_gameweek = gw_precedente
                print(f"Gameweek precedente ({gw_precedente}) ancora in finestra ({fin_start.strftime('%H:%M')}–{fin_end.strftime('%H:%M')}), uso quella.")

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
now = now_it()
orari = [parse_match_datetime(p["match_date"], p["match_time"]) for p in partite_db]
orari = [dt for dt in orari if dt]

if not orari:
    print("Impossibile determinare gli orari delle partite, uscita.")
    exit(0)

prima_partita = min(orari)
ultima_partita = max(orari)
finestra_start = prima_partita - datetime.timedelta(minutes=30)
finestra_end   = ultima_partita + datetime.timedelta(minutes=120)

print(f"Finestra attiva: {finestra_start.strftime('%H:%M')} - {finestra_end.strftime('%H:%M')} ({finestra_start.date()})")
print(f"Ora attuale:     {now.strftime('%H:%M')} (IT)")

if SKIP_TIME_CHECK:
    print("SKIP_TIME_CHECK=true, salto il controllo finestra orario.")
elif not (finestra_start <= now <= finestra_end):
    print("Fuori dalla finestra orario, uscita.")
    exit(0)

print("Dentro la finestra, procedo con il fetch SofaScore...")

# --- 4. Fetch SofaScore per ogni data unica delle partite ---
date_uniche = set(dt.strftime("%Y-%m-%d") for dt in orari)
print(f"Date da fetchare: {date_uniche}")

all_partite_sofa = []
for sofa_date in date_uniche:
    result = subprocess.run(
        ["node", "fetch_sofascore.js", "date", sofa_date],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"SofaScore {sofa_date}: errore subprocess ({result.returncode})")
        print(f"  STDERR: {result.stderr.strip()}")
        print(f"  STDOUT: {result.stdout.strip()}")
        continue
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"SofaScore {sofa_date}: errore parsing JSON")
        continue
    events = data.get("events", [])
    serie_a = [e for e in events if e.get("tournament", {}).get("uniqueTournament", {}).get("id") == SERIE_A_ID]
    print(f"SofaScore {sofa_date}: partite Serie A trovate: {len(serie_a)}")
    all_partite_sofa.extend(serie_a)

if not all_partite_sofa:
    print("Nessuna partita Serie A trovata su SofaScore, uscita.")
    exit(0)


def normalize_season(season_str: str) -> str:
    if "/" in season_str:
        first = season_str.split("/")[0].strip()
        return f"20{first}" if len(first) == 2 else first
    return season_str


# --- 5. Deduplica per sofascore_id ---
seen = set()
rows = []
for e in all_partite_sofa:
    sid = e["id"]
    if sid in seen:
        continue
    seen.add(sid)
    raw_season = e["season"]["year"]
    rows.append({
        "sofascore_id":   sid,
        "home_team":      e["homeTeam"]["name"],
        "home_team_id":   e["homeTeam"]["id"],
        "home_team_code": e["homeTeam"]["nameCode"],
        "away_team":      e["awayTeam"]["name"],
        "away_team_id":   e["awayTeam"]["id"],
        "away_team_code": e["awayTeam"]["nameCode"],
        "home_score":     e.get("homeScore", {}).get("current"),
        "away_score":     e.get("awayScore", {}).get("current"),
        "home_score_p1":  e.get("homeScore", {}).get("period1"),
        "away_score_p1":  e.get("awayScore", {}).get("period1"),
        "status_code":    e["status"]["code"],
        "status_type":    e["status"]["type"],
        "winner_code":    e.get("winnerCode"),
        "start_timestamp": e["startTimestamp"],
        "tournament_name": e["tournament"]["name"],
        "tournament_id":   e["tournament"]["uniqueTournament"]["id"],
        "season_year":     normalize_season(raw_season),
        "gameweek":        e.get("roundInfo", {}).get("round"),
    })

print(f"Righe uniche da inserire: {len(rows)}")

result = supabase.table("risultati_live").upsert(rows, on_conflict="sofascore_id").execute()
print(f"\nUpsert risultati_live: {len(rows)} righe ✅")
for row in rows:
    hs = row["home_score"] if row["home_score"] is not None else "-"
    aw = row["away_score"] if row["away_score"] is not None else "-"
    print(f"  {row['home_team']} {hs} - {aw} {row['away_team']} [{row['status_type']}]")
