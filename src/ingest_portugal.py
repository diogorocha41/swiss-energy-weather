"""Extract + load Portuguese electricity consumption from the E-REDES open data portal.

Dataset "consumo-total-nacional": mainland Portugal, 15-minute energy per
voltage level (BT = low voltage, mostly households and small businesses;
MT, AT, MAT = medium/high/very-high voltage) and total, in kWh.
`datahora` is in UTC and marks the END of the 15-minute interval (verified with the
28 April 2025 Iberian blackout at 11:33 local = 10:33 UTC: the slot labelled 10:45
is the first partial one).
Licence: CC BY 4.0 — source: E-REDES Open Data Portal.

The full dataset is small (~135k rows), so it is downloaded in full and the
table is replaced on every run (simple and idempotent).
"""
import io
import logging

import pandas as pd
import requests

from src.config import EREDES_EXPORT_URL, HTTP_TIMEOUT_S, RAW_EREDES_DIR, USER_AGENT

log = logging.getLogger(__name__)
SOURCE = "eredes"
VALUE_COLUMNS = ["bt", "mt", "at", "mat", "total"]


def download_csv() -> bytes:
    params = {"select": "datahora," + ",".join(VALUE_COLUMNS), "delimiter": ";", "timezone": "UTC"}
    r = requests.get(EREDES_EXPORT_URL, params=params, timeout=HTTP_TIMEOUT_S * 3,
                     headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    return r.content


def parse_eredes_csv(content: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(content), sep=";")
    df.columns = [c.strip().lower() for c in df.columns]
    missing = {"datahora", *VALUE_COLUMNS} - set(df.columns)
    if missing:
        raise ValueError(f"E-REDES export is missing columns: {sorted(missing)}")
    out = pd.DataFrame(
        {"ts_utc_end": pd.to_datetime(df["datahora"], utc=True, errors="coerce").dt.tz_localize(None)}
    )
    for c in VALUE_COLUMNS:
        out[f"{c}_kwh"] = pd.to_numeric(df[c], errors="coerce")
    out = out.dropna(subset=["ts_utc_end"]).drop_duplicates("ts_utc_end", keep="last")
    return out.sort_values("ts_utc_end").reset_index(drop=True)


def run(con) -> None:
    from src.db import file_sha256, log_load

    RAW_EREDES_DIR.mkdir(parents=True, exist_ok=True)
    dest = RAW_EREDES_DIR / "consumo_total_nacional.csv"
    try:
        dest.write_bytes(download_csv())
    except requests.RequestException as e:
        if not dest.exists():
            raise
        log.error("eredes: download failed (%s) — using cached file", e)

    df = parse_eredes_csv(dest.read_bytes())
    con.register("incoming", df)
    con.execute("CREATE OR REPLACE TABLE raw_eredes AS SELECT *, current_timestamp AS loaded_at FROM incoming")
    con.unregister("incoming")
    log_load(con, SOURCE, dest, file_sha256(dest), len(df))
    log.info("eredes: loaded %d quarter-hours (%s → %s)", len(df),
             df["ts_utc_end"].min(), df["ts_utc_end"].max())
