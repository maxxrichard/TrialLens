/**
 * Tools exposed to AIP Logic flows (aip-logic/*.yaml). Every tool returns validated,
 * structured data; the LLM never writes to the ontology directly.
 */
import { Function, Integer } from "@foundry/functions-api";
import { Objects } from "@foundry/ontology-api";

import { evaluatePatient, validateCriteria } from "../logic";
import { toPatientFeatures } from "./mappers";

export interface CriteriaCheck {
  valid: boolean;
  errors: string[];
  normalizedCriteriaJson: string;
}

export class AipTools {
  /** Validate criteria proposed by the "criteria from text" flow before showing them to the user. */
  @Function()
  public validateProposedCriteria(criteriaJson: string): CriteriaCheck {
    let parsed: unknown;
    try {
      parsed = JSON.parse(criteriaJson);
    } catch {
      return { valid: false, errors: ["not valid JSON"], normalizedCriteriaJson: "[]" };
    }
    const { criteria, errors } = validateCriteria(parsed);
    return { valid: errors.length === 0, errors, normalizedCriteriaJson: JSON.stringify(criteria) };
  }

  /** Vocabulary the flow may use, read from the ontology (Biomarker catalogue). */
  @Function()
  public async availableBiomarkers(): Promise<string[]> {
    const biomarkers = await Objects.search().biomarker().allAsync();
    return biomarkers.map((b) => `${b.analyte}: ${b.displayName} (${b.unit}, ${b.matrix})`);
  }

  /** Count only - the flow never receives patient-level data. */
  @Function()
  public async countMatchingPatients(criteriaJson: string): Promise<Integer> {
    const { criteria, errors } = validateCriteria(JSON.parse(criteriaJson));
    if (errors.length > 0) return -1;
    const patients = await Objects.search().patient().filter((p) => p.eligibleForResearch.isTrue()).allAsync();
    return patients.filter((p) => evaluatePatient(toPatientFeatures(p), criteria).included).length;
  }
}
