"""Build dimensions, run SQL models in order, run data tests, export marts."""
import logging
from datetime import date

import pandas as pd

from src.calendar_ch import holiday_frame
from src.config import MARTS_DIR, SQL_MODELS_DIR, SQL_TESTS_DIR, START_YEAR, STATIONS

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


def run_models(con) -> None:
    for sql_file in sorted(SQL_MODELS_DIR.glob("*.sql")):
        log.info("model: %s", sql_file.name)
        con.execute(sql_file.read_text(encoding="utf-8"))


def run_tests(con) -> None:
    """Each test is a query returning offending rows.
    Files named assert_*.sql fail the pipeline; warn_*.sql only log."""
    failures = []
    for sql_file in sorted(SQL_TESTS_DIR.glob("*.sql")):
        n = con.execute(
            f"SELECT count(*) FROM ({sql_file.read_text(encoding='utf-8').rstrip().rstrip(';')})"
        ).fetchone()[0]
        status = "OK" if n == 0 else ("FAIL" if sql_file.name.startswith("assert_") else "WARN")
        log.info("test %-40s %s (%d rows)", sql_file.stem, status, n)
        if status == "FAIL":
            failures.append(sql_file.stem)
    if failures:
        raise DataTestError(f"Data tests failed: {failures}")


def export_marts(con) -> None:
    MARTS_DIR.mkdir(parents=True, exist_ok=True)
    for table in EXPORT_TABLES:
        target = MARTS_DIR / f"{table}.parquet"
        con.execute(f"COPY (SELECT * FROM {table}) TO '{target.as_posix()}' (FORMAT parquet)")
        log.info("export: %s", target.name)


def run(con) -> None:
    build_dimensions(con)
    run_models(con)
    run_tests(con)
    export_marts(con)
