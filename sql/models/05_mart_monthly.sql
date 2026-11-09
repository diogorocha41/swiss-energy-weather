-- Mart: monthly totals with year-over-year change.
CREATE OR REPLACE TABLE mart_monthly AS
WITH m AS (
    SELECT
        year,
        month,
        make_date(year, month, 1)              AS month_start,
        sum(end_consumption_mwh) / 1000.0      AS end_consumption_gwh,
        sum(production_mwh) / 1000.0           AS production_gwh,
        avg(temp_mean_c)                       AS temp_mean_c,
        sum(hdd_20_12)                         AS hdd_20_12,
        count(*)                               AS n_days,
        bool_and(is_complete)                  AS is_complete
    FROM fct_daily
    GROUP BY year, month
)
SELECT
    *,
    production_gwh - end_consumption_gwh                                         AS balance_gwh,
    lag(end_consumption_gwh) OVER (PARTITION BY month ORDER BY year)             AS end_consumption_gwh_prev_year,
    100.0 * (end_consumption_gwh / lag(end_consumption_gwh) OVER (PARTITION BY month ORDER BY year) - 1)
                                                                                 AS yoy_change_pct
FROM m
ORDER BY month_start;
