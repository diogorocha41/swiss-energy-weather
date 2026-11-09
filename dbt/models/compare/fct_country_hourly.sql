-- Hourly consumption for both countries on a common basis:
-- CH = Swissgrid end-user consumption, PT = E-REDES total (mainland), same temperature source (ERA5).
WITH load AS (
    SELECT 'CH' AS country, hour_utc_end, end_consumption_mwh AS consumption_mwh,
           CAST(NULL AS DOUBLE) AS low_voltage_mwh, n_quarter_hours, FALSE AS is_grid_event
    FROM {{ ref('stg_grid_hourly') }}
    UNION ALL
    SELECT 'PT', hour_utc_end, consumption_mwh, low_voltage_mwh, n_quarter_hours, is_grid_event
    FROM {{ ref('stg_pt_load_hourly') }}
),
joined AS (
    SELECT
        l.*,
        w.temp_c,
        CASE l.country
            WHEN 'CH' THEN timezone('Europe/Zurich', (l.hour_utc_end - INTERVAL 1 HOUR)::TIMESTAMPTZ)
            ELSE           timezone('Europe/Lisbon', (l.hour_utc_end - INTERVAL 1 HOUR)::TIMESTAMPTZ)
        END AS hour_local_start
    FROM load l
    LEFT JOIN {{ ref('stg_era5_hourly') }} w
        ON w.country = l.country AND w.hour_utc = l.hour_utc_end - INTERVAL 1 HOUR
)
SELECT
    j.*,
    CAST(j.hour_local_start AS DATE)  AS date_local,
    CASE
        WHEN h.holiday_name IS NOT NULL      THEN 'Holiday'
        WHEN isodow(j.hour_local_start) = 7  THEN 'Sunday'
        WHEN isodow(j.hour_local_start) = 6  THEN 'Saturday'
        ELSE 'Working day'
    END                               AS day_type
FROM joined j
LEFT JOIN {{ source('raw', 'dim_holiday') }} h
    ON h.country = j.country AND h.holiday_date = CAST(j.hour_local_start AS DATE)
