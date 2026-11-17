# Projektplan: energy-market-insights (MVP, ca. 2 Wochen)

## Leitfrage

**Wann sollte ein Betrieb morgen seine energieintensiven Prozesse laufen lassen, und wie viel spart er dadurch?**

Abgeleitete Teilfragen:

1. Wie gut lässt sich der Day-Ahead-Preis (DE-LU) für morgen aus den SMARD-Prognosen (Wind, Solar, Verbrauch, Residuallast) vorhersagen, und erkennt die Prognose die **günstigsten Stunden**?
2. Wie viel spart eine Lastverschiebung gegenüber einer festen Schicht, und wie weit liegt sie hinter einer Planung mit perfekter Preiskenntnis zurück (**Regret**)?
3. Kontext: Wie hängen EE-Anteil, negative Preise und Preisniveau zusammen? Das ist die Motivation für die Verschiebung.

## Fachliche Leitplanken

- **Entscheidungszeitpunkt:** Der Day-Ahead-Preis für morgen wird heute gegen ca. 12:45 Uhr (MEZ/MESZ) veröffentlicht. Es gibt deshalb zwei Modi:
  - **Vor der Auktion** (Planung bis ca. 12:00): Planung auf Basis der **Preisprognose**. Nur hier bringt das Modell einen Mehrwert.
  - **Nach Veröffentlichung**: Planung auf Basis der **tatsächlichen Preise**. Der Regret ist dann trivialerweise 0.
  Im Backtest wird immer der Modus „vor der Auktion“ simuliert.
- **Kein Leakage:** Als Features für Tag D+1 dienen nur Werte, die am Tag D um 12:00 bekannt sind: SMARD-Day-Ahead-Prognosen für D+1, Preise bis D, Kalender.
- **Zeitauflösung:** Seit 01.10.2025 gibt es Preise in 15-Minuten-Auflösung. Die Rohdaten werden in nativer Auflösung gespeichert und im Cleaning **einheitlich auf Stundenwerte aggregiert**:
  - Preise (€/MWh): Mittelwert der vier Viertelstunden
  - Energiemengen (MWh je Intervall): Summe
  - Eine Stunde mit fehlenden Viertelstunden wird markiert und nicht stillschweigend gemittelt.
- **Zeitzonen:** Speicherung in UTC (Unix-ms wie bei SMARD), Anzeige und Planung in `Europe/Berlin`. Tage mit 23 bzw. 25 Stunden sind ausdrücklich getestet.
- **Kostenbegriff:** Kosten = Σ Leistung [kW] × Zeit [h] × Börsenpreis [€/MWh] / 1000. Netzentgelte, Leistungspreis, Umlagen und Steuern sind **nicht** modelliert (siehe README, Next Steps).

## Phase 0: Machbarkeitscheck (erster Umsetzungsschritt)

Ziel: Bevor der Rest gebaut wird, klären, ob die Daten und der Grundansatz tragen.

1. **Ein Jahr Daten laden** (z. B. die letzten 12 Monate): Preis DE-LU, Netzlast, Erzeugung nach Energieträger, SMARD-Prognosen (Wind onshore/offshore, PV, Verbrauch). Dabei die Filter-IDs und Auflösungen gegen die SMARD-API verifizieren und in `smard/series.py` festhalten.
2. **Streudiagramm Preis vs. EE-Anteil**, eingefärbt nach Stunde bzw. Jahreszeit, dazu Binned-Mittelwerte.
3. **Schnelles Testmodell:** Ridge auf Residuallast-Prognose, Kalender und Preis-Lags gegen die naive Baseline „gleiche Stunde Vortag“. Bewertet werden MAE und die Trefferquote der günstigsten Stunden.
4. **Go/No-Go:** Das Modell schlägt die Baseline sichtbar (MAE und Top-k-Treffer). Andernfalls wird das Feature-Set überdacht, bevor der Scheduler gebaut wird.

Ergebnis: `notebooks/00_feasibility.ipynb` mit kurzem Fazit. Der Code daraus wandert danach in die Module.

## Projektstruktur

```
energy-market-insights/
├── src/emi/
│   ├── config.py            # Settings aus Env/.env (DB-Pfad, Flags, API-Key)
│   ├── smard/
│   │   ├── client.py        # HTTP-Client (index → Chunks → Daten), Retry, Timeout
│   │   └── series.py        # Filter-ID ↔ Name/Region/Einheit/Kategorie/Auflösung
│   ├── db.py                # Schema, Upsert, Lesefunktionen
│   ├── ingest.py            # inkrementeller Download
│   ├── cleaning.py          # 15 min → 1 h, Lücken, DST, Wide-Tabelle
│   ├── anomalies.py         # negative Preise, Ausreißer
│   ├── features.py          # Prognose-Features (Residuallast etc.), Kalender, Lags
│   ├── forecast.py          # Baseline + Ridge, Backtest, Ranking-Metriken
│   ├── scheduling/
│   │   ├── loads.py         # YAML laden + validieren → Load-Objekte
│   │   ├── scheduler.py     # Sliding Window / günstigste Stunden, Leistungsgrenze
│   │   └── backtest.py      # Ersparnis vs. feste Schicht, Regret vs. Perfect Foresight
│   ├── queries.py           # gemeinsame Abfrage-API für Dashboard + Assistent
│   ├── dashboard/           # Flask-App, Plotly-Charts, Templates
│   ├── assistant/
│   │   ├── tools.py         # plan_fuer_morgen, ersparnis, negative_preise
│   │   └── agent.py         # Function-Calling-Loop (abschaltbar)
│   └── cli.py               # emi ingest | clean | train | plan | backtest | serve
├── config/loads.example.yaml
├── notebooks/00_feasibility.ipynb
├── tests/ (+ tests/fixtures/)
├── docs/PLAN.md
├── .github/workflows/ci.yml
├── Dockerfile, .dockerignore, docker-compose.yml
├── pyproject.toml, .env.example
└── README.md
```

## Kernbaustein Lastverschiebung

### Lastdefinition (YAML)

```yaml
power_limit_kw: 800          # optional: gemeinsame Leistungsgrenze aller Lasten
loads:
  - name: kompressor
    power_kw: 250
    duration_h: 3
    earliest_start: "06:00"
    latest_end: "22:00"
    mode: contiguous          # contiguous (am Stück) | divisible (teilbar)
    fixed_start: "06:00"      # Referenz "feste Schicht" für die Ersparnis
  - name: trocknung
    power_kw: 400
    duration_h: 4
    earliest_start: "00:00"
    latest_end: "23:59"
    mode: divisible
    fixed_start: "08:00"
```

- Die Validierung (Pydantic oder eine Dataclass mit Checks) prüft Dauer ≤ Zeitfenster, Leistung > 0 und Stundenraster. Im MVP sind Dauer und Zeiten ganze Stunden.
- `latest_end` mit Wert über Mitternacht ist im MVP nicht vorgesehen. Ein Plan gilt jeweils für einen Kalendertag (lokal).

### Algorithmus (MVP)

- **contiguous:** Sliding Window über alle zulässigen Startstunden, Auswahl des Fensters mit der minimalen Preissumme. Laufzeit O(n), bei n ≤ 25 Stunden pro Tag.
- **divisible:** die k günstigsten Stunden innerhalb des Fensters.
- **Gemeinsame Leistungsgrenze (optional):** Die Lasten werden greedy nacheinander eingeplant, absteigend nach Energiemenge (kWh). Jede Last bekommt das günstigste Fenster, das die Restkapazität nicht überschreitet. Das ist bewusst eine Heuristik. Sie ist im README so benannt, und ein exakter MILP-Ansatz steht unter Next Steps.
- Ist eine Last nicht einplanbar, gibt es einen klaren Fehler bzw. Status „infeasible“ statt eines stillen Teilplans.

### Kennzahlen und Backtest

Für jeden Tag D+1 im Backtest-Zeitraum (mehrere vergangene Monate):

| Kennzahl | Definition |
|---|---|
| `cost_fixed` | Kosten der festen Schicht (`fixed_start`) zu tatsächlichen Preisen |
| `cost_plan` | Plan auf Basis der **Prognose**, bewertet zu **tatsächlichen** Preisen |
| `cost_perfect` | Plan auf Basis der tatsächlichen Preise (Perfect Foresight) |
| `cost_baseline_plan` | Plan auf Basis der naiven Baseline-Prognose, bewertet zu tatsächlichen Preisen |
| **Ersparnis** | `cost_fixed − cost_plan` (absolut € und in %) |
| **Regret** | `cost_plan − cost_perfect` (≥ 0) |
| **Mehrwert Modell** | `cost_baseline_plan − cost_plan` |

Ausgewertet wird pro Tag, Monat und über den gesamten Zeitraum. Hochgerechnet auf ein Jahr gibt das die Kernaussage im README.

## Preisprognose

- **Inputs:** SMARD-Day-Ahead-Prognosen für D+1: Wind onshore, Wind offshore, PV, Verbrauch, daraus abgeleitet die **Residuallast** (Verbrauch − Wind − PV). Dazu Kalender (Stunde, Wochentag, Feiertag über `holidays`) und Preis-Lags (letzter bekannter Tag D, D−6).
- **Modelle:** naive Baseline (gleiche Stunde am Vortag bzw. an D) und Ridge-Regression. Gradient Boosting ist optional und erst nach dem MVP vorgesehen.
- **Validierung:** rollierender Backtest (Expanding Window, tägliches Re-Fit oder wöchentlich zur Beschleunigung).
- **Metriken:**
  - MAE und RMSE gegen die Baseline
  - **Top-k-Trefferquote:** Anteil der tatsächlich k günstigsten Stunden, die die Prognose ebenfalls unter ihren k günstigsten hat (k = 3, 4, 6)
  - Spearman-Rangkorrelation je Tag
  - indirekt der Regret aus dem Scheduling-Backtest, also die eigentliche Zielgröße
- Eine Lastprognose ist **nicht mehr** Teil des MVP, denn die SMARD-Verbrauchsprognose wird direkt genutzt.

## Datenmodell (SQLite)

```
series        (series_id TEXT PK, smard_filter INT, region TEXT, name TEXT, unit TEXT,
               category TEXT,       -- generation|load|price|forecast_generation|forecast_load
               resolution TEXT)     -- hour|quarterhour
observations  (series_id TEXT FK, ts_utc INT, resolution TEXT, value REAL,
               PRIMARY KEY (series_id, ts_utc, resolution))    -- Rohdaten, native Auflösung
fetch_log     (series_id TEXT, resolution TEXT, chunk_ts INT, fetched_at TEXT, n_rows INT,
               PRIMARY KEY (series_id, resolution, chunk_ts))
hourly_clean  (ts_utc INT PK, price REAL, load REAL, wind_on REAL, wind_off REAL, pv REAL, …,
               fc_load REAL, fc_wind_on REAL, fc_wind_off REAL, fc_pv REAL, fc_residual REAL,
               re_share REAL, is_negative_price INT, is_outlier INT,
               is_interpolated INT, is_incomplete_hour INT)
model_runs    (run_id TEXT PK, model TEXT, trained_at TEXT, train_start INT, train_end INT,
               mae REAL, baseline_mae REAL, topk_hit REAL, params_json TEXT)
price_forecasts (run_id TEXT FK, target_day TEXT, ts_utc INT, predicted REAL,
                 PRIMARY KEY (run_id, ts_utc))
schedule_results (run_id TEXT FK, day TEXT, load_name TEXT, price_source TEXT,  -- forecast|baseline|perfect|fixed
                  start_ts_list TEXT, cost_eur REAL,
                  PRIMARY KEY (run_id, day, load_name, price_source))
```

Die Lasten selbst stehen in der YAML-Datei, nicht in der Datenbank. In `schedule_results` wird pro Lauf ein Hash der YAML gespeichert, damit Ergebnisse nachvollziehbar bleiben.

## LLM-Assistent (optional, letzter Schritt)

- Aktiv nur bei `ASSISTANT_ENABLED=true` **und** gesetztem API-Key (ausschließlich aus `.env`). Sonst ist die Seite bzw. der Endpoint deaktiviert.
- Feste Funktionen (Tools), alle als dünne Wrapper um `queries.py` bzw. `scheduling`:
  - `plan_fuer_morgen(last)`: optimaler Startzeitpunkt bzw. optimale Stunden und erwartete Kosten für eine Last aus der YAML
  - `ersparnis(zeitraum)`: Backtest-Ersparnis und Regret für einen Zeitraum
  - `negative_preise(zeitraum)`: Stunden mit negativem Preis, Anzahl und typische Uhrzeiten
- Kein freies SQL, Argumente werden per JSON-Schema validiert, die Zahl der Tool-Runden ist begrenzt. Der Provider steckt hinter einer schmalen Schnittstelle (Default: Anthropic, Modell per Env).

## Dashboard (Flask + Plotly)

1. **Plan für morgen:** Preiskurve (Prognose bzw. tatsächlich, sobald veröffentlicht) mit eingeplanten Lasten als Balken, dazu die erwarteten Kosten im Vergleich zur festen Schicht
2. **Ersparnis-Backtest:** Ersparnis und Regret pro Monat, kumuliert
3. **Prognosegüte:** MAE vs. Baseline, Top-k-Trefferquote
4. **Markt-Kontext:** Preis vs. EE-Anteil (Streudiagramm), negative Preise
5. **Fragen (optional):** Assistent

## Tests (pytest, ohne Netzwerk)

| Bereich | Testfälle |
|---|---|
| SMARD-Client | Parsing der Fixtures, `null`-Werte, Retry (gemockt mit `responses`) |
| Ingest/DB | Upsert idempotent, nur fehlende Chunks, Viertelstunden und Stunden nebeneinander |
| Aggregation | 4 Viertelstunden → Mittelwert (Preis) bzw. Summe (Energie), unvollständige Stunde wird markiert, DST-Tage (23/25 h), Übergang am 01.10.2025 |
| Anomalien | negativer Preis markiert, synthetischer Spike erkannt |
| Features | **Leakage-Test:** Features für D+1 nutzen nur Daten bis D 12:00, Residuallast korrekt berechnet |
| Forecast | synthetischer Zusammenhang wird gelernt, Top-k-Trefferquote an handgerechneten Beispielen |
| Lasten-YAML | gültige Datei wird geladen, ungültige (Dauer > Fenster, Leistung ≤ 0) mit klarer Fehlermeldung abgelehnt |
| Scheduler | contiguous == Brute-Force auf Zufallspreisen (Property-Test), divisible wählt die k günstigsten Stunden, Fenstergrenzen eingehalten, Leistungsgrenze nie überschritten, „infeasible“ korrekt erkannt |
| Backtest | Regret ≥ 0, bei konstanten Preisen Ersparnis = 0 und Regret = 0, Perfect-Foresight-Plan hat Regret 0 |
| Dashboard | alle Routen 200 mit Fixture-DB, Assistent deaktiviert ohne Key |
| Assistent | Fake-LLM: korrekter Tool-Dispatch, ungültige Argumente abgefangen, Rundenlimit |

Ziel ca. 80 % Coverage auf `src/emi`.

## CI (GitHub Actions)

- Trigger: Push und PR auf `main`
- `lint`: `ruff check`, `ruff format --check`
- `test`: Python 3.12, `pytest --cov`, Coverage als Artifact
- `docker`: `docker build` als Smoke-Test
- Kein Netzwerkzugriff auf SMARD und kein API-Key in der CI

## Dockerfile

- `python:3.12-slim`, Dependencies vor dem Quellcode installieren (Layer-Cache), Non-root-User
- Volume `/app/data` (SQLite), `config/` als Mount für die eigene `loads.yaml`
- `CMD` gunicorn mit `create_app()`, `HEALTHCHECK` auf `/health`
- CLI-Jobs über dasselbe Image: `docker compose run --rm app emi plan --day tomorrow`
- Secrets nur über `env_file`, `.env` steht in `.gitignore` und `.dockerignore`

## README-Gliederung (Englisch)

1. Titel, Pitch, Badges, Status „work in progress“
2. Key question (Lastverschiebung) und Kernergebnis („Shifting X kWh/day would have saved Y € over Z months, regret W € vs. perfect foresight“)
3. Features (Checkliste)
4. How it works: Prognose → Scheduler → Backtest (kleines Diagramm)
5. Quickstart (lokal und Docker), Beispiel `loads.yaml`
6. Configuration (Env-Variablen, Assistent optional)
7. Methodology: Daten und Aggregation 15 min → 1 h, Entscheidungszeitpunkt und Leakage, Metriken (MAE, Top-k, Ersparnis, Regret)
8. Results
9. **Limitations & next steps:** Ersparnis bezieht sich nur auf den Börsenpreis, Netzentgelte und Leistungspreis sind nicht modelliert; außerdem Heuristik für die Leistungsgrenze (MILP als Next Step), ganzstündiges Raster, keine Prozessabhängigkeiten
10. Data source und Attribution (SMARD, CC BY 4.0), Testing & CI, License

## Zeitplan (10 Arbeitstage)

| Tag | Inhalt |
|---|---|
| 1 | Projektgerüst: `pyproject.toml`, Ruff, Pytest, CI, `config.py` |
| 2–3 | **Machbarkeitscheck:** SMARD-Client (minimal), ein Jahr Daten, Aggregation 15 min → 1 h, Streudiagramm, Ridge vs. Baseline, Go/No-Go |
| 4 | Machbarkeitscode in Module überführen: DB-Schema, inkrementeller Ingest, Cleaning, Anomalien, Tests |
| 5 | Features und Preisprognose mit rollierendem Backtest, MAE und Top-k |
| 6–7 | **Lastverschiebung:** YAML-Lasten, Scheduler (contiguous, divisible, Leistungsgrenze), Backtest Ersparnis/Regret, Tests |
| 8 | Dashboard (Plan für morgen, Ersparnis, Prognosegüte, Markt-Kontext) |
| 9 | Docker, README mit Ergebnissen und Limitations |
| 10 | Puffer und LLM-Assistent (`plan_fuer_morgen`, `ersparnis`, `negative_preise`); fällt bei Zeitmangel als Erstes weg |
