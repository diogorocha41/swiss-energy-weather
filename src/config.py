"""Central configuration for the Swiss energy x weather pipeline."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_SWISSGRID_DIR = DATA_DIR / "raw" / "swissgrid"
RAW_METEO_DIR = DATA_DIR / "raw" / "meteoswiss"
MARTS_DIR = DATA_DIR / "marts"
DB_PATH = DATA_DIR / "energy.duckdb"
DBT_DIR = ROOT / "dbt"

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

# --- Country comparison: Switzerland vs Portugal ---------------------------
# Population used for per-capita figures (latest official estimates).
POPULATION = {
    # OFS, permanent resident population on 31.12.2025
    "CH": 9_127_100,
    # Mainland Portugal (E-REDES covers the mainland grid only):
    # INE total 31.12.2025 (11 424 031) minus Madeira (266 130, DREM)
    # minus Azores (~245 000, approximation).
    "PT": 10_913_000,
}

# Portugal: E-REDES open data, national consumption, 15-minute, kWh, UTC.
EREDES_EXPORT_URL = (
    "https://e-redes.opendatasoft.com/api/explore/v2.1/catalog/datasets/"
    "consumo-total-nacional/exports/csv"
)
RAW_EREDES_DIR = DATA_DIR / "raw" / "eredes"

# Same weather source for both countries (ERA5 reanalysis via Open-Meteo),
# so the comparison is not biased by different measurement methods.
OPENMETEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
OPENMETEO_START = "2019-01-01"
OPENMETEO_CITIES = {
    # country: {city: (lat, lon, weight)} — weights ≈ share of population/load
    "CH": {
        "Zurich": (47.377, 8.540, 0.30),
        "Bern": (46.948, 7.447, 0.15),
        "Basel": (47.560, 7.588, 0.12),
        "Geneva": (46.204, 6.143, 0.15),
        "Lausanne": (46.520, 6.633, 0.15),
        "Lugano": (46.004, 8.951, 0.13),
    },
    "PT": {
        "Lisboa": (38.722, -9.139, 0.40),
        "Porto": (41.150, -8.611, 0.30),
        "Braga": (41.545, -8.427, 0.10),
        "Coimbra": (40.211, -8.429, 0.10),
        "Faro": (37.019, -7.930, 0.10),
    },
}
COUNTRY_TIMEZONE = {"CH": "Europe/Zurich", "PT": "Europe/Lisbon"}
