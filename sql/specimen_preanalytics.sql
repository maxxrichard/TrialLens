-- Pre-analytical quality of primary specimens: processing delay by specimen type.
-- CSF processed later than 2 h after collection is flagged for amyloid measurements.
SELECT
    specimen_type,
    COUNT(*) AS n_primary_specimens,
    ROUND(PERCENTILE_APPROX(processing_delay_hours, 0.5), 2) AS median_delay_hours,
    ROUND(PERCENTILE_APPROX(processing_delay_hours, 0.95), 2) AS p95_delay_hours,
    SUM(CASE WHEN processing_delay_hours > 2 THEN 1 ELSE 0 END) AS n_over_2h,
    SUM(CASE WHEN processing_delay_hours > 24 THEN 1 ELSE 0 END) AS n_over_24h
FROM specimen_inventory
WHERE parent_specimen_id IS NULL
GROUP BY specimen_type
ORDER BY specimen_type
