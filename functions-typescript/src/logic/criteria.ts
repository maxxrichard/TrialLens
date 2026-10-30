import { DiagnosisGroup, PatientFeatures, Sex } from "./types";

/**
 * Cohort criteria: the structured representation shared by the Cohort Builder app,
 * the createCohortFromCriteria action and the AIP Logic "criteria from text" flow.
 */

export type Operator = "<" | "<=" | ">" | ">=" | "==" | "!=";

export const BIOMARKER_FEATURES = {
  ABETA42_40_RATIO: "latestAbeta4240Ratio",
  PTAU181: "latestPtau181",
  PTAU217: "latestPtau217",
  NFL: "latestNfl",
  GFAP: "latestGfap",
} as const;
export type BiomarkerFeature = keyof typeof BIOMARKER_FEATURES;

export const COGNITIVE_FEATURES = {
  MMSE: "latestMmse",
  MOCA: "latestMoca",
  CDR_SB: "latestCdrSb",
} as const;
export type CognitiveInstrument = keyof typeof COGNITIVE_FEATURES;

export type DataModality = "CSF" | "MRI" | "PET" | "GENETICS";

interface BaseCriterion {
  /** Exclusion criteria remove patients that match them. */
  exclude?: boolean;
}

export type Criterion = BaseCriterion &
  (
    | { type: "AGE_RANGE"; min?: number; max?: number }
    | { type: "SEX"; values: Sex[] }
    | { type: "DIAGNOSIS_GROUP"; values: DiagnosisGroup[] }
    | { type: "BIOMARKER"; analyte: BiomarkerFeature; operator: Operator; value: number }
    | { type: "COGNITIVE_SCORE"; instrument: CognitiveInstrument; operator: Operator; value: number }
    | { type: "AMYLOID_STATUS"; value: "POSITIVE" | "NEGATIVE" }
    | { type: "HAS_DATA"; modality: DataModality }
    | { type: "APOE_E4_CARRIER"; value: boolean }
  );

export interface CriterionResult {
  criterion: Criterion;
  /** True when the patient satisfies the criterion (before applying `exclude`). */
  matches: boolean;
  /** True when the criterion could not be evaluated because data is missing. */
  missingData: boolean;
}

export interface PatientEvaluation {
  patientId: string;
  included: boolean;
  /** Human-readable reasons, shown in the Cohort Builder and stored on CohortMembership. */
  reasons: string[];
  results: CriterionResult[];
}

const SEXES: Sex[] = ["M", "F", "X", "U"];
const DIAGNOSIS_GROUPS: DiagnosisGroup[] = [
  "ALZHEIMERS", "MCI", "FTD", "DLB", "PARKINSONS", "ALS", "VASCULAR_DEMENTIA", "NONE",
];
const OPERATORS: Operator[] = ["<", "<=", ">", ">=", "==", "!="];
const MODALITIES: DataModality[] = ["CSF", "MRI", "PET", "GENETICS"];

export function compare(left: number, operator: Operator, right: number): boolean {
  switch (operator) {
    case "<":
      return left < right;
    case "<=":
      return left <= right;
    case ">":
      return left > right;
    case ">=":
      return left >= right;
    case "==":
      return left === right;
    case "!=":
      return left !== right;
  }
}

function numeric(value: number | null, check: (v: number) => boolean): [boolean, boolean] {
  return value === null ? [false, true] : [check(value), false];
}

export function evaluateCriterion(patient: PatientFeatures, criterion: Criterion): CriterionResult {
  let matches = false;
  let missingData = false;
  switch (criterion.type) {
    case "AGE_RANGE": {
      const { min, max } = criterion;
      [matches, missingData] = numeric(
        patient.ageYears,
        (age) => (min === undefined || age >= min) && (max === undefined || age <= max),
      );
      break;
    }
    case "SEX":
      matches = criterion.values.includes(patient.sex);
      break;
    case "DIAGNOSIS_GROUP":
      matches = criterion.values.includes(patient.primaryDiagnosisGroup);
      break;
    case "BIOMARKER": {
      const { operator, value } = criterion;
      [matches, missingData] = numeric(patient[BIOMARKER_FEATURES[criterion.analyte]], (v) => compare(v, operator, value));
      break;
    }
    case "COGNITIVE_SCORE": {
      const { operator, value } = criterion;
      [matches, missingData] = numeric(patient[COGNITIVE_FEATURES[criterion.instrument]], (v) => compare(v, operator, value));
      break;
    }
    case "AMYLOID_STATUS":
      missingData = patient.amyloidStatus === "UNKNOWN";
      matches = patient.amyloidStatus === criterion.value;
      break;
    case "HAS_DATA":
      matches = {
        CSF: patient.hasCsf,
        MRI: patient.hasMri,
        PET: patient.hasPet,
        GENETICS: patient.hasGenetics,
      }[criterion.modality];
      break;
    case "APOE_E4_CARRIER":
      // Genetic criteria may only be evaluated with an active genetics consent.
      if (!patient.consentGenetics || patient.apoeE4Carrier === null) {
        missingData = true;
        matches = false;
      } else {
        matches = patient.apoeE4Carrier === criterion.value;
      }
      break;
  }
  return { criterion, matches, missingData };
}

export function describeCriterion(criterion: Criterion): string {
  const prefix = criterion.exclude ? "NOT " : "";
  switch (criterion.type) {
    case "AGE_RANGE":
      return `${prefix}age ${criterion.min ?? "-"}..${criterion.max ?? "-"}`;
    case "SEX":
      return `${prefix}sex in ${criterion.values.join(", ")}`;
    case "DIAGNOSIS_GROUP":
      return `${prefix}diagnosis in ${criterion.values.join(", ")}`;
    case "BIOMARKER":
      return `${prefix}${criterion.analyte} ${criterion.operator} ${criterion.value}`;
    case "COGNITIVE_SCORE":
      return `${prefix}${criterion.instrument} ${criterion.operator} ${criterion.value}`;
    case "AMYLOID_STATUS":
      return `${prefix}amyloid ${criterion.value.toLowerCase()}`;
    case "HAS_DATA":
      return `${prefix}has ${criterion.modality} data`;
    case "APOE_E4_CARRIER":
      return `${prefix}APOE e4 carrier = ${criterion.value}`;
  }
}

/**
 * Evaluate a patient against all criteria. Patients that are not eligible for research
 * (no valid consent, deceased) are always excluded, whatever the criteria say. Inclusion
 * criteria with missing data exclude the patient; exclusion criteria with missing data
 * do not (the patient cannot be shown to meet them).
 */
export function evaluatePatient(patient: PatientFeatures, criteria: Criterion[]): PatientEvaluation {
  const results = criteria.map((c) => evaluateCriterion(patient, c));
  const reasons: string[] = [];
  if (!patient.eligibleForResearch) {
    reasons.push("not eligible for research (consent or vital status)");
  }
  for (const result of results) {
    const label = describeCriterion(result.criterion);
    if (result.criterion.exclude) {
      if (result.matches) reasons.push(`meets exclusion: ${label}`);
    } else if (result.missingData) {
      reasons.push(`missing data for: ${label}`);
    } else if (!result.matches) {
      reasons.push(`fails: ${label}`);
    }
  }
  return { patientId: patient.patientId, included: reasons.length === 0, reasons, results };
}

export interface FunnelStep {
  label: string;
  remaining: number;
}

/** Sequential attrition funnel, applying criteria in the order given. */
export function attritionFunnel(patients: PatientFeatures[], criteria: Criterion[]): FunnelStep[] {
  let remaining = patients.filter((p) => p.eligibleForResearch);
  const steps: FunnelStep[] = [
    { label: "All patients", remaining: patients.length },
    { label: "Eligible for research", remaining: remaining.length },
  ];
  for (const criterion of criteria) {
    remaining = remaining.filter((p) => evaluatePatient(p, [criterion]).included);
    steps.push({ label: describeCriterion(criterion), remaining: remaining.length });
  }
  return steps;
}

export interface ValidationResult {
  criteria: Criterion[];
  errors: string[];
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

/**
 * Validate untrusted input (Workshop JSON, AIP Logic output) into typed criteria.
 * Invalid entries are reported and dropped, never silently coerced.
 */
export function validateCriteria(input: unknown): ValidationResult {
  const errors: string[] = [];
  const criteria: Criterion[] = [];
  if (!Array.isArray(input)) {
    return { criteria, errors: ["criteria must be a JSON array"] };
  }
  input.forEach((raw, index) => {
    const where = `criterion ${index}`;
    if (typeof raw !== "object" || raw === null) {
      errors.push(`${where}: not an object`);
      return;
    }
    const c = raw as Record<string, unknown>;
    const exclude = c.exclude === true;
    switch (c.type) {
      case "AGE_RANGE":
        if ((c.min !== undefined && !isNumber(c.min)) || (c.max !== undefined && !isNumber(c.max))) {
          errors.push(`${where}: min/max must be numbers`);
        } else if (c.min === undefined && c.max === undefined) {
          errors.push(`${where}: AGE_RANGE needs min or max`);
        } else if (isNumber(c.min) && isNumber(c.max) && c.min > c.max) {
          errors.push(`${where}: min > max`);
        } else {
          criteria.push({ type: "AGE_RANGE", min: c.min as number | undefined, max: c.max as number | undefined, exclude });
        }
        return;
      case "SEX":
      case "DIAGNOSIS_GROUP": {
        const allowed: string[] = c.type === "SEX" ? SEXES : DIAGNOSIS_GROUPS;
        const values = c.values;
        if (!Array.isArray(values) || values.length === 0 || !values.every((v) => allowed.includes(v as string))) {
          errors.push(`${where}: values must be a non-empty subset of ${allowed.join(", ")}`);
        } else if (c.type === "SEX") {
          criteria.push({ type: "SEX", values: values as Sex[], exclude });
        } else {
          criteria.push({ type: "DIAGNOSIS_GROUP", values: values as DiagnosisGroup[], exclude });
        }
        return;
      }
      case "BIOMARKER":
      case "COGNITIVE_SCORE": {
        const keyName = c.type === "BIOMARKER" ? "analyte" : "instrument";
        const allowed = Object.keys(c.type === "BIOMARKER" ? BIOMARKER_FEATURES : COGNITIVE_FEATURES);
        const key = c[keyName];
        if (typeof key !== "string" || !allowed.includes(key)) {
          errors.push(`${where}: ${keyName} must be one of ${allowed.join(", ")}`);
        } else if (!OPERATORS.includes(c.operator as Operator)) {
          errors.push(`${where}: operator must be one of ${OPERATORS.join(" ")}`);
        } else if (!isNumber(c.value)) {
          errors.push(`${where}: value must be a number`);
        } else if (c.type === "BIOMARKER") {
          criteria.push({ type: "BIOMARKER", analyte: key as BiomarkerFeature, operator: c.operator as Operator, value: c.value, exclude });
        } else {
          criteria.push({
            type: "COGNITIVE_SCORE",
            instrument: key as CognitiveInstrument,
            operator: c.operator as Operator,
            value: c.value,
            exclude,
          });
        }
        return;
      }
      case "AMYLOID_STATUS":
        if (c.value !== "POSITIVE" && c.value !== "NEGATIVE") {
          errors.push(`${where}: value must be POSITIVE or NEGATIVE`);
        } else {
          criteria.push({ type: "AMYLOID_STATUS", value: c.value as "POSITIVE" | "NEGATIVE", exclude });
        }
        return;
      case "HAS_DATA":
        if (!MODALITIES.includes(c.modality as DataModality)) {
          errors.push(`${where}: modality must be one of ${MODALITIES.join(", ")}`);
        } else {
          criteria.push({ type: "HAS_DATA", modality: c.modality as DataModality, exclude });
        }
        return;
      case "APOE_E4_CARRIER":
        if (typeof c.value !== "boolean") {
          errors.push(`${where}: value must be true or false`);
        } else {
          criteria.push({ type: "APOE_E4_CARRIER", value: c.value, exclude });
        }
        return;
      default:
        errors.push(`${where}: unknown type ${String(c.type)}`);
    }
  });
  return { criteria, errors };
}
