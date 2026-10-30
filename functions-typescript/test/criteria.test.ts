import { attritionFunnel, Criterion, evaluatePatient, validateCriteria } from "../src/logic";
import { patient } from "./fixtures";

const EARLY_AD: Criterion[] = [
  { type: "DIAGNOSIS_GROUP", values: ["ALZHEIMERS", "MCI"] },
  { type: "AMYLOID_STATUS", value: "POSITIVE" },
  { type: "COGNITIVE_SCORE", instrument: "MMSE", operator: ">=", value: 20 },
  { type: "AGE_RANGE", min: 50, max: 85 },
];

describe("evaluatePatient", () => {
  it("includes a patient meeting every criterion", () => {
    const result = evaluatePatient(patient(), EARLY_AD);
    expect(result.included).toBe(true);
    expect(result.reasons).toEqual([]);
  });

  it("explains why a patient is excluded", () => {
    const result = evaluatePatient(patient({ latestMmse: 17, amyloidStatus: "NEGATIVE" }), EARLY_AD);
    expect(result.included).toBe(false);
    expect(result.reasons).toEqual(["fails: amyloid positive", "fails: MMSE >= 20"]);
  });

  it("treats missing data on inclusion criteria as exclusion", () => {
    const result = evaluatePatient(patient({ latestMmse: null }), EARLY_AD);
    expect(result.included).toBe(false);
    expect(result.reasons).toEqual(["missing data for: MMSE >= 20"]);
  });

  it("applies exclusion criteria", () => {
    const criteria: Criterion[] = [{ type: "BIOMARKER", analyte: "NFL", operator: ">", value: 30, exclude: true }];
    expect(evaluatePatient(patient({ latestNfl: 45 }), criteria).included).toBe(false);
    expect(evaluatePatient(patient({ latestNfl: 12 }), criteria).included).toBe(true);
    // An exclusion criterion that cannot be evaluated does not exclude.
    expect(evaluatePatient(patient({ latestNfl: null }), criteria).included).toBe(true);
  });

  it("always excludes patients not eligible for research", () => {
    const result = evaluatePatient(patient({ eligibleForResearch: false }), []);
    expect(result.included).toBe(false);
  });

  it("does not evaluate APOE without genetics consent", () => {
    const criteria: Criterion[] = [{ type: "APOE_E4_CARRIER", value: true }];
    expect(evaluatePatient(patient(), criteria).included).toBe(true);
    const noConsent = evaluatePatient(patient({ consentGenetics: false }), criteria);
    expect(noConsent.included).toBe(false);
    expect(noConsent.results[0].missingData).toBe(true);
  });
});

describe("attritionFunnel", () => {
  it("counts remaining patients after each criterion", () => {
    const patients = [
      patient({ patientId: "a" }),
      patient({ patientId: "b", primaryDiagnosisGroup: "PARKINSONS" }),
      patient({ patientId: "c", amyloidStatus: "NEGATIVE" }),
      patient({ patientId: "d", eligibleForResearch: false }),
    ];
    expect(attritionFunnel(patients, EARLY_AD).map((s) => s.remaining)).toEqual([4, 3, 2, 1, 1, 1]);
  });
});

describe("validateCriteria", () => {
  it("accepts well-formed criteria", () => {
    const { criteria, errors } = validateCriteria(JSON.parse(JSON.stringify(EARLY_AD)));
    expect(errors).toEqual([]);
    expect(criteria).toHaveLength(4);
  });

  it("rejects malformed input without coercion", () => {
    const { criteria, errors } = validateCriteria([
      { type: "BIOMARKER", analyte: "PTAU999", operator: ">", value: 1 },
      { type: "COGNITIVE_SCORE", instrument: "MMSE", operator: "~", value: 20 },
      { type: "AGE_RANGE", min: 80, max: 60 },
      { type: "SEX", values: ["male"] },
      { type: "HAS_DATA", modality: "PET" },
      "free text",
    ]);
    expect(criteria).toEqual([{ type: "HAS_DATA", modality: "PET", exclude: false }]);
    expect(errors).toHaveLength(5);
  });

  it("rejects non-arrays", () => {
    expect(validateCriteria({ type: "SEX" }).errors).toEqual(["criteria must be a JSON array"]);
  });
});
