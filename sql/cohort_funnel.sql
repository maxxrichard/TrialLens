-- Attrition funnel for an early Alzheimer's disease cohort (amyloid positive, mild stage).
-- Mirrors the default criteria template of the Cohort Builder app.
SELECT step_order, step, n_patients
FROM (
    SELECT 1 AS step_order, 'All patients' AS step, COUNT(*) AS n_patients
    FROM cohort_features
    UNION ALL
    SELECT 2, 'Eligible for research (valid consent, alive)', COUNT(*)
    FROM cohort_features
    WHERE eligible_for_research
    UNION ALL
    SELECT 3, 'Diagnosis: AD or MCI', COUNT(*)
    FROM cohort_features
    WHERE eligible_for_research AND primary_diagnosis_group IN ('ALZHEIMERS', 'MCI')
    UNION ALL
    SELECT 4, 'Amyloid positive (CSF ratio or PET)', COUNT(*)
    FROM cohort_features
    WHERE eligible_for_research AND primary_diagnosis_group IN ('ALZHEIMERS', 'MCI')
      AND amyloid_status = 'POSITIVE'
    UNION ALL
    SELECT 5, 'MMSE 20-28', COUNT(*)
    FROM cohort_features
    WHERE eligible_for_research AND primary_diagnosis_group IN ('ALZHEIMERS', 'MCI')
      AND amyloid_status = 'POSITIVE' AND latest_mmse BETWEEN 20 AND 28
    UNION ALL
    SELECT 6, 'Structural MRI available', COUNT(*)
    FROM cohort_features
    WHERE eligible_for_research AND primary_diagnosis_group IN ('ALZHEIMERS', 'MCI')
      AND amyloid_status = 'POSITIVE' AND latest_mmse BETWEEN 20 AND 28 AND has_mri
) funnel
ORDER BY step_order
