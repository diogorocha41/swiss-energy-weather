-- The comparison needs days where both countries have complete data.
SELECT 'no common days for CH and PT' AS problem
WHERE (SELECT count(*) FROM {{ ref('fct_country_daily') }} WHERE in_common_window) = 0
