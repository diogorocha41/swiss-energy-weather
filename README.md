# ⚡ Swiss Electricity Demand × Weather

An end-to-end data engineering project that answers a simple question with public Swiss data:

> **How much does Swiss electricity demand rise when it gets colder?**

It ingests 15-minute grid data from **Swissgrid** and hourly station data from **MeteoSwiss**, models them with **dbt** on **DuckDB** (staging → core → marts) with schema and data-quality tests, refreshes daily with **GitHub Actions**, and serves a **Streamlit** dashboard.

## Architecture

```mermaid
flowchart LR
    A[Swissgrid XLSX<br/>15-min energy data] -->|ingest_swissgrid.py| R[(DuckDB<br/>raw_*)]
    B[MeteoSwiss STAC API<br/>hourly station CSV] -->|ingest_meteoswiss.py<br/>ETag caching| R
    subgraph dbt [dbt build]
      S[staging<br/>stg_grid_hourly<br/>stg_weather_hourly] --> F[core<br/>fct_hourly · fct_daily]
      F --> M[marts<br/>monthly · temp sensitivity<br/>temp bins · load profile]
      T[schema + data tests]
    end
    R --> S
    M -->|Parquet export| P[data/marts/*.parquet]
    P --> D[Streamlit dashboard]
    G[GitHub Actions<br/>daily cron] -.-> R
```

## Key findings (2019 – Sep 2026)

![Dashboard](docs/dashboard.png)

* **Each 1 °C colder adds ≈ 3.3 GWh/day of demand** on winter working days — about **1.9 %** of daily consumption. Temperature alone explains **≈ 76 %** of the day-to-day variation (mean R² over the 7 full heating seasons 2019/20–2025/26, range 0.63–0.83).
* **The sensitivity is rising**: ≈ 3.15 GWh/°C on average in 2019/20–2022/23 vs ≈ 3.48 GWh/°C in 2023/24–2025/26 (+10 %), with the highest value in 2025/26 (3.7 GWh/°C) — consistent with the spread of electric heating (heat pumps).
* **Demand is lower than before the 2022 energy crisis**: 2025 used **53.5 TWh vs 56.0 TWh in 2019 (−4.4 %)** with almost identical heating degree days (2,801 vs 2,768).
* **Calendar effects are large**: Saturdays use 12.8 % less electricity than working days, Sundays 18.3 % and public holidays 17.4 % less.
* **Winter-half-year days use 23 % more** electricity than summer ones; on a winter working day the 08:00–09:00 peak (≈ 8.2 GW) is 40 % above the 04:00 trough (≈ 5.8 GW).
* **Record day: 6 January 2026 with 208 GWh** of end-user consumption.

Full tables: [`docs/findings.md`](docs/findings.md), regenerated with `python scripts/findings.py`.


## What it shows

* **Temperature sensitivity** per heating season: extra MWh/day of demand for each °C colder (linear fit on working days < 15 °C).
* **Consumption vs temperature** scatter by day type (working day, Saturday, Sunday, public holiday).
* **Typical load profiles** (MW by hour) for winter vs summer half-year.
* **Monthly balance** of production vs consumption, heating degree days (SIA 381/3, 20/12) and year-over-year change.

## Data engineering highlights

| Topic | Implementation |
|---|---|
| Incremental, idempotent loads | SHA-256 file hashes in `ingest_log`; reloading a file replaces its rows; staging deduplicates on the latest load |
| Efficient downloads | HTTP `If-None-Match` / ETag caching against the STAC API |
| Time zones & DST | Swissgrid local timestamps converted to UTC with DST inference; all joins in UTC, calendar features in Europe/Zurich |
| Interval semantics | 15-min "interval end" timestamps rolled up to hourly buckets correctly |
| Transformations | **dbt-duckdb** project in `dbt/`: sources, `ref()`-based DAG, documented models |
| Data quality | dbt schema tests (unique, not_null, accepted_values) + singular tests; `warn_*` tests only warn |
| Feature engineering | Swiss public holidays (computed Easter), day type, season, heating degree days |
| Orchestration | GitHub Actions daily cron + manual trigger; marts committed as Parquet |
| Unit tests | `pytest` on parsers, DST handling, asset selection, holiday calendar |

## Quick start

```bash
git clone <this repo> && cd swiss-energy-weather
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 1. Download Swissgrid "Energy Statistic Switzerland" XLSX files (2019 → current year) from
#    https://www.swissgrid.ch/en/home/customers/topics/energy-data-ch.html
#    and save them in data/raw/swissgrid/

# 2. Run tests and the pipeline
pytest -q
python -m src.pipeline all

# 3. Open the dashboard
streamlit run dashboard/app.py
```

Individual steps: `python -m src.pipeline swissgrid | meteo | transform`.

Work on the dbt models directly, and browse the lineage graph:

```bash
cd dbt
dbt build --profiles-dir .
dbt docs generate --profiles-dir . && dbt docs serve --profiles-dir .
```

Regenerate the findings below with `python scripts/findings.py` (writes `docs/findings.md`).

## Data model

| Table | Grain | Description |
|---|---|---|
| `raw_swissgrid` | quarter-hour × series | Long format, UTC, kWh |
| `raw_meteo_hourly` | station × hour | Temperature, radiation, precipitation, sunshine, humidity |
| `stg_grid_hourly` (dbt) | hour (UTC) | End-user consumption, total consumption, production (MWh) |
| `stg_weather_hourly` | hour (UTC) | Weighted national weather from 6 stations |
| `fct_hourly` | hour | Energy + weather + calendar features |
| `fct_daily` | local day | Daily totals, temperature stats, HDD, completeness flag |
| `mart_monthly` | month | Totals, balance, YoY change |
| `mart_temp_sensitivity` | heating season | Regression slope, intercept, R² |
| `mart_temp_bins` | 1 °C bin × day type | Mean and P10/P90 daily consumption |
| `mart_load_profile` | season × day type × hour | Average load (MW) |

## Assumptions & limitations

* Swissgrid Excel files (~200 MB) are not committed; a compact Parquet extract (`data/processed/swissgrid_qh.parquet`) is.
* Swissgrid timestamps are treated as Swiss local time marking the **end** of each 15-minute interval. The `warn_incomplete_days` test reports days that do not have 92/96/100 quarter-hours.
* MeteoSwiss timestamps are UTC (interval end for hourly data), per the official documentation.
* The national temperature is a weighted average of 6 lowland stations (Zürich, Bern, Basel, Genève, Pully, Lugano). Weights in `src/config.py` are approximate.
* Swissgrid data for recent months is provisional and may be revised.

## Roadmap

- [ ] Add ElCom electricity tariffs per municipality (LINDAS SPARQL endpoint)
- [ ] Add BFE register of electricity production plants (solar growth by canton)
- [ ] Day-ahead demand forecast model with weather features
- [x] Migrate SQL models to dbt-duckdb

## Data sources & licences

* **Swissgrid** — Energy Statistic Switzerland (15-minute aggregates). Source: Swissgrid AG.
* **MeteoSwiss** — Automatic weather stations (SwissMetNet), Open Government Data. Source: MeteoSwiss.

---
Author: Diogo Rocha · Electrical engineer moving into data engineering
