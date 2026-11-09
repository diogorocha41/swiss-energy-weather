-- One row per country and local day, with per-capita consumption.
-- is_complete excludes days with missing data or a known grid incident (seed grid_events).
-- in_common_window = both countries have a complete day (fair comparison).
WITH d AS (
    SELECT
        h.country,
        h.date_local,
        any_value(h.day_type)                       AS day_type,
        year(h.date_local)                          AS year,
        month(h.date_local)                         AS month,
        sum(h.consumption_mwh)                      AS consumption_mwh,
        sum(h.low_voltage_mwh)                      AS low_voltage_mwh,
        avg(h.temp_c)                               AS temp_mean_c,
        sum(h.n_quarter_hours)                      AS n_quarter_hours,
        count(h.temp_c)                             AS n_temp_hours,
        bool_or(h.is_grid_event)                    AS has_grid_event
    FROM {{ ref('fct_country_hourly') }} h
    GROUP BY h.country, h.date_local
),
flagged AS (
    SELECT
        d.*,
        p.population,
        1000.0 * d.consumption_mwh / p.population   AS kwh_per_capita,
        1000.0 * d.low_voltage_mwh / p.population   AS low_voltage_kwh_per_capita,
        d.n_quarter_hours >= 92 AND d.n_temp_hours >= 20 AND NOT d.has_grid_event AS is_complete
    FROM d
    JOIN {{ source('raw', 'dim_country') }} p USING (country)
)
SELECT
    f.*,
    f.is_complete AND f.date_local IN (
        SELECT date_local FROM flagged WHERE is_complete
        GROUP BY date_local HAVING count(DISTINCT country) = 2
    ) AS in_common_window
FROM flagged f
