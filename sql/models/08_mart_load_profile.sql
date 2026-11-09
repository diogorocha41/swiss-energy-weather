-- Mart: typical load profile — average power (MW) by local hour, day type and season.
-- Energy in one hour (MWh) equals average power over that hour (MW).
CREATE OR REPLACE TABLE mart_load_profile AS
SELECT
    season,
    day_type,
    hour_local,
    avg(end_consumption_mwh)   AS end_consumption_mean_mw,
    avg(temp_c)                AS temp_mean_c,
    count(*)                   AS n_hours
FROM fct_hourly
WHERE n_quarter_hours = 4
GROUP BY ALL
ORDER BY season, day_type, hour_local;
