# fantastudio-live-scores

GitHub Action che fetcha automaticamente i risultati live di **Serie A** da SofaScore ogni 5 minuti e li salva su Supabase.

## Setup

### 1. Aggiungi i secrets su GitHub
Vai su **Settings → Secrets and variables → Actions → New repository secret** e aggiungi:

| Secret | Valore |
|--------|--------|
| `SUPABASE_URL` | `https://xxxxx.supabase.co` |
| `SUPABASE_KEY` | La tua `service_role` key |

### 2. Tabella Supabase
Esegui questo SQL nel tuo SQL Editor:

```sql
create table risultati_live (
  id uuid default gen_random_uuid() primary key,
  sofascore_id bigint unique not null,
  home_team text not null,
  home_team_id integer,
  home_team_code text,
  away_team text not null,
  away_team_id integer,
  away_team_code text,
  home_score integer,
  away_score integer,
  home_score_p1 integer,
  away_score_p1 integer,
  status_code integer,
  status_type text not null,
  winner_code integer,
  start_timestamp bigint,
  tournament_name text,
  tournament_id integer,
  season_year text,
  gameweek integer,
  updated_at timestamp with time zone default now()
);
```

### 3. Lancia manualmente per testare
Vai su **Actions → Fetch Serie A Live Scores → Run workflow**

## Schedule
L'action gira ogni **5 minuti** dalle **14:00 alle 01:00** ora italiana.
Puoi modificare il cron in `.github/workflows/fetch.yml`.
