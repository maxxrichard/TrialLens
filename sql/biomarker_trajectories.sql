-- Mean biomarker level by diagnosis group and follow-up year (QC-failed results excluded).
-- Feeds the "Biomarker trajectories" Quiver analysis.
SELECT
    f.primary_diagnosis_group,
    b.analyte,
    CAST(FLOOR(b.days_since_baseline / 365.25) AS INT) AS follow_up_year,
    COUNT(DISTINCT b.patient_id) AS n_patients,
    ROUND(AVG(b.value), 3) AS mean_value,
    ROUND(PERCENTILE_APPROX(b.value, 0.5), 3) AS median_value
FROM biomarker_timeseries b
JOIN cohort_features f ON f.patient_id = b.patient_id
WHERE b.source = 'ASSAY' AND b.qc_status <> 'FAIL'
GROUP BY f.primary_diagnosis_group, b.analyte, CAST(FLOOR(b.days_since_baseline / 365.25) AS INT)
ORDER BY b.analyte, f.primary_diagnosis_group, follow_up_year
