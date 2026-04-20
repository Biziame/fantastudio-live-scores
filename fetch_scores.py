import tls_client
import os
import datetime
from supabase import create_client

# --- CONFIG ---
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
SERIE_A_ID = 23

MESI = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4,
    "maggio": 5, "giugno": 6, "luglio": 7, "agosto": 8,
    "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12
}

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 1. Trova il gameweek più alto in probabili_formazioni ---
res = supabase.table("probabili_formazioni").select("gameweek").order("gameweek", desc=True).limit(1).execute()
if not res.data:
    print("Nessun dato in probabili_formazioni, uscita.")
    exit(0)

current_gameweek = res.data[0]["gameweek"]
print(f"Gameweek corrente: {current_gameweek}")

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

if not (finestra_start <= now <= finestra_end):
    print("Fuori dalla finestra orario, uscita.")
    exit(0)

print("Dentro la finestra, procedo con il fetch SofaScore...")

# --- 4. Fetch SofaScore per ogni data unica delle partite ---
session = tls_client.Session(
    client_identifier="chrome_124",
    random_tls_extension_order=True
)
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
}

date_uniche = set(dt.strftime("%Y-%m-%d") for dt in orari)
print(f"Date da fetchare: {date_uniche}")

all_partite_sofa = []
for sofa_date in date_uniche:
    url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{sofa_date}"
    r = session.get(url, headers=headers)
    print(f"SofaScore {sofa_date}: {r.status_code}")
    if r.status_code != 200:
        print(f"  Errore: {r.text[:200]}")
        continue
    events = r.json().get("events", [])
    serie_a = [e for e in events if e.get("tournament", {}).get("uniqueTournament", {}).get("id") == SERIE_A_ID]
    print(f"  Partite Serie A trovate: {len(serie_a)}")
    all_partite_sofa.extend(serie_a)

if not all_partite_sofa:
    print("Nessuna partita Serie A trovata su SofaScore, uscita.")
    exit(0)


def normalize_season(season_str: str) -> str:
    if "/" in season_str:
        first = season_str.split("/")[0].strip()
        return f"20{first}" if len(first) == 2 else first
    return season_str


# --- 5. Deduplication per sofascore_id (SofaScore può restituire la stessa partita su più date) ---
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
