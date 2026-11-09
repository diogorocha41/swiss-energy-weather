-- Never publish empty marts (e.g. Swissgrid extract missing in CI).
SELECT 'fct_daily is empty' AS problem
WHERE (SELECT count(*) FROM {{ ref('fct_daily') }} WHERE is_complete) = 0
