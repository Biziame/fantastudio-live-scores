# fantastudio-live-scores

Raccolta automatica dei risultati live e delle statistiche giocatori della Serie A tramite SofaScore, con salvataggio su Supabase. Utilizzato come backend dati per l'applicazione [Fantastudio](https://github.com/Biziame/fantastudio).

---

## Panoramica

Il repository contiene due script Python eseguiti in sequenza da una GitHub Action:

| Script | Funzione |
|---|---|
| `fetch_scores.py` | Scarica i punteggi live/finali di tutte le partite Serie A della giornata corrente e li salva nella tabella `risultati_live` su Supabase |
| `fetch_lineups.py` | Per ogni partita in corso o terminata, scarica le formazioni ufficiali e gli eventi (gol, cartellini, rigori) e li salva nella tabella `player_stats` su Supabase |

Entrambi gli script leggono la gameweek corrente dalla tabella `probabili_formazioni` già presente su Supabase (popolata da un processo separato), e operano solo all'interno di una **finestra oraria** calcolata automaticamente sugli orari delle partite.

---

## Flusso di Esecuzione

```
GitHub Action (manuale)
        │
        ▼
 fetch_scores.py
   1. Determina gameweek (manuale o da Supabase)
   2. Controlla le 2 GW più recenti: se la precedente è ancora in finestra, usa quella
   3. Calcola finestra oraria: (prima partita - 30min) → (ultima partita + 120min)
   4. Se fuori finestra → exit
   5. Fetcha SofaScore per ogni data unica delle partite
   6. Filtra solo eventi Serie A (tournament ID = 23)
   7. Upsert su tabella `risultati_live` (chiave: sofascore_id)
        │
        ▼
 fetch_lineups.py
   1. Stessa logica gameweek e finestra oraria
   2. Legge da `risultati_live` solo le partite con status `inprogress` o `finished`
   3. Per ogni partita → fetch lineups da SofaScore
   4. Per ogni partita → fetch incidents (gol, cartellini, rigori) da SofaScore
   5. Upsert su tabella `player_stats` (chiave: sofascore_id + player_id)
```

---

## Finestra Oraria

Per evitare chiamate API inutili, entrambi gli script calcolano una finestra temporale basata sugli orari reali delle partite della giornata:

```
finestra_start = orario prima partita  - 30 minuti
finestra_end   = orario ultima partita + 120 minuti
```

I 120 minuti finali coprono la durata standard di una partita (90 min) più i recuperi tipici.

### Logica doppia gameweek

`fetch_scores.py` gestisce il caso in cui nel database siano già presenti le partite della giornata successiva mentre quella corrente è ancora in corso:

1. Recupera le **2 gameweek più recenti** da `probabili_formazioni`
2. Controlla se la **gameweek precedente** è ancora dentro la sua finestra oraria
3. Se sì → usa quella; altrimenti → usa la più recente

Questo evita di fetchare la giornata N+1 mentre le partite della giornata N sono ancora in corso.

### Override manuale

Impostando `SKIP_TIME_CHECK=true`, il controllo della finestra viene completamente ignorato. Utile per esecuzioni manuali di test o recupero dati a posteriori.

---

## Tabelle Supabase

### `probabili_formazioni` (lettura)
Fonte di verità per le gameweek disponibili e gli orari delle partite. Popolata da un processo esterno separato.

Campi utilizzati: `gameweek`, `match_date`, `match_time`, `home_team`, `away_team`, `season`

> Il campo `match_date` è in formato italiano testuale (es. `"20 aprile"`), il campo `match_time` in formato `"HH:MM"`.

### `risultati_live` (scrittura)
Contiene i risultati delle partite Serie A aggiornati in tempo reale.

| Campo | Descrizione |
|---|---|
| `sofascore_id` | ID univoco partita su SofaScore (chiave upsert) |
| `home_team` / `away_team` | Nomi squadre |
| `home_team_id` / `away_team_id` | ID squadre su SofaScore |
| `home_team_code` / `away_team_code` | Codici brevi squadre (es. `INT`) |
| `home_score` / `away_score` | Punteggio attuale |
| `home_score_p1` / `away_score_p1` | Punteggio primo tempo |
| `status_code` | Codice numerico stato partita |
| `status_type` | Stato testuale (`not_started`, `inprogress`, `finished`) |
| `winner_code` | Codice vincitore (1=casa, 2=trasferta, 3=pareggio) |
| `start_timestamp` | Timestamp Unix inizio partita |
| `tournament_name` / `tournament_id` | Nome e ID torneo |
| `season_year` | Anno stagione normalizzato (es. `"2025"`) |
| `gameweek` | Numero giornata |

### `player_stats` (scrittura)
Contiene le statistiche per singolo giocatore per ogni partita.

| Campo | Descrizione |
|---|---|
| `sofascore_id` + `player_id` | Chiave upsert composita |
| `match_id` | Riferimento a `risultati_live.id` |
| `player_name` / `player_id` | Nome e ID giocatore |
| `team_name` / `is_home` | Squadra e lato campo |
| `goals` / `goals_penalty` | Gol totali e su rigore |
| `penalty_miss` / `penalty_save` | Rigori sbagliati / parati |
| `yellow_card` / `red_card` | Cartellini |
| `minutes_played` | Minuti giocati |
| `gameweek` / `season_year` | Giornata e stagione |

---

## GitHub Action

Il workflow `.github/workflows/fetch.yml` si chiama **Fetch Serie A Live Scores** ed è di tipo **manuale** (`workflow_dispatch`): non ha trigger automatici a cadenza fissa, va lanciato a mano dall'interfaccia GitHub Actions.

### Input disponibili

| Input | Descrizione | Default |
|---|---|---|
| `gameweek` | Numero giornata da scaricare. Se vuoto, usa la più recente da Supabase | `` (vuoto) |
| `skip_time_check` | Se `true`, ignora il controllo della finestra oraria | `false` |

### Steps del workflow

1. **Checkout** del repository
2. **Setup Python 3.11**
3. **Install dependencies** (`pip install -r requirements.txt`)
4. **Run `fetch_scores.py`** — punteggi live
5. **Run `fetch_lineups.py`** — formazioni e statistiche giocatori

Entrambi gli script ricevono le variabili `SUPABASE_URL`, `SUPABASE_KEY`, `GAMEWEEK` e `SKIP_TIME_CHECK` come variabili d'ambiente.

### Secrets richiesti

Configurare nei **Repository Secrets** di GitHub:

| Secret | Descrizione |
|---|---|
| `SUPABASE_URL` | URL del progetto Supabase |
| `SUPABASE_KEY` | Chiave `service_role` o `anon` con permessi di lettura/scrittura |

---

## Dipendenze

```
tls_client   # Sessione HTTP che simula Chrome per bypassare i controlli SofaScore
supabase     # Client ufficiale Python per Supabase
zoneinfo     # Gestione fuso orario Europe/Rome (built-in da Python 3.9+)
```

---

## Collegamento con Fantastudio

I dati scritti da questo repository vengono letti in tempo reale dall'app [Fantastudio](https://github.com/Biziame/fantastudio) tramite:

- **Realtime Supabase** su `player_stats` → aggiorna automaticamente le statistiche nel dialog di ogni partita quando la partita è live
- **Query diretta** su `risultati_live` → mostra punteggi e stato partita nelle card della homepage
- **Query diretta** su `probabili_formazioni` → mostra probabili formazioni e ballottaggi per le partite non ancora iniziate

---

## Struttura Repository

```
fantastudio-live-scores/
├── .github/
│   └── workflows/
│       └── fetch.yml          # GitHub Action manuale
├── fetch_scores.py            # Script punteggi live
├── fetch_lineups.py           # Script formazioni e statistiche
├── requirements.txt           # Dipendenze Python
└── README.md
```
