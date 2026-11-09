{{ config(materialized='view') }}
-- Long format: one row per country, series and day, restricted to the common window.
-- PT also gets a "Low voltage" series (mostly households and small businesses).
-- is_holiday_period marks the Christmas/New Year break (20 Dec – 6 Jan) and August:
-- businesses and industry slow down then, which coincides with the coldest/hottest days
-- and would otherwise be mistaken for a (negative) weather effect.
WITH long AS (
    SELECT country, 'Total' AS series, date_local, day_type, year, month, temp_mean_c,
           kwh_per_capita AS kwh_pc
    FROM {{ ref('fct_country_daily') }}
    WHERE in_common_window
    UNION ALL
    SELECT country, 'Low voltage' AS series, date_local, day_type, year, month, temp_mean_c,
           low_voltage_kwh_per_capita AS kwh_pc
    FROM {{ ref('fct_country_daily') }}
    WHERE in_common_window AND low_voltage_kwh_per_capita IS NOT NULL
)
SELECT
    *,
    (month = 12 AND day(date_local) >= 20) OR (month = 1 AND day(date_local) <= 6) OR month = 8
        AS is_holiday_period
FROM long
