-- Consent coverage per study and site: share of participants whose data may be used,
-- and share with an active genetics consent (required for APOE-based selection).
SELECT
    study_code,
    site_code,
    COUNT(*) AS n_enrollments,
    SUM(CASE WHEN status IN ('ENROLLED', 'COMPLETED') THEN 1 ELSE 0 END) AS n_active_or_completed,
    ROUND(AVG(CASE WHEN is_consent_valid THEN 1.0 ELSE 0.0 END), 3) AS share_valid_consent,
    ROUND(AVG(CASE WHEN consent_genetics THEN 1.0 ELSE 0.0 END), 3) AS share_genetics_consent,
    ROUND(AVG(CASE WHEN consent_imaging THEN 1.0 ELSE 0.0 END), 3) AS share_imaging_consent,
    SUM(CASE WHEN status IN ('ENROLLED', 'COMPLETED') AND NOT is_consent_valid THEN 1 ELSE 0 END) AS n_consent_gaps
FROM study_participation
GROUP BY study_code, site_code
ORDER BY study_code, site_code
