"""Compute headline findings from the exported marts and write docs/findings.md.

    python scripts/findings.py
"""
import numbers
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
MARTS = ROOT / "data" / "marts"
OUT = ROOT / "docs" / "findings.md"

con = duckdb.connect()
for f in MARTS.glob("*.parquet"):
    con.execute(f"CREATE VIEW {f.stem} AS SELECT * FROM read_parquet('{f.as_posix()}')")


def one(sql):
    return con.execute(sql).fetchone()


def _fmt(col, v):
    if not isinstance(v, numbers.Number):
        return str(v)
    if col in ("year", "days", "n_days") or float(v).is_integer():
        return f"{int(v)}" if col in ("year",) else f"{int(v):,}"
    return f"{v:,.2f}"


def table(sql):
    df = con.execute(sql).df()
    header = "| " + " | ".join(df.columns) + " |"
    sep = "|" + "---|" * len(df.columns)
    rows = ["| " + " | ".join(_fmt(c, v) for c, v in zip(df.columns, r)) + " |"
            for r in df.itertuples(index=False)]
    return "\n".join([header, sep, *rows])


lines = ["# Key findings (auto-generated)", ""]

first, last, n_days = one("SELECT min(date_local), max(date_local), count(*) FROM fct_daily WHERE is_complete")
lines += [f"Data: {n_days:,} complete days, {first} → {last}.", ""]

# 1. Temperature sensitivity per heating season
lines += ["## Temperature sensitivity (working days, Oct–Apr, < 15 °C)", ""]
lines += [table("""
    SELECT heating_season,
           round(-slope_mwh_per_degc)        AS extra_mwh_per_day_per_degc_colder,
           round(r2, 2)                      AS r2,
           round(100 * -slope_mwh_per_degc / end_consumption_mean_mwh, 2) AS pct_of_daily_demand,
           n_days
    FROM mart_temp_sensitivity ORDER BY season_start_year
"""), ""]
avg_slope, avg_r2, avg_pct = one("""
    SELECT avg(-slope_mwh_per_degc), avg(r2), avg(100 * -slope_mwh_per_degc / end_consumption_mean_mwh)
    FROM mart_temp_sensitivity
""")
lines += [f"**Average: each 1 °C colder adds ≈ {avg_slope:,.0f} MWh/day "
          f"(≈ {avg_pct:.1f} % of a winter working day), mean R² = {avg_r2:.2f}.**", ""]

# 2. Day type effect
wd, sat, sun, hol = one("""
    SELECT avg(end_consumption_mwh) FILTER (WHERE day_type = 'Working day'),
           avg(end_consumption_mwh) FILTER (WHERE day_type = 'Saturday'),
           avg(end_consumption_mwh) FILTER (WHERE day_type = 'Sunday'),
           avg(end_consumption_mwh) FILTER (WHERE day_type = 'Holiday')
    FROM fct_daily WHERE is_complete
""")
lines += ["## Day type", "",
          f"- Saturdays use {100 * (1 - sat / wd):.1f} % less electricity than working days.",
          f"- Sundays use {100 * (1 - sun / wd):.1f} % less; public holidays {100 * (1 - hol / wd):.1f} % less.", ""]

# 3. Seasonality
win, summ = one("""
    SELECT avg(end_consumption_mwh) FILTER (WHERE season = 'Winter half-year'),
           avg(end_consumption_mwh) FILTER (WHERE season = 'Summer half-year')
    FROM fct_daily WHERE is_complete
""")
lines += ["## Seasonality", "",
          f"- An average winter-half-year day uses {100 * (win / summ - 1):.1f} % more electricity than a summer one.", ""]

# 4. Peak hour
hr, mw = one("""
    SELECT hour_local, end_consumption_mean_mw FROM mart_load_profile
    WHERE season = 'Winter half-year' AND day_type = 'Working day'
    ORDER BY end_consumption_mean_mw DESC LIMIT 1
""")
lo_hr, lo_mw = one("""
    SELECT hour_local, end_consumption_mean_mw FROM mart_load_profile
    WHERE season = 'Winter half-year' AND day_type = 'Working day'
    ORDER BY end_consumption_mean_mw ASC LIMIT 1
""")
lines += ["## Daily profile (winter working day)", "",
          f"- Peak at {hr:02d}:00–{hr + 1:02d}:00 with ≈ {mw:,.0f} MW; minimum at {lo_hr:02d}:00 with ≈ {lo_mw:,.0f} MW "
          f"(peak is {100 * (mw / lo_mw - 1):.0f} % above the night trough).", ""]

# 5. Coldest day / extremes
d, t, c = one("SELECT date_local, temp_mean_c, end_consumption_mwh FROM fct_daily WHERE is_complete ORDER BY temp_mean_c LIMIT 1")
d2, c2 = one("SELECT date_local, end_consumption_mwh FROM fct_daily WHERE is_complete ORDER BY end_consumption_mwh DESC LIMIT 1")
lines += ["## Extremes", "",
          f"- Coldest day: {d} ({t:.1f} °C mean) — {c / 1000:,.0f} GWh consumed.",
          f"- Highest consumption: {d2} — {c2 / 1000:,.0f} GWh.", ""]

# 6. Yearly totals
lines += ["## Yearly end-user consumption", "", table("""
    SELECT year, round(sum(end_consumption_gwh) / 1000, 2) AS twh, round(avg(temp_mean_c), 1) AS temp_mean_c,
           round(sum(hdd_20_12)) AS hdd_20_12, sum(n_days) AS days
    FROM mart_monthly GROUP BY year ORDER BY year
"""), ""]

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
print(f"\n→ written to {OUT}")
