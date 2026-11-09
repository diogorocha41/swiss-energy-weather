"""Extract + load hourly MeteoSwiss station data through the STAC API.

For each station, the STAC item lists its CSV assets. We keep the hourly
("_h_") files: "historical" (split by decade, updated yearly) and "recent"
(current year up to yesterday). Downloads use ETags so unchanged files are
not fetched again.

CSV format (MeteoSwiss docs): separator ';', decimal '.', Windows-1252,
timestamps 'dd.mm.yyyy HH:MM' in UTC, marking the END of the interval for
hourly data.
"""
import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from src.config import (
    HTTP_TIMEOUT_S,
    METEO_COLLECTION,
    METEO_PARAMS,
    RAW_METEO_DIR,
    STAC_BASE_URL,
    START_YEAR,
    STATIONS,
    USER_AGENT,
)

log = logging.getLogger(__name__)
SOURCE = "meteoswiss"


# ---------------------------------------------------------------- extract ---
def list_station_assets(session: requests.Session, station: str) -> dict[str, str]:
    url = f"{STAC_BASE_URL}/collections/{METEO_COLLECTION}/items/{station.lower()}"
    r = session.get(url, timeout=HTTP_TIMEOUT_S)
    r.raise_for_status()
    return {name: a["href"] for name, a in r.json().get("assets", {}).items()}


def select_hourly_assets(assets: dict[str, str], start_year: int = START_YEAR) -> dict[str, str]:
    """Keep hourly historical files that overlap start_year.., plus the recent file."""
    selected = {}
    for name, href in assets.items():
        n = name.lower()
        if not n.endswith(".csv") or "_h_" not in n:
            continue
        if "recent" in n:
            selected[name] = href
        elif "historical" in n:
            m = re.search(r"(\d{4})-(\d{4})", n)
            if m and int(m.group(2)) < start_year:
                continue
            selected[name] = href
    return selected


def download(session: requests.Session, href: str, dest: Path) -> bool:
    """Download href to dest using ETag caching. Returns True if file changed."""
    etag_file = dest.with_suffix(dest.suffix + ".etag")
    headers = {}
    if dest.exists() and etag_file.exists():
        headers["If-None-Match"] = etag_file.read_text().strip()
    r = session.get(href, headers=headers, timeout=HTTP_TIMEOUT_S)
    if r.status_code == 304:
        return False
    r.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)
    if r.headers.get("ETag"):
        etag_file.write_text(r.headers["ETag"])
    return True


# -------------------------------------------------------------- transform ---
def _timestamp_column(columns) -> str:
    for c in columns:
        lc = c.lower()
        if "timestamp" in lc or lc == "referencets":
            return c
    raise ValueError(f"No timestamp column found in {list(columns)}")


def parse_meteo_csv(path: Path, station: str) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";", encoding="cp1252", dtype=str)
    ts_col = _timestamp_column(df.columns)
    out = pd.DataFrame(
        {
            "station": station.upper(),
            "ts_utc_end": pd.to_datetime(df[ts_col], format="%d.%m.%Y %H:%M", errors="coerce"),
        }
    )
    for code, name in METEO_PARAMS.items():
        out[name] = pd.to_numeric(df[code], errors="coerce") if code in df.columns else np.nan
    out = out.dropna(subset=["ts_utc_end"])
    out = out[out["ts_utc_end"].dt.year >= START_YEAR]
    out["source_file"] = path.name
    return out.reset_index(drop=True)


# ------------------------------------------------------------------- load ---
def run(con) -> None:
    from src.db import already_loaded, file_sha256, log_load

    cols = ", ".join(f"{c} DOUBLE" for c in METEO_PARAMS.values())
    con.execute(
        f"""
        CREATE TABLE IF NOT EXISTS raw_meteo_hourly (
            station VARCHAR, ts_utc_end TIMESTAMP, {cols},
            source_file VARCHAR, loaded_at TIMESTAMP
        )
        """
    )
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    for station in STATIONS:
        try:
            assets = select_hourly_assets(list_station_assets(session, station))
        except requests.HTTPError as e:
            log.error("meteo: cannot list assets for %s: %s", station, e)
            continue
        if not assets:
            log.warning("meteo: no hourly assets for %s", station)
            continue

        for name, href in sorted(assets.items()):
            dest = RAW_METEO_DIR / name
            download(session, href, dest)
            sha = file_sha256(dest)
            if already_loaded(con, SOURCE, dest, sha):
                log.info("meteo: %s unchanged, skipping", name)
                continue
            df = parse_meteo_csv(dest, station)
            con.execute("DELETE FROM raw_meteo_hourly WHERE source_file = ?", [name])
            con.register("incoming", df)
            con.execute(
                f"""
                INSERT INTO raw_meteo_hourly
                SELECT station, ts_utc_end, {", ".join(METEO_PARAMS.values())},
                       source_file, current_timestamp
                FROM incoming
                """
            )
            con.unregister("incoming")
            log_load(con, SOURCE, dest, sha, len(df))
            log.info("meteo: loaded %s (%d rows)", name, len(df))
