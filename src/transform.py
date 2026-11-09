"""Transformation layer: build dimensions, run dbt (models + tests), export marts.

The SQL models and data tests live in the dbt project in ./dbt.
Run them on their own with:  cd dbt && dbt build --profiles-dir .
"""
import logging
import os
from datetime import date

import pandas as pd

from src.calendar_ch import holiday_frame
from src.config import DB_PATH, DBT_DIR, MARTS_DIR, OPENMETEO_CITIES, POPULATION, START_YEAR, STATIONS
from src.db import connect

log = logging.getLogger(__name__)

EXPORT_TABLES = [
    "fct_daily",
    "mart_monthly",
    "mart_temp_sensitivity",
    "mart_temp_bins",
    "mart_load_profile",
    "fct_country_daily",
    "mart_country_sensitivity",
    "mart_country_temp_bins",
    "mart_country_cooling",
    "mart_country_yearly",
]


class DataTestError(RuntimeError):
    pass


def build_dimensions(con) -> None:
    stations = pd.DataFrame(
        [{"station": k, "station_name": v[0], "weight": v[1]} for k, v in STATIONS.items()]
    )
    holidays = holiday_frame(START_YEAR, date.today().year + 1)

    con.register("tmp_df", stations)
    con.execute("CREATE OR REPLACE TABLE dim_station AS SELECT * FROM tmp_df")
    con.unregister("tmp_df")

    con.register("tmp_df", holidays)
    con.execute(
        "CREATE OR REPLACE TABLE dim_holiday AS "
        "SELECT country, CAST(holiday_date AS DATE) AS holiday_date, holiday_name FROM tmp_df"
    )
    con.unregister("tmp_df")

    countries = pd.DataFrame([{"country": k, "population": v} for k, v in POPULATION.items()])
    cities = pd.DataFrame(
        [{"country": c, "city": city, "weight": w}
         for c, cs in OPENMETEO_CITIES.items() for city, (_, _, w) in cs.items()]
    )
    for name, df in {"dim_country": countries, "dim_city": cities}.items():
        con.register("tmp_df", df)
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM tmp_df")
        con.unregister("tmp_df")


def run_dbt(args: list[str]) -> None:
    """Run a dbt command in-process. dbt needs the database file for itself,
    so no other DuckDB connection may be open while this runs."""
    from dbt.cli.main import dbtRunner

    os.environ["DUCKDB_PATH"] = str(DB_PATH)
    result = dbtRunner().invoke(
        [*args, "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR)]
    )
    if not result.success:
        raise DataTestError(f"dbt {' '.join(args)} failed — see the dbt output above")


def export_marts(con) -> None:
    """Parquet for the dashboard; CSV copies of the small marts so results can be
    read anywhere (and are rendered as tables on GitHub)."""
    MARTS_DIR.mkdir(parents=True, exist_ok=True)
    for table in EXPORT_TABLES:
        target = MARTS_DIR / f"{table}.parquet"
        con.execute(f"COPY (SELECT * FROM {table}) TO '{target.as_posix()}' (FORMAT parquet)")
        if table.startswith("mart_"):
            csv = MARTS_DIR / "csv" / f"{table}.csv"
            csv.parent.mkdir(exist_ok=True)
            con.execute(f"COPY (SELECT * FROM {table}) TO '{csv.as_posix()}' (HEADER, DELIMITER ',')")
        log.info("export: %s", target.name)


def run() -> None:
    con = connect()
    try:
        build_dimensions(con)
    finally:
        con.close()

    run_dbt(["build"])  # models + schema tests + singular tests, in DAG order

    con = connect()
    try:
        export_marts(con)
    finally:
        con.close()
