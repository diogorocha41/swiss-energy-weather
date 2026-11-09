"""Unit tests for the parsing logic, using small synthetic inputs."""
from datetime import date

import pandas as pd

from src.calendar_ch import easter_sunday, swiss_holidays
from src.ingest_meteoswiss import parse_meteo_csv, select_hourly_assets
from src.ingest_swissgrid import find_timeseries_sheet, localize_to_utc, map_columns, parse_swissgrid_frame


# ------------------------------------------------------------- swissgrid ---
def _swissgrid_frame():
    cols = [
        "Unnamed: 0",
        "Summe endverbrauchte Energie Regelblock Schweiz\nTotal energy consumed by end users in the Swiss controlblock",
        "Summe produzierte Energie Regelblock Schweiz\nTotal energy production Swiss controlblock",
        "Summe verbrauchte Energie Regelblock Schweiz\nTotal energy consumption Swiss controlblock",
        "Something else",
    ]
    rows = [["Zeitstempel", "kWh", "kWh", "kWh", "kWh"]]
    ts = pd.date_range("2024-01-01 00:15", periods=8, freq="15min")
    for i, t in enumerate(ts):
        rows.append([t.strftime("%d.%m.%Y %H:%M"), 1_500_000 + i, 1_200_000, 1_800_000, 1])
    return pd.DataFrame(rows, columns=cols)


def test_find_sheet():
    assert find_timeseries_sheet(["Übersicht", "Zeitreihen0h15"]) == "Zeitreihen0h15"


def test_map_columns_distinguishes_consumption_series():
    mapping = map_columns(_swissgrid_frame().columns[1:])
    assert sorted(mapping.values()) == ["end_consumption", "production", "total_consumption"]


def test_parse_swissgrid_frame_to_utc_long():
    long = parse_swissgrid_frame(_swissgrid_frame(), "test.xlsx")
    assert len(long) == 8 * 3                    # 8 quarter-hours x 3 mapped series
    # 01.01.2024 00:15 local (CET, UTC+1) -> 2023-12-31 23:15 UTC
    assert long["ts_utc_end"].min() == pd.Timestamp("2023-12-31 23:15")
    assert long["value_kwh"].notna().all()


def test_dst_spring_and_autumn():
    spring = pd.Series(pd.to_datetime(["2024-03-31 01:45", "2024-03-31 03:00", "2024-03-31 03:15"]))
    utc = localize_to_utc(spring)
    assert utc.iloc[0] == pd.Timestamp("2024-03-31 00:45")   # CET
    assert utc.iloc[2] == pd.Timestamp("2024-03-31 01:15")   # CEST
    # autumn: 02:15..02:45 occur twice; 'infer' resolves them in order
    autumn = pd.Series(pd.to_datetime([
        "2024-10-27 01:45", "2024-10-27 02:00", "2024-10-27 02:15", "2024-10-27 02:30",
        "2024-10-27 02:45", "2024-10-27 02:00", "2024-10-27 02:15", "2024-10-27 02:30",
        "2024-10-27 02:45", "2024-10-27 03:00",
    ]))
    utc = localize_to_utc(autumn)
    assert utc.is_unique and utc.is_monotonic_increasing


def test_parse_frame_keeps_dst_duplicates():
    """Autumn DST night: repeated local labels must all survive as distinct UTC times."""
    cols = _swissgrid_frame().columns
    labels = ["27.10.2024 01:45", "27.10.2024 02:00", "27.10.2024 02:15", "27.10.2024 02:30",
              "27.10.2024 02:45", "27.10.2024 02:00", "27.10.2024 02:15", "27.10.2024 02:30",
              "27.10.2024 02:45", "27.10.2024 03:00"]
    rows = [["Zeitstempel", "kWh", "kWh", "kWh", "kWh"]] + [[t, 1, 1, 1, 1] for t in labels]
    long = parse_swissgrid_frame(pd.DataFrame(rows, columns=cols), "dst.xlsx")
    ts = long[long["series"] == "end_consumption"]["ts_utc_end"]
    assert len(ts) == 10 and ts.is_unique


# ------------------------------------------------------------ meteoswiss ---
def test_select_hourly_assets_filters_granularity_and_years():
    assets = {
        "ogd-smn_sma_h_historical_2000-2009.csv": "u1",
        "ogd-smn_sma_h_historical_2010-2019.csv": "u2",
        "ogd-smn_sma_h_historical_2020-2029.csv": "u3",
        "ogd-smn_sma_h_recent.csv": "u4",
        "ogd-smn_sma_h_now.csv": "u5",
        "ogd-smn_sma_d_recent.csv": "u6",
        "ogd-smn_sma_t_recent.csv": "u7",
    }
    sel = select_hourly_assets(assets, start_year=2019)
    assert set(sel) == {
        "ogd-smn_sma_h_historical_2010-2019.csv",
        "ogd-smn_sma_h_historical_2020-2029.csv",
        "ogd-smn_sma_h_recent.csv",
    }


def test_parse_meteo_csv(tmp_path):
    content = (
        "station_abbr;reference_timestamp;tre200h0;gre000h0;rre150h0;sre000h0\n"
        "SMA;31.12.2018 23:00;1.0;0;0.0;0\n"
        "SMA;01.01.2024 01:00;-2.5;0;0.1;0\n"
        "SMA;01.01.2024 02:00;;0;0.0;0\n"
    )
    f = tmp_path / "ogd-smn_sma_h_recent.csv"
    f.write_bytes(content.encode("cp1252"))
    df = parse_meteo_csv(f, "sma")
    assert len(df) == 2                                  # 2018 row dropped (START_YEAR)
    assert df["station"].unique().tolist() == ["SMA"]
    assert df["temp_c"].iloc[0] == -2.5
    assert pd.isna(df["temp_c"].iloc[1])
    assert df["rel_humidity_pct"].isna().all()           # parameter absent -> NaN


# -------------------------------------------------------------- calendar ---
def test_easter_known_dates():
    assert easter_sunday(2024) == date(2024, 3, 31)
    assert easter_sunday(2025) == date(2025, 4, 20)
    assert easter_sunday(2026) == date(2026, 4, 5)


def test_holidays_contain_national_day():
    assert (date(2026, 8, 1), "Swiss National Day") in swiss_holidays(2026)
