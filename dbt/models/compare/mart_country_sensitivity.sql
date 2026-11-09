-- Heating sensitivity per country and series: working days in Oct–Apr colder than 15 °C,
-- excluding the Christmas/New Year break. Slope in Wh per person per day for 1 °C colder.
-- One row per heating season, a pooled row ('All') over every season in the common window, and a
-- pooled row restricted to 7–15 °C ('All, 7–15 °C'): Portuguese winter days rarely drop below 7 °C,
-- so this shared temperature range is the fair, like-for-like comparison between the two countries.
WITH d AS (
    SELECT *, CASE WHEN month >= 10 THEN year ELSE year - 1 END AS season_start_year
    FROM {{ ref('int_country_daily_long') }}
    WHERE day_type = 'Working day'
      AND month IN (10, 11, 12, 1, 2, 3, 4)
      AND temp_mean_c < 15
      AND NOT is_holiday_period
),
stats AS (
    SELECT
        country, series,
        season_start_year::VARCHAR || '/' || right((season_start_year + 1)::VARCHAR, 2) AS heating_season,
        season_start_year,
        count(*) AS n_days,
        regr_slope(kwh_pc, temp_mean_c) AS slope, regr_r2(kwh_pc, temp_mean_c) AS r2,
        avg(kwh_pc) AS kwh_pc_mean, avg(temp_mean_c) AS temp_mean_c, min(temp_mean_c) AS temp_min_c
    FROM d GROUP BY ALL
    UNION ALL
    SELECT
        country, series, 'All' AS heating_season, NULL AS season_start_year,
        count(*), regr_slope(kwh_pc, temp_mean_c), regr_r2(kwh_pc, temp_mean_c),
        avg(kwh_pc), avg(temp_mean_c), min(temp_mean_c)
    FROM d GROUP BY ALL
    UNION ALL
    SELECT
        country, series, 'All, 7–15 °C' AS heating_season, NULL AS season_start_year,
        count(*), regr_slope(kwh_pc, temp_mean_c), regr_r2(kwh_pc, temp_mean_c),
        avg(kwh_pc), avg(temp_mean_c), min(temp_mean_c)
    FROM d WHERE temp_mean_c >= 7 GROUP BY ALL
)
SELECT
    country, series, heating_season, season_start_year, n_days,
    -1000.0 * slope               AS wh_pc_per_degc_colder,
    r2,
    kwh_pc_mean,
    -100.0 * slope / kwh_pc_mean  AS pct_per_degc_colder,
    temp_mean_c,
    temp_min_c
FROM stats
WHERE n_days >= 20
ORDER BY country, series, season_start_year NULLS LAST
