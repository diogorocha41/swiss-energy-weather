-- Days with missing quarter-hours or weather hours (excluded from the models).
SELECT date_local, n_quarter_hours, n_weather_hours
FROM fct_daily
WHERE NOT is_complete
