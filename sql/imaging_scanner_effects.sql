-- Scanner effects on hippocampal volumetrics: compare like with like (cognitively
-- unimpaired participants) across scanners before pooling sites.
SELECT
    i.manufacturer,
    i.field_strength_t,
    COUNT(*) AS n_series,
    ROUND(AVG(i.hippocampal_volume_mm3), 1) AS mean_hippocampal_volume_mm3,
    ROUND(STDDEV(i.hippocampal_volume_mm3), 1) AS sd_hippocampal_volume_mm3
FROM imaging_studies i
JOIN cohort_features f ON f.patient_id = i.patient_id
WHERE i.modality = 'MR'
  AND i.hippocampal_volume_mm3 IS NOT NULL
  AND f.primary_diagnosis_group = 'NONE'
GROUP BY i.manufacturer, i.field_strength_t
ORDER BY i.manufacturer, i.field_strength_t
