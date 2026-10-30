import { Measurement } from "./types";

/**
 * Suggested review decision for a biomarker measurement. Reviewers see the suggestion
 * and its flags in the Biomarker Review app; only a human records the final decision
 * (the reviewBiomarkerMeasurement action). EXCLUDED is never suggested automatically.
 */

export type ReviewDecision = "ACCEPTED" | "EXCLUDED" | "REPEAT_REQUESTED";

export type ReviewFlag =
  | "QC_FAIL"
  | "QC_WARN"
  | "ABOVE_ULOQ"
  | "BELOW_LLOQ"
  | "OUT_OF_REFERENCE_RANGE"
  | "LARGE_CHANGE_FROM_PREVIOUS";

export interface ReviewSuggestion {
  measurementId: string;
  suggestedDecision: Exclude<ReviewDecision, "EXCLUDED">;
  flags: ReviewFlag[];
  previousValue: number | null;
  relativeChange: number | null;
  rationale: string;
}

export interface ReviewOptions {
  /** Relative change vs. the previous valid measurement that triggers a flag (0.5 = 50 %). */
  maxRelativeChange: number;
}

export const DEFAULT_REVIEW_OPTIONS: ReviewOptions = { maxRelativeChange: 0.5 };

export function relativeChange(previous: number, current: number): number {
  if (previous === 0) {
    return current === 0 ? 0 : Number.POSITIVE_INFINITY;
  }
  return Math.abs(current - previous) / Math.abs(previous);
}

/** Most recent earlier measurement of the same analyte that did not fail QC. */
export function previousValid(measurement: Measurement, history: Measurement[]): Measurement | null {
  const candidates = history
    .filter(
      (m) =>
        m.measurementId !== measurement.measurementId &&
        m.patientId === measurement.patientId &&
        m.analyte === measurement.analyte &&
        m.qcStatus !== "FAIL" &&
        m.measuredDate < measurement.measuredDate,
    )
    .sort((a, b) => (a.measuredDate < b.measuredDate ? 1 : a.measuredDate > b.measuredDate ? -1 : 0));
  return candidates.length > 0 ? candidates[0] : null;
}

export function suggestReview(
  measurement: Measurement,
  history: Measurement[],
  options: ReviewOptions = DEFAULT_REVIEW_OPTIONS,
): ReviewSuggestion {
  const flags: ReviewFlag[] = [];
  if (measurement.qcStatus === "FAIL") flags.push("QC_FAIL");
  if (measurement.qcStatus === "WARN") flags.push("QC_WARN");
  if (measurement.aboveUloq) flags.push("ABOVE_ULOQ");
  if (measurement.belowLloq) flags.push("BELOW_LLOQ");
  if (measurement.isAbnormal) flags.push("OUT_OF_REFERENCE_RANGE");

  const previous = previousValid(measurement, history);
  const change = previous ? relativeChange(previous.value, measurement.value) : null;
  if (change !== null && change > options.maxRelativeChange) flags.push("LARGE_CHANGE_FROM_PREVIOUS");

  const repeat =
    flags.includes("QC_FAIL") ||
    flags.includes("ABOVE_ULOQ") ||
    (flags.includes("QC_WARN") && flags.includes("LARGE_CHANGE_FROM_PREVIOUS"));

  const reasons: string[] = [];
  if (flags.includes("QC_FAIL")) reasons.push("assay run failed QC");
  if (flags.includes("ABOVE_ULOQ")) reasons.push("value above ULOQ, re-run with dilution");
  if (flags.includes("QC_WARN") && flags.includes("LARGE_CHANGE_FROM_PREVIOUS")) {
    reasons.push("QC warning combined with an implausible change from the previous value");
  }
  if (!repeat && flags.includes("BELOW_LLOQ")) reasons.push("report as <LLOQ");
  if (!repeat && flags.includes("LARGE_CHANGE_FROM_PREVIOUS")) reasons.push("large change; confirm clinically");

  return {
    measurementId: measurement.measurementId,
    suggestedDecision: repeat ? "REPEAT_REQUESTED" : "ACCEPTED",
    flags,
    previousValue: previous ? previous.value : null,
    relativeChange: change,
    rationale: reasons.length > 0 ? reasons.join("; ") : "no issues detected",
  };
}

/** Review queue ordering: repeats first, then flagged results, oldest first. */
export function reviewQueue(measurements: Measurement[], history: Measurement[] = measurements): ReviewSuggestion[] {
  const priority = (s: ReviewSuggestion) => (s.suggestedDecision === "REPEAT_REQUESTED" ? 0 : s.flags.length > 0 ? 1 : 2);
  const dates = new Map(measurements.map((m) => [m.measurementId, m.measuredDate]));
  return measurements
    .map((m) => suggestReview(m, history))
    .sort((a, b) => {
      const byPriority = priority(a) - priority(b);
      if (byPriority !== 0) return byPriority;
      const da = dates.get(a.measurementId) ?? "";
      const db = dates.get(b.measurementId) ?? "";
      return da < db ? -1 : da > db ? 1 : 0;
    });
}
