/**
 * Mapping between ontology objects (generated @foundry/ontology-api types) and the plain
 * types used by the unit-tested logic in src/logic.
 */
import { BiomarkerMeasurement, DataQualityIssue, Patient } from "@foundry/ontology-api";

import { AmyloidStatus, DataQualityIssueView, DiagnosisGroup, Measurement, PatientFeatures, QcStatus, Severity, Sex } from "../logic";

const num = (value: number | undefined): number | null => (value === undefined ? null : value);

export function toPatientFeatures(p: Patient): PatientFeatures {
  return {
    patientId: p.patientId,
    sex: (p.sex ?? "U") as Sex,
    ageYears: num(p.ageYears),
    isDeceased: p.isDeceased ?? false,
    primaryDiagnosisGroup: (p.primaryDiagnosisGroup ?? "NONE") as DiagnosisGroup,
    latestMmse: num(p.latestMmse),
    latestMoca: num(p.latestMoca),
    latestCdrSb: num(p.latestCdrSb),
    latestAbeta4240Ratio: num(p.latestAbeta4240Ratio),
    latestPtau181: num(p.latestPtau181),
    latestPtau217: num(p.latestPtau217),
    latestNfl: num(p.latestNfl),
    latestGfap: num(p.latestGfap),
    amyloidStatus: (p.amyloidStatus ?? "UNKNOWN") as AmyloidStatus,
    hasCsf: p.hasCsf ?? false,
    hasMri: p.hasMri ?? false,
    hasPet: p.hasPet ?? false,
    hasGenetics: p.hasGenetics ?? false,
    apoeE4Carrier: p.apoeE4Carrier ?? null,
    consentGenetics: p.consentGenetics ?? false,
    consentResearch: p.consentResearch ?? false,
    eligibleForResearch: p.eligibleForResearch ?? false,
  };
}

export function toMeasurement(m: BiomarkerMeasurement): Measurement {
  return {
    measurementId: m.measurementId,
    patientId: m.patientId ?? "",
    analyte: m.analyte ?? "",
    value: m.value ?? Number.NaN,
    unit: m.unit ?? "",
    measuredDate: m.measuredDate?.toISOString() ?? "",
    qcStatus: (m.qcStatus ?? "WARN") as QcStatus,
    belowLloq: m.belowLloq ?? false,
    aboveUloq: m.aboveUloq ?? false,
    isAbnormal: m.isAbnormal ?? false,
  };
}

export function toIssueView(i: DataQualityIssue): DataQualityIssueView {
  return {
    issueId: i.issueId,
    ruleCode: i.ruleCode ?? "",
    severity: (i.severity ?? "LOW") as Severity,
    status: (i.status ?? "OPEN") as DataQualityIssueView["status"],
    detectedDate: i.detectedDate?.toISOString() ?? "",
    patientId: i.patientId ?? null,
  };
}
