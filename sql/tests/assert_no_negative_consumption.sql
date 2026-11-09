-- End-user consumption can never be negative.
SELECT * FROM fct_hourly WHERE end_consumption_mwh < 0
