/**
 * Data-quality dashboard functions. Backed action: updateDataQualityIssue.
 */
import { Edits, Function, Integer, OntologyEditFunction } from "@foundry/functions-api";
import { DataQualityIssue, Objects } from "@foundry/ontology-api";

import { priorityScore, triage } from "../logic";
import { toIssueView } from "./mappers";

const STATUSES = ["OPEN", "IN_PROGRESS", "RESOLVED", "DISMISSED"];

async function patientsInLockedCohorts(): Promise<Set<string>> {
  const locked = await Objects.search().cohort().filter((c) => c.status.exactMatch("LOCKED")).allAsync();
  const memberships = await Promise.all(locked.map((c) => c.cohortMemberships.allAsync()));
  return new Set(memberships.flat().map((m) => m.patientId ?? ""));
}

export class DataQualityFunctions {
  /** Priority score column in the issue table. */
  @Function()
  public async issuePriority(issue: DataQualityIssue): Promise<Integer> {
    return priorityScore(toIssueView(issue), new Date(), await patientsInLockedCohorts());
  }

  /** Issue ids in triage order for the "My queue" tab. */
  @Function()
  public async triagedIssueIds(): Promise<string[]> {
    const open = await Objects.search()
      .dataQualityIssue()
      .filter((i) => i.status.exactMatch("OPEN", "IN_PROGRESS"))
      .allAsync();
    return triage(open.map(toIssueView), new Date(), await patientsInLockedCohorts()).map((i) => i.issueId);
  }

  @Edits(DataQualityIssue)
  @OntologyEditFunction()
  public async updateDataQualityIssue(
    issue: DataQualityIssue,
    status: string,
    assignee?: string,
    resolutionNote?: string,
  ): Promise<void> {
    if (!STATUSES.includes(status)) {
      throw new Error(`Unknown status ${status}`);
    }
    if ((status === "RESOLVED" || status === "DISMISSED") && !resolutionNote) {
      throw new Error("Resolving or dismissing an issue requires a resolution note.");
    }
    issue.status = status;
    if (assignee !== undefined) issue.assignee = assignee;
    if (resolutionNote !== undefined) issue.resolutionNote = resolutionNote;
  }
}
