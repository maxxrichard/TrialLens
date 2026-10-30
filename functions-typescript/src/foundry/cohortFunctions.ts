/**
 * Cohort Builder functions. Backed actions: createCohort, addPatientsToCohort,
 * removePatientFromCohort (see ontology/action_types.yaml).
 */
import { Edits, Function, Integer, OntologyEditFunction, Timestamp, Users, Uuid } from "@foundry/functions-api";
import { Cohort, CohortCriterion, CohortMembership, Objects, Patient, Study } from "@foundry/ontology-api";

import {
  attritionFunnel,
  CohortSummary,
  describeCriterion,
  evaluatePatient,
  FunnelStep,
  summarizeCohort,
  validateCriteria,
} from "../logic";
import { toPatientFeatures } from "./mappers";

function parseCriteria(criteriaJson: string) {
  const { criteria, errors } = validateCriteria(JSON.parse(criteriaJson));
  if (errors.length > 0) {
    throw new Error(`Invalid cohort criteria: ${errors.join("; ")}`);
  }
  return criteria;
}

async function eligiblePatients(): Promise<Patient[]> {
  return Objects.search().patient().filter((p) => p.eligibleForResearch.isTrue()).allAsync();
}

export class CohortFunctions {
  /** Live preview in the Cohort Builder: number of patients matching the criteria. */
  @Function()
  public async previewCohortSize(criteriaJson: string): Promise<Integer> {
    const criteria = parseCriteria(criteriaJson);
    const patients = await eligiblePatients();
    return patients.filter((p) => evaluatePatient(toPatientFeatures(p), criteria).included).length;
  }

  /** Attrition funnel (one bar per criterion) for the Cohort Builder chart. */
  @Function()
  public async cohortFunnel(criteriaJson: string): Promise<FunnelStep[]> {
    const criteria = parseCriteria(criteriaJson);
    const patients = await Objects.search().patient().allAsync();
    return attritionFunnel(patients.map(toPatientFeatures), criteria);
  }

  /** Summary card for a cohort (demographics, amyloid status, data availability). */
  @Function()
  public async cohortSummary(cohort: Cohort): Promise<CohortSummary> {
    const memberships = await cohort.cohortMemberships.allAsync();
    const patients = await Promise.all(memberships.map((m) => m.patient.getAsync()));
    return summarizeCohort(patients.filter((p): p is Patient => p !== undefined).map(toPatientFeatures));
  }

  @Edits(Cohort, CohortCriterion, CohortMembership)
  @OntologyEditFunction()
  public async createCohortFromCriteria(
    name: string,
    criteriaJson: string,
    description?: string,
    study?: Study,
  ): Promise<void> {
    const criteria = parseCriteria(criteriaJson);
    const now = Timestamp.now();
    const user = Users.getCurrentUser().username;

    const cohort = Objects.create().cohort(Uuid.random());
    cohort.name = name;
    cohort.description = description ?? "";
    cohort.studyCode = study?.studyCode;
    cohort.owner = user;
    cohort.status = "DRAFT";
    cohort.criteriaJson = JSON.stringify(criteria);
    cohort.createdTs = now;

    criteria.forEach((criterion) => {
      const row = Objects.create().cohortCriterion(Uuid.random());
      row.cohortId = cohort.cohortId;
      row.criterionType = criterion.type;
      row.criterionJson = JSON.stringify(criterion);
      row.isExclusion = criterion.exclude === true;
      row.createdTs = now;
    });

    let members = 0;
    for (const patient of await eligiblePatients()) {
      const evaluation = evaluatePatient(toPatientFeatures(patient), criteria);
      if (!evaluation.included) continue;
      const membership = Objects.create().cohortMembership(Uuid.random());
      membership.cohortId = cohort.cohortId;
      membership.patientId = patient.patientId;
      membership.addedTs = now;
      membership.addedBy = user;
      membership.inclusionReason = criteria.map(describeCriterion).join(" AND ") || "all eligible patients";
      members += 1;
    }
    cohort.nPatients = members;
  }

  @Edits(Cohort, CohortMembership)
  @OntologyEditFunction()
  public async addPatientsToCohort(cohort: Cohort, patients: Patient[], inclusionReason: string): Promise<void> {
    if (cohort.status !== "DRAFT") {
      throw new Error("Locked cohorts cannot be changed.");
    }
    const existing = new Set((await cohort.cohortMemberships.allAsync()).map((m) => m.patientId));
    const user = Users.getCurrentUser().username;
    let added = 0;
    for (const patient of patients) {
      if (existing.has(patient.patientId)) continue;
      if (!toPatientFeatures(patient).eligibleForResearch) {
        throw new Error(`Patient ${patient.patientId} is not eligible for research use.`);
      }
      const membership = Objects.create().cohortMembership(Uuid.random());
      membership.cohortId = cohort.cohortId;
      membership.patientId = patient.patientId;
      membership.addedTs = Timestamp.now();
      membership.addedBy = user;
      membership.inclusionReason = `manual: ${inclusionReason}`;
      added += 1;
    }
    cohort.nPatients = (cohort.nPatients ?? 0) + added;
  }

  @Edits(Cohort, CohortMembership)
  @OntologyEditFunction()
  public async removePatientFromCohort(membership: CohortMembership): Promise<void> {
    const cohort = await membership.cohort.getAsync();
    if (cohort === undefined || cohort.status !== "DRAFT") {
      throw new Error("Only memberships of draft cohorts can be removed.");
    }
    membership.delete();
    cohort.nPatients = Math.max(0, (cohort.nPatients ?? 1) - 1);
  }
}
