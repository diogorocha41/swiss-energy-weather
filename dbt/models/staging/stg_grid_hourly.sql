-- Staging: Swissgrid 15-minute data -> deduplicated -> hourly (UTC), in MWh.
-- A quarter-hour ending at 00:15, 00:30, 00:45 or 01:00 belongs to the hour ending 01:00.
WITH dedup AS (
    SELECT ts_utc_end, series, value_kwh
    FROM {{ source('raw', 'raw_swissgrid') }}
    WHERE value_kwh IS NOT NULL
    QUALIFY row_number() OVER (PARTITION BY ts_utc_end, series ORDER BY loaded_at DESC) = 1
)
SELECT
    date_trunc('hour', ts_utc_end - INTERVAL 15 MINUTE) + INTERVAL 1 HOUR      AS hour_utc_end,
    sum(value_kwh) FILTER (WHERE series = 'end_consumption')   / 1000.0       AS end_consumption_mwh,
    sum(value_kwh) FILTER (WHERE series = 'total_consumption') / 1000.0       AS total_consumption_mwh,
    sum(value_kwh) FILTER (WHERE series = 'production')        / 1000.0       AS production_mwh,
    count(DISTINCT ts_utc_end) FILTER (WHERE series = 'end_consumption')      AS n_quarter_hours
FROM dedup
GROUP BY 1
