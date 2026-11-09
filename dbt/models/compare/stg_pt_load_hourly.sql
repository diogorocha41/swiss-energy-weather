-- Portugal (mainland): 15-minute E-REDES data -> hourly (UTC), MWh.
-- E-REDES timestamps mark the END of the interval: 00:15..01:00 -> hour ending 01:00.
-- Zero values (a few quarter-hours on spring DST nights) are recording gaps -> NULL.
-- Hours inside a known grid incident (seed grid_events) are flagged.
WITH qh AS (
    SELECT ts_utc_end, nullif(total_kwh, 0) AS total_kwh, nullif(bt_kwh, 0) AS bt_kwh
    FROM {{ source('raw', 'raw_eredes') }}
),
hourly AS (
    SELECT
        date_trunc('hour', ts_utc_end - INTERVAL 15 MINUTE) + INTERVAL 1 HOUR  AS hour_utc_end,
        sum(total_kwh) / 1000.0                                               AS consumption_mwh,
        sum(bt_kwh) / 1000.0                                                  AS low_voltage_mwh,
        count(total_kwh)                                                      AS n_quarter_hours
    FROM qh
    GROUP BY 1
)
SELECT
    h.*,
    EXISTS (
        SELECT 1 FROM {{ ref('grid_events') }} e
        WHERE e.country = 'PT'
          AND h.hour_utc_end > e.start_utc
          AND h.hour_utc_end - INTERVAL 1 HOUR < e.end_utc
    ) AS is_grid_event
FROM hourly h
