-- Staging: hourly station data -> one weighted "national" value per hour.
-- Weights come from dim_station (config.py). A station with a missing value
-- is left out and the remaining weights are re-normalised.
WITH dedup AS (
    SELECT *
    FROM {{ source('raw', 'raw_meteo_hourly') }}
    QUALIFY row_number() OVER (PARTITION BY station, ts_utc_end ORDER BY loaded_at DESC) = 1
)
SELECT
    d.ts_utc_end AS hour_utc_end,
    sum(d.temp_c * s.weight)         / nullif(sum(s.weight) FILTER (WHERE d.temp_c IS NOT NULL), 0)         AS temp_c,
    sum(d.global_rad_wm2 * s.weight) / nullif(sum(s.weight) FILTER (WHERE d.global_rad_wm2 IS NOT NULL), 0) AS global_rad_wm2,
    sum(d.precip_mm * s.weight)      / nullif(sum(s.weight) FILTER (WHERE d.precip_mm IS NOT NULL), 0)      AS precip_mm,
    sum(d.sunshine_min * s.weight)   / nullif(sum(s.weight) FILTER (WHERE d.sunshine_min IS NOT NULL), 0)   AS sunshine_min,
    count(*) FILTER (WHERE d.temp_c IS NOT NULL)                                                            AS n_stations
FROM dedup d
JOIN {{ source('raw', 'dim_station') }} s USING (station)
GROUP BY 1
