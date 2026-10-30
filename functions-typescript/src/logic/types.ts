/**
 * Plain TypeScript views of ontology objects used by the pure logic in this folder.
 * The Foundry bindings (src/foundry) map ontology objects onto these types, which keeps
 * the business rules unit-testable without the Foundry runtime.
 */

export type Sex = "M" | "F" | "X" | "U";

export type DiagnosisGroup =
  | "ALZHEIMERS"
  | "MCI"
  | "FTD"
  | "DLB"
  | "PARKINSONS"
  | "ALS"
  | "VASCULAR_DEMENTIA"
  | "NONE";

export type AmyloidStatus = "POSITIVE" | "NEGATIVE" | "UNKNOWN";

/** Mirrors the Patient object type (backed by curated/cohort_features). */
export interface PatientFeatures {
  patientId: string;
  sex: Sex;
  ageYears: number | null;
  isDeceased: boolean;
  primaryDiagnosisGroup: DiagnosisGroup;
  latestMmse: number | null;
  latestMoca: number | null;
  latestCdrSb: number | null;
  latestAbeta4240Ratio: number | null;
  latestPtau181: number | null;
  latestPtau217: number | null;
  latestNfl: number | null;
  latestGfap: number | null;
  amyloidStatus: AmyloidStatus;
  hasCsf: boolean;
  hasMri: boolean;
  hasPet: boolean;
  hasGenetics: boolean;
  apoeE4Carrier: boolean | null;
  consentGenetics: boolean;
  consentResearch: boolean;
  eligibleForResearch: boolean;
}

export type QcStatus = "PASS" | "WARN" | "FAIL";

/** Mirrors the BiomarkerMeasurement object type. */
export interface Measurement {
  measurementId: string;
  patientId: string;
  analyte: string;
  value: number;
  unit: string;
  measuredDate: string; // ISO date
  qcStatus: QcStatus;
  belowLloq: boolean;
  aboveUloq: boolean;
  isAbnormal: boolean;
}

export type Severity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

/** Mirrors the DataQualityIssue object type. */
export interface DataQualityIssueView {
  issueId: string;
  ruleCode: string;
  severity: Severity;
  status: "OPEN" | "IN_PROGRESS" | "RESOLVED" | "DISMISSED";
  detectedDate: string; // ISO date
  patientId: string | null;
}
