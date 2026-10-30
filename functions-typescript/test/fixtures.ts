import { Measurement, PatientFeatures } from "../src/logic";

export function patient(overrides: Partial<PatientFeatures> = {}): PatientFeatures {
  return {
    patientId: "TL-P-0000000000000001",
    sex: "F",
    ageYears: 71,
    isDeceased: false,
    primaryDiagnosisGroup: "MCI",
    latestMmse: 26,
    latestMoca: 23,
    latestCdrSb: 1.5,
    latestAbeta4240Ratio: 0.052,
    latestPtau181: 34,
    latestPtau217: 0.71,
    latestNfl: 14,
    latestGfap: 210,
    amyloidStatus: "POSITIVE",
    hasCsf: true,
    hasMri: true,
    hasPet: false,
    hasGenetics: true,
    apoeE4Carrier: true,
    consentGenetics: true,
    consentResearch: true,
    eligibleForResearch: true,
    ...overrides,
  };
}

export function measurement(overrides: Partial<Measurement> = {}): Measurement {
  return {
    measurementId: "ASSAY-BA0000001",
    patientId: "TL-P-0000000000000001",
    analyte: "NFL",
    value: 14,
    unit: "pg/mL",
    measuredDate: "2024-03-01",
    qcStatus: "PASS",
    belowLloq: false,
    aboveUloq: false,
    isAbnormal: false,
    ...overrides,
  };
}
