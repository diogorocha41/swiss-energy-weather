-- Mart: average daily consumption per 1 °C temperature bin and day type.
CREATE OR REPLACE TABLE mart_temp_bins AS
SELECT
    floor(temp_mean_c)::INTEGER       AS temp_bin_c,
    day_type,
    count(*)                          AS n_days,
    avg(end_consumption_mwh)          AS end_consumption_mean_mwh,
    quantile_cont(end_consumption_mwh, 0.1) AS end_consumption_p10_mwh,
    quantile_cont(end_consumption_mwh, 0.9) AS end_consumption_p90_mwh
FROM fct_daily
WHERE is_complete
GROUP BY ALL
ORDER BY temp_bin_c, day_type;
