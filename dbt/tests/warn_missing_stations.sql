{{ config(severity='warn') }}
-- Hours where fewer than all configured stations reported temperature.
SELECT hour_utc_end, n_stations
FROM {{ ref('stg_weather_hourly') }}
WHERE n_stations < (SELECT count(*) FROM {{ source('raw', 'dim_station') }})
