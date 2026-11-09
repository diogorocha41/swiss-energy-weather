-- Mart: temperature sensitivity of daily consumption, per heating season.
-- Linear fit on complete working days colder than 15 °C:
--   end_consumption_mwh = intercept + slope * temp_mean_c
-- A slope of -900 means: each 1 °C colder adds ~900 MWh/day of demand.
-- Heating season "2024/25" = October 2024 .. April 2025.
CREATE OR REPLACE TABLE mart_temp_sensitivity AS
WITH d AS (
    SELECT
        *,
        CASE WHEN month >= 10 THEN year ELSE year - 1 END AS season_start_year
    FROM fct_daily
    WHERE is_complete
      AND day_type = 'Working day'
      AND month IN (10, 11, 12, 1, 2, 3, 4)
      AND temp_mean_c < 15
)
SELECT
    season_start_year::VARCHAR || '/' || right((season_start_year + 1)::VARCHAR, 2) AS heating_season,
    season_start_year,
    count(*)                                              AS n_days,
    regr_slope(end_consumption_mwh, temp_mean_c)          AS slope_mwh_per_degc,
    regr_intercept(end_consumption_mwh, temp_mean_c)      AS intercept_mwh,
    regr_r2(end_consumption_mwh, temp_mean_c)             AS r2,
    avg(temp_mean_c)                                      AS temp_mean_c,
    avg(end_consumption_mwh)                              AS end_consumption_mean_mwh
FROM d
GROUP BY season_start_year
HAVING count(*) >= 30
ORDER BY season_start_year;
