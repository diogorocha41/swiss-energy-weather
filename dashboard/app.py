"""Streamlit dashboard: how Swiss electricity demand reacts to the weather.

Reads only the exported Parquet marts (data/marts), so it can be deployed on
Streamlit Community Cloud straight from the GitHub repository.

    streamlit run dashboard/app.py
"""
from pathlib import Path

import altair as alt
import duckdb
import pandas as pd
import streamlit as st

MARTS = Path(__file__).resolve().parents[1] / "data" / "marts"

st.set_page_config(page_title="Swiss electricity x weather", layout="wide")


@st.cache_data(ttl=3600)
def q(sql: str):
    con = duckdb.connect()
    for f in MARTS.glob("*.parquet"):
        con.execute(f"CREATE VIEW {f.stem} AS SELECT * FROM read_parquet('{f.as_posix()}')")
    return con.execute(sql).df()


if not (MARTS / "fct_daily.parquet").exists():
    st.error("No data yet. Run `python -m src.pipeline all` first.")
    st.stop()

st.title("⚡ Swiss electricity demand × weather")
st.caption(
    "Swissgrid 15-min energy data + MeteoSwiss station data, modelled in DuckDB. "
    "Sources: Swissgrid, MeteoSwiss (Open Government Data)."
)

daily = q("SELECT * FROM fct_daily WHERE is_complete ORDER BY date_local")
daily["date_local"] = pd.to_datetime(daily["date_local"])
sens = q("SELECT * FROM mart_temp_sensitivity ORDER BY season_start_year")
years = sorted(daily["year"].unique().tolist())

# ---------------------------------------------------------------- KPIs ---
year = st.selectbox("Year", years[::-1], index=0)
cur = daily[daily["year"] == year]
last_day = cur["date_local"].max()
is_partial = len(cur) < 360

# Compare with the same period of the previous year (fair for partial years)
prev = daily[(daily["year"] == year - 1) & (daily["date_local"] <= last_day - pd.DateOffset(years=1))]
period = f"{year} (to {last_day:%d %b})" if is_partial else str(year)

cons = cur.end_consumption_mwh.sum() / 1e6
temp = cur.temp_mean_c.mean()
cons_delta = f"{100 * (cons / (prev.end_consumption_mwh.sum() / 1e6) - 1):+.1f}% vs {year - 1}" if len(prev) else None
temp_delta = f"{temp - prev.temp_mean_c.mean():+.1f} °C vs {year - 1}" if len(prev) else None

c1, c2, c3, c4 = st.columns(4)
c1.metric(f"End-user consumption {period}", f"{cons:,.1f} TWh", cons_delta, delta_color="off")
c2.metric(f"Mean temperature {period}", f"{temp:.1f} °C", temp_delta, delta_color="off")

# Heating season ending in the selected year (e.g. 2025 -> winter 2024/25)
season = sens[sens["season_start_year"] == year - 1]
if season.empty:
    c3.metric("Extra demand per °C colder", "n/a")
    c4.metric("Model fit (R²)", "n/a")
    st.caption(f"Not enough winter working days for heating season {year - 1}/{str(year)[-2:]}.")
else:
    s = season.iloc[0]
    c3.metric(f"Extra demand per °C colder (winter {s.heating_season})",
              f"{-s.slope_mwh_per_degc:,.0f} MWh/day")
    c4.metric(f"Model fit R² (winter {s.heating_season})", f"{s.r2:.2f}",
              f"{int(s.n_days)} working days", delta_color="off")

# --------------------------------------------------------- time series ---
st.subheader(f"Daily consumption and temperature — {year}")
d = cur
base = alt.Chart(d).encode(x=alt.X("date_local:T", title=None))
line_cons = base.mark_line(color="#1f77b4").encode(
    y=alt.Y("end_consumption_mwh:Q", title="End-user consumption (MWh/day)")
)
line_temp = base.mark_line(color="#d62728", opacity=0.6).encode(
    y=alt.Y("temp_mean_c:Q", title="Weighted mean temperature (°C)")
)
st.altair_chart(alt.layer(line_cons, line_temp).resolve_scale(y="independent"), use_container_width=True)

# ------------------------------------------------------------- scatter ---
left, right = st.columns(2)
with left:
    st.subheader("Consumption vs temperature")
    scatter = (
        alt.Chart(d)
        .mark_circle(size=25, opacity=0.6)
        .encode(
            x=alt.X("temp_mean_c:Q", title="Mean temperature (°C)"),
            y=alt.Y("end_consumption_mwh:Q", title="MWh/day", scale=alt.Scale(zero=False)),
            color=alt.Color("day_type:N", title="Day type"),
            tooltip=["date_local:T", "day_type", alt.Tooltip("temp_mean_c:Q", format=".1f"),
                     alt.Tooltip("end_consumption_mwh:Q", format=",.0f")],
        )
    )
    st.altair_chart(scatter, use_container_width=True)

with right:
    st.subheader("Sensitivity per heating season")
    if sens.empty:
        st.info("Not enough winter days yet.")
    else:
        sens["mwh_per_degc_colder"] = -sens["slope_mwh_per_degc"]
        bars = (
            alt.Chart(sens)
            .mark_bar()
            .encode(
                x=alt.X("heating_season:N", title="Heating season"),
                y=alt.Y("mwh_per_degc_colder:Q", title="Extra MWh/day per °C colder"),
                tooltip=["heating_season", alt.Tooltip("mwh_per_degc_colder:Q", format=",.0f"),
                         alt.Tooltip("r2:Q", format=".2f"), "n_days"],
            )
        )
        st.altair_chart(bars, use_container_width=True)

# -------------------------------------------------------- load profile ---
st.subheader("Typical daily load profile")
prof = q("SELECT * FROM mart_load_profile")
season = st.radio("Season", sorted(prof["season"].unique()), horizontal=True)
profile_chart = (
    alt.Chart(prof[prof["season"] == season])
    .mark_line(point=False)
    .encode(
        x=alt.X("hour_local:O", title="Hour (Swiss local time)"),
        y=alt.Y("end_consumption_mean_mw:Q", title="Average load (MW)", scale=alt.Scale(zero=False)),
        color=alt.Color("day_type:N", title="Day type"),
    )
)
st.altair_chart(profile_chart, use_container_width=True)

# ------------------------------------------------------------- monthly ---
st.subheader("Monthly overview")
monthly = q("SELECT * FROM mart_monthly ORDER BY month_start")
st.dataframe(
    monthly[["month_start", "end_consumption_gwh", "production_gwh", "balance_gwh",
             "temp_mean_c", "hdd_20_12", "yoy_change_pct"]].round(1),
    use_container_width=True,
    hide_index=True,
)
