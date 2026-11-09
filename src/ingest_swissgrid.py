"""Extract + load Swissgrid 15-minute energy data (Energy Statistic Switzerland XLSX).

Each yearly XLSX has a sheet "Zeitreihen0h15": first row = bilingual column
headers, second row = units (kWh), then one row per quarter-hour. The
timestamp marks the END of the 15-minute interval, in Swiss local time.
"""
import logging
import re

import pandas as pd

from src.config import (
    RAW_SWISSGRID_DIR,
    START_YEAR,
    SWISSGRID_SERIES,
    SWISSGRID_SHEET_PREFIX,
    SWISSGRID_TIMEZONE,
)

log = logging.getLogger(__name__)
SOURCE = "swissgrid"


def _norm(text) -> str:
    return re.sub(r"\s+", " ", str(text)).strip().lower()


def find_timeseries_sheet(sheet_names: list[str]) -> str:
    for name in sheet_names:
        if name.lower().startswith(SWISSGRID_SHEET_PREFIX):
            return name
    raise ValueError(f"No sheet starting with '{SWISSGRID_SHEET_PREFIX}' in {sheet_names}")


def map_columns(columns) -> dict[str, str]:
    """Map raw column headers to our series codes using text fragments."""
    mapping = {}
    for col in columns:
        header = _norm(col)
        for code, fragment in SWISSGRID_SERIES.items():
            if fragment in header and code not in mapping.values():
                mapping[col] = code
                break
    return mapping


def localize_to_utc(ts: pd.Series, tz: str = SWISSGRID_TIMEZONE) -> pd.Series:
    """Local wall-clock timestamps -> naive UTC. Handles DST transitions."""
    try:
        local = ts.dt.tz_localize(tz, ambiguous="infer", nonexistent="shift_forward")
    except Exception:  # ambiguity cannot be inferred -> drop those rows
        log.warning("DST ambiguity could not be inferred; ambiguous rows set to NaT")
        local = ts.dt.tz_localize(tz, ambiguous="NaT", nonexistent="shift_forward")
    return local.dt.tz_convert("UTC").dt.tz_localize(None)


def parse_swissgrid_frame(df: pd.DataFrame, source_file: str) -> pd.DataFrame:
    """Wide Swissgrid sheet -> long table (ts_utc_end, series, value_kwh, source_file)."""
    ts_col = df.columns[0]
    ts = pd.to_datetime(df[ts_col], dayfirst=True, errors="coerce", format="mixed")
    # Keep the file's row order: on the autumn DST night the hour 02:00-03:00
    # appears twice, and only the original order tells which one is CEST/CET.
    df = df.assign(_ts=ts).dropna(subset=["_ts"])

    mapping = map_columns(df.columns[1:])
    missing = set(SWISSGRID_SERIES) - set(mapping.values())
    if missing:
        log.warning("%s: series not found: %s", source_file, sorted(missing))
    if not mapping:
        raise ValueError(f"{source_file}: none of the expected series were found")

    out = df[["_ts", *mapping.keys()]].rename(columns=mapping)
    out["ts_utc_end"] = localize_to_utc(out["_ts"])
    out = out.drop(columns="_ts").dropna(subset=["ts_utc_end"])

    long = out.melt(id_vars="ts_utc_end", var_name="series", value_name="value_kwh")
    long["value_kwh"] = pd.to_numeric(long["value_kwh"], errors="coerce")
    long = long[long["ts_utc_end"].dt.year >= START_YEAR]
    long["source_file"] = source_file
    return long.reset_index(drop=True)


def read_swissgrid_file(path) -> pd.DataFrame:
    xls = pd.ExcelFile(path)
    sheet = find_timeseries_sheet(xls.sheet_names)
    raw = pd.read_excel(xls, sheet_name=sheet, header=0)
    return parse_swissgrid_frame(raw, path.name)


def run(con) -> None:
    from src.db import already_loaded, file_sha256, log_load

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS raw_swissgrid (
            ts_utc_end  TIMESTAMP,
            series      VARCHAR,
            value_kwh   DOUBLE,
            source_file VARCHAR,
            loaded_at   TIMESTAMP
        )
        """
    )
    files = sorted(RAW_SWISSGRID_DIR.glob("*.xls*"))
    if not files:
        log.warning("No Swissgrid files in %s — download them first (see README).", RAW_SWISSGRID_DIR)
        return

    for path in files:
        sha = file_sha256(path)
        if already_loaded(con, SOURCE, path, sha):
            log.info("swissgrid: %s unchanged, skipping", path.name)
            continue
        df = read_swissgrid_file(path)
        con.execute("DELETE FROM raw_swissgrid WHERE source_file = ?", [path.name])
        con.register("incoming", df)
        con.execute(
            """
            INSERT INTO raw_swissgrid
            SELECT ts_utc_end, series, value_kwh, source_file, current_timestamp
            FROM incoming
            """
        )
        con.unregister("incoming")
        log_load(con, SOURCE, path, sha, len(df))
        log.info("swissgrid: loaded %s (%d rows)", path.name, len(df))
