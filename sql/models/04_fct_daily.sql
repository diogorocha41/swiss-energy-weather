-- Fact table: one row per local day.
-- hdd_20_12 = heating degree days per Swiss standard SIA 381/3 (20 °C indoor,
-- heating limit 12 °C): 20 - Tmean on days with Tmean < 12 °C, else 0.
CREATE OR REPLACE TABLE fct_daily AS
SELECT
    date_local,
    any_value(day_type)                       AS day_type,
    any_value(season)                         AS season,
    year(date_local)                          AS year,
    month(date_local)                         AS month,
    sum(end_consumption_mwh)                  AS end_consumption_mwh,
    sum(total_consumption_mwh)                AS total_consumption_mwh,
    sum(production_mwh)                       AS production_mwh,
    avg(temp_c)                               AS temp_mean_c,
    min(temp_c)                               AS temp_min_c,
    max(temp_c)                               AS temp_max_c,
    avg(global_rad_wm2)                       AS global_rad_mean_wm2,
    sum(precip_mm)                            AS precip_mm,
    sum(sunshine_min) / 60.0                  AS sunshine_h,
    CASE WHEN avg(temp_c) < 12 THEN 20 - avg(temp_c) ELSE 0 END AS hdd_20_12,
    sum(n_quarter_hours)                      AS n_quarter_hours,
    count(temp_c)                             AS n_weather_hours,
    -- DST days have 92 or 100 quarter-hours, normal days 96
    sum(n_quarter_hours) >= 92 AND count(temp_c) >= 20 AS is_complete
FROM fct_hourly
GROUP BY date_local;
