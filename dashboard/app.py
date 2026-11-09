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


tab_findings, tab_explore, tab_compare = st.tabs(
    ["📌 Key findings", "🔎 Explore by year", "🇨🇭 vs 🇵🇹 Switzerland vs Portugal"]
)

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


# ------------------------------------------------- Switzerland vs Portugal ---
with tab_compare:
    if not (MARTS / "mart_country_sensitivity.parquet").exists():
        st.info("Comparison data not built yet. Run `python -m src.pipeline all`.")
        st.stop()

    csens = q("SELECT * FROM mart_country_sensitivity")
    ccool = q("SELECT * FROM mart_country_cooling")
    cbins = q("SELECT * FROM mart_country_temp_bins")
    cyear = q("SELECT * FROM mart_country_yearly")
    cwin = q("SELECT min(date_local) AS d0, max(date_local) AS d1, count(DISTINCT date_local) AS n "
             "FROM fct_country_daily WHERE in_common_window")

    st.caption(
        f"Same method for both countries: working days only, ERA5 temperature (Open-Meteo), "
        f"{int(cwin.n[0]):,} common days ({pd.to_datetime(cwin.d0[0]):%b %Y} – {pd.to_datetime(cwin.d1[0]):%b %Y}). "
        "Holiday periods (20 Dec – 6 Jan, August) are excluded from the weather models. "
        "CH = Swissgrid end-user consumption · PT = E-REDES mainland consumption (total and low voltage)."
    )

    def get(df, country, series, col, period_col="heating_season", period="All"):
        row = df[(df.country == country) & (df.series == series) & (df[period_col] == period)]
        return row[col].iloc[0] if not row.empty else float("nan")

    def fit(r2):
        if pd.isna(r2):
            return "n/a"
        return "strong" if r2 >= 0.6 else "moderate" if r2 >= 0.3 else "weak"

    BAND = "All, 7–15 °C"
    h = {k: get(csens, *k, "wh_pc_per_degc_colder") for k in [("CH", "Total"), ("PT", "Total"), ("PT", "Low voltage")]}
    hb = {k: get(csens, *k, "wh_pc_per_degc_colder", period=BAND) for k in h}
    r2b = {k: get(csens, *k, "r2", period=BAND) for k in h}
    pct = {k: get(csens, *k, "pct_per_degc_colder") for k in h}
    r2 = {k: get(csens, *k, "r2") for k in h}
    nd = {k: get(csens, *k, "n_days") for k in h}
    c = {k: get(ccool, *k, "wh_pc_per_degc_hotter", "period") for k in h}
    cr2 = {k: get(ccool, *k, "r2", "period") for k in h}

    last_year = cyear.groupby("year").country.nunique().loc[lambda x: x == 2].index.max()
    yr = cyear[cyear.year == last_year].set_index("country") if pd.notna(last_year) else None
    bins_tot = cbins[cbins.series == "Total"]
    valley = {k: int(g.loc[g.kwh_pc_mean.idxmin(), "temp_bin_c"]) for k, g in bins_tot.groupby("country")}

    # ---- side-by-side table (clearer than metric cards for a comparison)
    def fmt(v, f="{:,.0f}"):
        return "–" if pd.isna(v) else f.format(v)

    rows = []
    if yr is not None:
        rows.append(["Electricity per person per year (" + str(int(last_year)) + ")",
                     fmt(yr.loc["CH", "kwh_per_capita"]) + " kWh", fmt(yr.loc["PT", "kwh_per_capita"]) + " kWh",
                     fmt(yr.loc["PT", "low_voltage_kwh_per_capita"]) + " kWh"])
    rows += [
        ["Extra per person per day, per °C colder — same 7–15 °C range", fmt(hb[("CH", "Total")]) + " Wh",
         fmt(hb[("PT", "Total")]) + " Wh", fmt(hb[("PT", "Low voltage")]) + " Wh"],
        ["Extra per person per day, per °C colder — all winter days", fmt(h[("CH", "Total")]) + " Wh",
         fmt(h[("PT", "Total")]) + " Wh", fmt(h[("PT", "Low voltage")]) + " Wh"],
        ["… as % of daily demand", fmt(pct[("CH", "Total")], "{:.1f}") + " %",
         fmt(pct[("PT", "Total")], "{:.1f}") + " %", fmt(pct[("PT", "Low voltage")], "{:.1f}") + " %"],
        ["… model fit R² (days)", f"{fmt(r2[('CH', 'Total')], '{:.2f}')} ({fmt(nd[('CH', 'Total')])})",
         f"{fmt(r2[('PT', 'Total')], '{:.2f}')} ({fmt(nd[('PT', 'Total')])})",
         f"{fmt(r2[('PT', 'Low voltage')], '{:.2f}')} ({fmt(nd[('PT', 'Low voltage')])})"],
        ["Extra per person per day, per °C hotter (summer)", fmt(c[("CH", "Total")]) + " Wh",
         fmt(c[("PT", "Total")]) + " Wh", fmt(c[("PT", "Low voltage")]) + " Wh"],
        ["Temperature with the lowest demand", f"{valley.get('CH', '–')} °C", f"{valley.get('PT', '–')} °C", "–"],
    ]
    st.dataframe(pd.DataFrame(rows, columns=["", "🇨🇭 Switzerland", "🇵🇹 Portugal (total)",
                                             "🇵🇹 Portugal (low voltage)"]),
                 use_container_width=True, hide_index=True)

    # ---- what the data says (computed and hedged by model quality)
    hc, hp, hl = hb[("CH", "Total")], hb[("PT", "Total")], h[("PT", "Low voltage")]
    bullets = []
    if pd.notna(hc) and pd.notna(hp):
        ratio = hc / hp if hp > 0 else float("nan")
        bullets.append(
            f"❄️ **In the same 7–15 °C range, each 1 °C colder adds ≈ {hc:,.0f} Wh per person per day in Switzerland "
            f"vs ≈ {hp:,.0f} Wh in Portugal**"
            + (f" — ≈ {ratio:.1f}× more in Switzerland." if pd.notna(ratio) and ratio > 1 else ".")
        )
    if pd.notna(r2[("PT", "Total")]) and r2[("PT", "Total")] < 0.3:
        bullets.append(
            f"📉 The Portuguese fit is {fit(r2[('PT', 'Total')])} (R² {r2[('PT', 'Total')]:.2f} vs "
            f"{r2[('CH', 'Total')]:.2f} in CH) mainly because Portuguese winter days span a narrow range "
            "(≈ 7–15 °C), so day-to-day noise weighs more; the temperature curve below still shows a steady rise "
            "as it gets colder. Rooftop solar (sunny cold days lower grid demand) also blurs the signal."
        )
    if pd.notna(hl):
        hpt = h[("PT", "Total")]
        share = f" — about {100 * hl / hpt:.0f} % of Portugal's total heating response" if pd.notna(hpt) and hpt > 0 and hl <= hpt else ""
        bullets.append(
            f"🏠 **In Portugal the cold response comes almost entirely from low voltage** (mostly homes and small "
            f"businesses): ≈ {hl:,.0f} Wh per person per °C{share}, i.e. ≈ {pct[('PT', 'Low voltage')]:.1f} % of "
            "low-voltage demand per °C."
        )
    if pd.notna(c[("PT", "Total")]):
        bullets.append(
            f"☀️ **Summer works the other way round:** each 1 °C hotter adds ≈ {c[('PT', 'Total')]:,.0f} Wh/person/day "
            f"in Portugal vs ≈ {fmt(c[('CH', 'Total')])} in Switzerland (R² {fmt(cr2[('PT', 'Total')], '{:.2f}')} PT, "
            f"{fmt(cr2[('CH', 'Total')], '{:.2f}')} CH)."
        )
    if valley:
        bullets.append(
            f"🌡️ Working-day demand per person is lowest around **{valley.get('CH', '–')} °C in Switzerland** and "
            f"**{valley.get('PT', '–')} °C in Portugal**."
        )
    st.markdown("\n".join(f"- {b}" for b in bullets))

    st.info(
        "**How to read this.** These are *electricity* figures only. Much Swiss heating still runs on oil, gas "
        "or district heat, so the Swiss response mostly reflects heat pumps and electric heating. "
        "Electricity data cannot measure whether homes are warm enough: energy poverty is real in Portugal — "
        "Eurostat reports that 15.7 % of people could not keep their home adequately warm in 2024, vs 9.2 % in "
        "the EU — but it does not show up as a clearly weaker reaction to cold in this data."
    )

    # ---- heating/cooling curve
    st.subheader("Electricity per person vs daily temperature (working days)")
    cb = cbins.assign(label=cbins.country.map({"CH": "🇨🇭 Switzerland", "PT": "🇵🇹 Portugal"})
                      + cbins.series.map({"Total": "", "Low voltage": " – low voltage"}))
    curve = alt.Chart(cb).mark_line(point=True).encode(
        x=alt.X("temp_bin_c:Q", title="Daily mean temperature (°C)"),
        y=alt.Y("kwh_pc_mean:Q", title="kWh per person per day", scale=alt.Scale(zero=False)),
        color=alt.Color("label:N", title=None),
        strokeDash=alt.StrokeDash("series:N", legend=None),
        tooltip=["label", "temp_bin_c", alt.Tooltip("kwh_pc_mean:Q", format=".2f"), "n_days"],
    )
    st.altair_chart(curve, use_container_width=True)

    # ---- per season
    st.subheader("Heating response per heating season")
    seas = csens[csens.heating_season != "All"].assign(
        label=lambda d: d.country.map({"CH": "🇨🇭 CH", "PT": "🇵🇹 PT"})
        + d.series.map({"Total": "", "Low voltage": " low voltage"})
    )
    bars = alt.Chart(seas).mark_bar().encode(
        x=alt.X("heating_season:N", title="Heating season"),
        xOffset="label:N",
        y=alt.Y("wh_pc_per_degc_colder:Q", title="Extra Wh per person per day, per °C colder"),
        color=alt.Color("label:N", title=None),
        tooltip=["label", "heating_season", alt.Tooltip("wh_pc_per_degc_colder:Q", format=",.0f"),
                 alt.Tooltip("pct_per_degc_colder:Q", format=".2f"), alt.Tooltip("r2:Q", format=".2f"), "n_days"],
    )
    st.altair_chart(bars, use_container_width=True)

    with st.expander("Model details (all regressions)"):
        st.markdown("**Heating** (working days, Oct–Apr, < 15 °C, excl. 20 Dec – 6 Jan)")
        st.dataframe(csens.round(3), use_container_width=True, hide_index=True)
        st.markdown("**Cooling** (working days, Jun–Sep excl. August, ≥ 20 °C)")
        st.dataframe(ccool.round(3), use_container_width=True, hide_index=True)
        st.markdown("**Yearly figures** (full years in the common window)")
        st.dataframe(cyear.round(1), use_container_width=True, hide_index=True)

    st.caption("Sources: Swissgrid; E-REDES Open Data Portal (CC BY 4.0); ERA5 via Open-Meteo; "
               "population: OFS (CH), INE/DREM (PT mainland, approx.).")
