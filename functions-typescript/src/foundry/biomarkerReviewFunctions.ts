/**
 * Biomarker Review app functions. Backed action: reviewBiomarkerMeasurement.
 */
import { Edits, Function, OntologyEditFunction, Timestamp, Users, Uuid } from "@foundry/functions-api";
import { BiomarkerMeasurement, BiomarkerReview, Objects } from "@foundry/ontology-api";

import { ReviewSuggestion, reviewQueue, suggestReview } from "../logic";
import { toMeasurement } from "./mappers";

const DECISIONS = ["ACCEPTED", "EXCLUDED", "REPEAT_REQUESTED"];

async function patientHistory(measurement: BiomarkerMeasurement) {
  const history = await Objects.search()
    .biomarkerMeasurement()
    .filter((m) => m.patientId.exactMatch(measurement.patientId ?? ""))
    .filter((m) => m.analyte.exactMatch(measurement.analyte ?? ""))
    .allAsync();
  return history.map(toMeasurement);
}

export class BiomarkerReviewFunctions {
  /** Suggested decision and flags shown next to a measurement in the review panel. */
  @Function()
  public async suggestBiomarkerReview(measurement: BiomarkerMeasurement): Promise<ReviewSuggestion> {
    return suggestReview(toMeasurement(measurement), await patientHistory(measurement));
  }

  /** Ordered review queue for an assay run (repeats first). */
  @Function()
  public async assayRunReviewQueue(runId: string): Promise<ReviewSuggestion[]> {
    const measurements = await Objects.search()
      .biomarkerMeasurement()
      .filter((m) => m.runId.exactMatch(runId))
      .allAsync();
    return reviewQueue(measurements.map(toMeasurement));
  }

  @Edits(BiomarkerReview)
  @OntologyEditFunction()
  public async reviewBiomarkerMeasurement(
    measurement: BiomarkerMeasurement,
    decision: string,
    reason: string,
    comment?: string,
  ): Promise<void> {
    if (!DECISIONS.includes(decision)) {
      throw new Error(`Unknown decision ${decision}`);
    }
    if (decision === "EXCLUDED" && !comment) {
      throw new Error("Exclusions require a comment.");
    }
    const review = Objects.create().biomarkerReview(Uuid.random());
    review.measurementId = measurement.measurementId;
    review.patientId = measurement.patientId;
    review.decision = decision;
    review.reason = reason;
    review.reviewer = Users.getCurrentUser().username;
    review.reviewedTs = Timestamp.now();
    review.reviewComment = comment ?? "";
  }
}
