-- Every hour must appear exactly once in the hourly fact table.
SELECT hour_utc_end, count(*) AS n
FROM fct_hourly
GROUP BY hour_utc_end
HAVING count(*) > 1
