-- ERA5 temperature per country and hour: population-weighted mean over the configured cities.
SELECT
    o.country,
    o.ts_utc                                                                              AS hour_utc,
    sum(o.temp_c * c.weight) / nullif(sum(c.weight) FILTER (WHERE o.temp_c IS NOT NULL), 0) AS temp_c,
    count(o.temp_c)                                                                       AS n_cities
FROM {{ source('raw', 'raw_openmeteo_hourly') }} o
JOIN {{ source('raw', 'dim_city') }} c USING (country, city)
GROUP BY 1, 2
