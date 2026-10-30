-- Assay run quality: failure rate and share of results outside the quantification range.
-- Used by the biomarker laboratory to decide on run repeats.
SELECT
    run_id,
    MAX(platform) AS platform,
    MIN(run_date) AS run_date,
    COUNT(*) AS n_results,
    ROUND(AVG(CASE WHEN qc_status = 'FAIL' THEN 1.0 ELSE 0.0 END), 3) AS fail_rate,
    ROUND(AVG(CASE WHEN qc_status = 'WARN' THEN 1.0 ELSE 0.0 END), 3) AS warn_rate,
    ROUND(AVG(CASE WHEN value < lloq THEN 1.0 ELSE 0.0 END), 3) AS share_below_lloq,
    ROUND(AVG(CASE WHEN value > uloq THEN 1.0 ELSE 0.0 END), 3) AS share_above_uloq
FROM biomarker_assays_clean
GROUP BY run_id
HAVING COUNT(*) >= 3
ORDER BY fail_rate DESC, run_date DESC
