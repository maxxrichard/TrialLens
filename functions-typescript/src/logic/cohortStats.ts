import { PatientFeatures } from "./types";

export interface CohortSummary {
  nPatients: number;
  medianAge: number | null;
  shareFemale: number | null;
  shareAmyloidPositive: number | null;
  shareApoeE4Carrier: number | null;
  medianMmse: number | null;
  diagnosisCounts: Record<string, number>;
  dataAvailability: { csf: number; mri: number; pet: number; genetics: number };
}

export function median(values: number[]): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 1 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function share(numerator: number, denominator: number): number | null {
  return denominator === 0 ? null : Math.round((numerator / denominator) * 1000) / 1000;
}

function present<T>(values: (T | null)[]): T[] {
  return values.filter((v): v is T => v !== null);
}

/** Summary shown on the cohort header card and stored with a locked cohort. */
export function summarizeCohort(patients: PatientFeatures[]): CohortSummary {
  const n = patients.length;
  const diagnosisCounts: Record<string, number> = {};
  for (const p of patients) {
    diagnosisCounts[p.primaryDiagnosisGroup] = (diagnosisCounts[p.primaryDiagnosisGroup] ?? 0) + 1;
  }
  const knownAmyloid = patients.filter((p) => p.amyloidStatus !== "UNKNOWN");
  // APOE is only reported for participants with an active genetics consent.
  const knownApoe = present(patients.map((p) => (p.consentGenetics ? p.apoeE4Carrier : null)));
  return {
    nPatients: n,
    medianAge: median(present(patients.map((p) => p.ageYears))),
    shareFemale: share(patients.filter((p) => p.sex === "F").length, n),
    shareAmyloidPositive: share(knownAmyloid.filter((p) => p.amyloidStatus === "POSITIVE").length, knownAmyloid.length),
    shareApoeE4Carrier: share(knownApoe.filter(Boolean).length, knownApoe.length),
    medianMmse: median(present(patients.map((p) => p.latestMmse))),
    diagnosisCounts,
    dataAvailability: {
      csf: patients.filter((p) => p.hasCsf).length,
      mri: patients.filter((p) => p.hasMri).length,
      pet: patients.filter((p) => p.hasPet).length,
      genetics: patients.filter((p) => p.hasGenetics && p.consentGenetics).length,
    },
  };
}

/**
 * Minimum cell size for aggregates leaving the platform (e.g. in exported reports):
 * counts below the threshold are suppressed to limit re-identification risk.
 */
export const MIN_CELL_SIZE = 5;

export function suppressSmallCells(counts: Record<string, number>, minimum = MIN_CELL_SIZE): Record<string, number | null> {
  const result: Record<string, number | null> = {};
  for (const [key, value] of Object.entries(counts)) {
    result[key] = value > 0 && value < minimum ? null : value;
  }
  return result;
}
