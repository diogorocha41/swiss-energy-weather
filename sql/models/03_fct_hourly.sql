-- Fact table: one row per hour with energy, weather and calendar features.
-- Calendar features use Swiss local time of the START of the hour.
CREATE OR REPLACE TABLE fct_hourly AS
WITH base AS (
    SELECT
        g.hour_utc_end,
        timezone('Europe/Zurich', (g.hour_utc_end - INTERVAL 1 HOUR)::TIMESTAMPTZ) AS hour_local_start,
        g.end_consumption_mwh,
        g.total_consumption_mwh,
        g.production_mwh,
        g.n_quarter_hours,
        w.temp_c,
        w.global_rad_wm2,
        w.precip_mm,
        w.sunshine_min,
        w.n_stations
    FROM stg_grid_hourly g
    LEFT JOIN stg_weather_hourly w USING (hour_utc_end)
)
SELECT
    b.*,
    CAST(b.hour_local_start AS DATE)              AS date_local,
    hour(b.hour_local_start)                      AS hour_local,
    isodow(b.hour_local_start)                    AS iso_dow,
    h.holiday_name IS NOT NULL                    AS is_holiday,
    CASE
        WHEN h.holiday_name IS NOT NULL      THEN 'Holiday'
        WHEN isodow(b.hour_local_start) = 7  THEN 'Sunday'
        WHEN isodow(b.hour_local_start) = 6  THEN 'Saturday'
        ELSE 'Working day'
    END                                           AS day_type,
    CASE WHEN month(b.hour_local_start) IN (10, 11, 12, 1, 2, 3)
         THEN 'Winter half-year' ELSE 'Summer half-year' END AS season
FROM base b
LEFT JOIN dim_holiday h ON h.holiday_date = CAST(b.hour_local_start AS DATE);
