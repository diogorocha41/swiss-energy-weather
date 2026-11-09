-- Yearly consumption per person for full calendar years in the common window.
SELECT
    country,
    year,
    count(*)                                AS n_days,
    sum(consumption_mwh) / 1e6              AS consumption_twh,
    sum(kwh_per_capita)                     AS kwh_per_capita,
    sum(low_voltage_kwh_per_capita)         AS low_voltage_kwh_per_capita,
    avg(temp_mean_c)                        AS temp_mean_c,
    sum(CASE WHEN temp_mean_c < 12 THEN 20 - temp_mean_c ELSE 0 END) AS hdd_20_12
FROM {{ ref('fct_country_daily') }}
WHERE in_common_window
GROUP BY ALL
HAVING count(*) >= 360
ORDER BY country, year
