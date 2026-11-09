-- Weighted lowland temperature outside -30..45 °C means a parsing/unit error.
SELECT * FROM fct_hourly WHERE temp_c NOT BETWEEN -30 AND 45
