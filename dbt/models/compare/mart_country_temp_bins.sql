-- Average consumption per person on working days, per 1 °C temperature bin:
-- the shape of this curve shows where heating (left) and cooling (right) kick in.
-- Holiday periods are excluded so that business shutdowns do not distort the curve.
SELECT
    country,
    series,
    floor(temp_mean_c)::INTEGER  AS temp_bin_c,
    count(*)                     AS n_days,
    avg(kwh_pc)                  AS kwh_pc_mean
FROM {{ ref('int_country_daily_long') }}
WHERE day_type = 'Working day' AND NOT is_holiday_period
GROUP BY ALL
HAVING count(*) >= 5
ORDER BY country, series, temp_bin_c
