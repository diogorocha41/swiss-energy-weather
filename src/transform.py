"""Transformation layer: build dimensions, run dbt (models + tests), export marts.

The SQL models and data tests live in the dbt project in ./dbt.
Run them on their own with:  cd dbt && dbt build --profiles-dir .
"""
import logging
import os
from datetime import date

import pandas as pd

from src.calendar_ch import holiday_frame
from src.config import DB_PATH, DBT_DIR, MARTS_DIR, START_YEAR, STATIONS
from src.db import connect

log = logging.getLogger(__name__)

EXPORT_TABLES = [
    "fct_daily",
    "mart_monthly",
    "mart_temp_sensitivity",
    "mart_temp_bins",
    "mart_load_profile",
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
        "SELECT CAST(holiday_date AS DATE) AS holiday_date, holiday_name FROM tmp_df"
    )
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
    MARTS_DIR.mkdir(parents=True, exist_ok=True)
    for table in EXPORT_TABLES:
        target = MARTS_DIR / f"{table}.parquet"
        con.execute(f"COPY (SELECT * FROM {table}) TO '{target.as_posix()}' (FORMAT parquet)")
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
