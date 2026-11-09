-- Mainland Portugal load is roughly 4-9 GW. Values outside 2-15 GW point to a
-- unit error, a broken export, or a grid incident not yet listed in seeds/grid_events.csv.
SELECT * FROM {{ ref('stg_pt_load_hourly') }}
WHERE n_quarter_hours = 4
  AND NOT is_grid_event
  AND consumption_mwh NOT BETWEEN 2000 AND 15000
