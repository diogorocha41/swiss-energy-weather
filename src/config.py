"""Central configuration for the Swiss energy x weather pipeline."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_SWISSGRID_DIR = DATA_DIR / "raw" / "swissgrid"
RAW_METEO_DIR = DATA_DIR / "raw" / "meteoswiss"
MARTS_DIR = DATA_DIR / "marts"
DB_PATH = DATA_DIR / "energy.duckdb"
SQL_MODELS_DIR = ROOT / "sql" / "models"
SQL_TESTS_DIR = ROOT / "sql" / "tests"

# First year to keep (older data is ignored to keep the project light).
START_YEAR = 2019

# --- Swissgrid -------------------------------------------------------------
# Swissgrid "Energy Statistic Switzerland" XLSX files (one per year) are
# downloaded manually from:
# https://www.swissgrid.ch/en/home/customers/topics/energy-data-ch.html
# and saved into data/raw/swissgrid/.
SWISSGRID_SHEET_PREFIX = "zeitreihen"  # sheet "Zeitreihen0h15"
SWISSGRID_TIMEZONE = "Europe/Zurich"   # timestamps in the file are local time
# The XLSX files (~200 MB) stay out of git; this compact extract is committed instead.
SWISSGRID_EXTRACT = DATA_DIR / "processed" / "swissgrid_qh.parquet"

# series code -> text fragment found in the (bilingual DE/EN) column header
SWISSGRID_SERIES = {
    "end_consumption": "total energy consumed by end users",
    "total_consumption": "total energy consumption swiss control",
    "production": "total energy production swiss control",
    "net_outflow": "net outflow of the swiss transmission grid",
    "grid_feed_in": "grid feed-in swiss transmission grid",
}

# --- MeteoSwiss (Open Government Data, STAC API) ---------------------------
STAC_BASE_URL = "https://data.geo.admin.ch/api/stac/v1"
METEO_COLLECTION = "ch.meteoschweiz.ogd-smn"  # automatic weather stations

# SwissMetNet stations used to build a national "weighted temperature".
# Weights are a rough proxy for the population/load each station represents;
# tweak them and see how the model fit (R²) changes.
STATIONS = {
    "SMA": ("Zürich / Fluntern", 0.30),
    "BER": ("Bern / Zollikofen", 0.15),
    "BAS": ("Basel / Binningen", 0.12),
    "GVE": ("Genève / Cointrin", 0.15),
    "PUY": ("Pully (Lausanne)", 0.15),
    "LUG": ("Lugano", 0.13),
}

# MeteoSwiss parameter short name (hourly) -> column name in our database
METEO_PARAMS = {
    "tre200h0": "temp_c",            # air temperature 2 m, hourly mean
    "gre000h0": "global_rad_wm2",    # global radiation, hourly mean
    "rre150h0": "precip_mm",         # precipitation, hourly total
    "sre000h0": "sunshine_min",      # sunshine duration, hourly total
    "ure200h0": "rel_humidity_pct",  # relative humidity 2 m, hourly mean
}

HTTP_TIMEOUT_S = 120
USER_AGENT = "swiss-energy-weather/1.0 (portfolio project)"
