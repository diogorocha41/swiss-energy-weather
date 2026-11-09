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


def _data_version() -> str:
    """Changes whenever a mart file changes, so the cache never serves stale data."""
    return "|".join(f"{f.name}:{f.stat().st_mtime_ns}:{f.stat().st_size}" for f in sorted(MARTS.glob("*.parquet")))


@st.cache_data(ttl=3600)
def _query(sql: str, version: str):
    con = duckdb.connect()
    for f in MARTS.glob("*.parquet"):
        con.execute(f"CREATE VIEW {f.stem} AS SELECT * FROM read_parquet('{f.as_posix()}')")
    return con.execute(sql).df()


def q(sql: str):
    return _query(sql, _data_version())


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
if daily.empty:
    st.warning("The data marts are empty — the pipeline ran without Swissgrid data.")
    st.stop()
sens = q("SELECT * FROM mart_temp_sensitivity ORDER BY season_start_year")
years = sorted(daily["year"].unique().tolist())


tab_findings, tab_explore = st.tabs(["📌 Key findings", "🔎 Explore by year"])

# ------------------------------------------------------- key findings ---
with tab_findings:
    full = sens[sens["n_days"] >= 120]  # full heating seasons only
    if full.empty:
        st.info("Not enough full heating seasons yet.")
    else:
        slope = -full["slope_mwh_per_degc"]
        pct = 100 * slope / full["end_consumption_mean_mwh"]
        half = (len(full) + 1) // 2
        early, late = slope.iloc[:max(half, 1)].mean(), slope.iloc[max(half, 1):].mean()

        yearly = q("""
            SELECT year, sum(end_consumption_gwh) / 1000 AS twh, sum(hdd_20_12) AS hdd, sum(n_days) AS days
            FROM mart_monthly GROUP BY year ORDER BY year
        """)
        yfull = yearly[yearly["days"] >= 365]
        y0, y1 = yfull.iloc[0], yfull.iloc[-1]

        dt = daily.groupby("day_type")["end_consumption_mwh"].mean()
        ss = daily.groupby("season")["end_consumption_mwh"].mean()
        prof = q("""SELECT hour_local, end_consumption_mean_mw FROM mart_load_profile
                    WHERE season = 'Winter half-year' AND day_type = 'Working day'""")
        peak, low = prof.loc[prof.end_consumption_mean_mw.idxmax()], prof.loc[prof.end_consumption_mean_mw.idxmin()]
        rec = daily.loc[daily.end_consumption_mwh.idxmax()]

        st.caption(f"Computed live from {len(daily):,} complete days "
                   f"({daily.date_local.min():%b %Y} – {daily.date_local.max():%b %Y}).")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Extra demand per °C colder", f"{slope.mean() / 1000:.1f} GWh/day",
                  f"{pct.mean():.1f} % of a winter day", delta_color="off")
        k2.metric("Explained by temperature (R²)", f"{100 * full['r2'].mean():.0f} %",
                  f"{len(full)} heating seasons", delta_color="off")
        k3.metric(f"Consumption {int(y1.year)} vs {int(y0.year)}", f"{y1.twh:.1f} TWh",
                  f"{100 * (y1.twh / y0.twh - 1):+.1f} %", delta_color="inverse")
        k4.metric("Record day", f"{rec.end_consumption_mwh / 1000:.0f} GWh",
                  f"{rec.date_local:%d %b %Y}", delta_color="off")

        st.markdown(f"""
- 🌡️ **Each 1 °C colder adds ≈ {slope.mean() / 1000:.1f} GWh/day** on winter working days
  (≈ {pct.mean():.1f} % of daily demand); temperature explains ≈ {100 * full['r2'].mean():.0f} % of the variation.
- 📈 **The sensitivity is {'rising' if late > early else 'falling'}**: {early / 1000:.2f} GWh/°C in the first
  {max(half, 1)} seasons vs {late / 1000:.2f} GWh/°C in the last {len(full) - max(half, 1)}
  ({100 * (late / early - 1):+.0f} %) — consistent with the spread of electric heating (heat pumps).
- 📉 **{int(y1.year)} used {y1.twh:.1f} TWh vs {y0.twh:.1f} TWh in {int(y0.year)}
  ({100 * (y1.twh / y0.twh - 1):+.1f} %)**, with heating degree days of {y1.hdd:,.0f} vs {y0.hdd:,.0f}.
- 📅 **Calendar effects are large**: Saturdays use {100 * (1 - dt['Saturday'] / dt['Working day']):.1f} % less than
  working days, Sundays {100 * (1 - dt['Sunday'] / dt['Working day']):.1f} % and public holidays
  {100 * (1 - dt['Holiday'] / dt['Working day']):.1f} % less.
- ❄️ **Winter-half-year days use {100 * (ss['Winter half-year'] / ss['Summer half-year'] - 1):.0f} % more**
  electricity than summer ones; on a winter working day the {int(peak.hour_local):02d}:00 peak
  (≈ {peak.end_consumption_mean_mw / 1000:.1f} GW) is {100 * (peak.end_consumption_mean_mw / low.end_consumption_mean_mw - 1):.0f} %
  above the {int(low.hour_local):02d}:00 trough (≈ {low.end_consumption_mean_mw / 1000:.1f} GW).
""")

        st.subheader("Temperature sensitivity per heating season")
        chart_df = full.assign(gwh_per_degc=slope / 1000)
        bars = alt.Chart(chart_df).mark_bar().encode(
            x=alt.X("heating_season:N", title="Heating season"),
            y=alt.Y("gwh_per_degc:Q", title="Extra GWh/day per °C colder"),
            tooltip=["heating_season", alt.Tooltip("gwh_per_degc:Q", format=".2f"),
                     alt.Tooltip("r2:Q", format=".2f"), "n_days"],
        )
        st.altair_chart(bars, use_container_width=True)

# ------------------------------------------------------ explore by year ---
with tab_explore:
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
