-- End-user consumption can never be negative.
SELECT * FROM {{ ref('fct_hourly') }} WHERE end_consumption_mwh < 0
