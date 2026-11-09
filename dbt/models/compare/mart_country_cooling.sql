-- Cooling sensitivity: working days in Jun–Sep (excluding August holidays) warmer than 20 °C.
-- Slope in Wh per person per day for 1 °C hotter. One row per year plus a pooled row ('All').
WITH d AS (
    SELECT *
    FROM {{ ref('int_country_daily_long') }}
    WHERE day_type = 'Working day' AND month BETWEEN 6 AND 9 AND temp_mean_c >= 20
      AND NOT is_holiday_period
),
stats AS (
    SELECT country, series, year::VARCHAR AS period, count(*) AS n_days,
           regr_slope(kwh_pc, temp_mean_c) AS slope, regr_r2(kwh_pc, temp_mean_c) AS r2,
           avg(kwh_pc) AS kwh_pc_mean, avg(temp_mean_c) AS temp_mean_c, max(temp_mean_c) AS temp_max_c
    FROM d GROUP BY ALL
    UNION ALL
    SELECT country, series, 'All', count(*), regr_slope(kwh_pc, temp_mean_c), regr_r2(kwh_pc, temp_mean_c),
           avg(kwh_pc), avg(temp_mean_c), max(temp_mean_c)
    FROM d GROUP BY ALL
)
SELECT country, series, period, n_days,
       1000.0 * slope AS wh_pc_per_degc_hotter, r2, kwh_pc_mean, temp_mean_c, temp_max_c
FROM stats
WHERE n_days >= 10
ORDER BY country, series, period
