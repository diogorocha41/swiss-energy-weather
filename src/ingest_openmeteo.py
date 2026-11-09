"""Extract + load hourly temperature for Swiss and Portuguese cities (ERA5 via Open-Meteo).

Used only for the country comparison, so both countries are measured with the
same method. (The Swiss-only analysis keeps using MeteoSwiss station data.)
Open-Meteo is free for non-commercial use and needs no API key.
Times are requested in GMT; the value is the instantaneous temperature at that hour.
"""
import logging
from datetime import date

import pandas as pd
import requests

from src.config import HTTP_TIMEOUT_S, OPENMETEO_ARCHIVE_URL, OPENMETEO_CITIES, OPENMETEO_START, USER_AGENT

log = logging.getLogger(__name__)


def fetch_city(session: requests.Session, lat: float, lon: float, start: str, end: str) -> pd.DataFrame:
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": start, "end_date": end,
        "hourly": "temperature_2m", "timezone": "GMT",
    }
    r = session.get(OPENMETEO_ARCHIVE_URL, params=params, timeout=HTTP_TIMEOUT_S * 2)
    r.raise_for_status()
    hourly = r.json()["hourly"]
    return pd.DataFrame(
        {"ts_utc": pd.to_datetime(hourly["time"]), "temp_c": pd.to_numeric(hourly["temperature_2m"])}
    )


def run(con) -> None:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    end = date.today().isoformat()

    frames = []
    for country, cities in OPENMETEO_CITIES.items():
        for city, (lat, lon, _) in cities.items():
            df = fetch_city(session, lat, lon, OPENMETEO_START, end)
            df.insert(0, "city", city)
            df.insert(0, "country", country)
            frames.append(df.dropna(subset=["temp_c"]))
            log.info("open-meteo: %s/%s %d hours", country, city, len(frames[-1]))

    all_df = pd.concat(frames, ignore_index=True)
    con.register("incoming", all_df)
    con.execute("CREATE OR REPLACE TABLE raw_openmeteo_hourly AS SELECT * FROM incoming")
    con.unregister("incoming")
