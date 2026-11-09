-- Swiss end-user load is roughly 5-12 GW. Values outside 2-20 GW point to a
-- unit or column-mapping error (e.g. kWh vs MWh, wrong series).
SELECT * FROM fct_hourly
WHERE n_quarter_hours = 4
  AND end_consumption_mwh NOT BETWEEN 2000 AND 20000
