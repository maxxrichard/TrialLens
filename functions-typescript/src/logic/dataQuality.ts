import { DataQualityIssueView, Severity } from "./types";

/** Service levels per severity, in days from detection to resolution. */
export const SLA_DAYS: Record<Severity, number> = { CRITICAL: 2, HIGH: 5, MEDIUM: 14, LOW: 30 };

const SEVERITY_WEIGHT: Record<Severity, number> = { CRITICAL: 100, HIGH: 60, MEDIUM: 30, LOW: 10 };

const DAY_MS = 24 * 60 * 60 * 1000;

export function ageInDays(detectedDate: string, today: Date): number {
  const detected = Date.parse(`${detectedDate}T00:00:00Z`);
  const now = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate());
  return Math.max(0, Math.floor((now - detected) / DAY_MS));
}

export function isOverdue(issue: DataQualityIssueView, today: Date): boolean {
  const open = issue.status === "OPEN" || issue.status === "IN_PROGRESS";
  return open && ageInDays(issue.detectedDate, today) > SLA_DAYS[issue.severity];
}

/**
 * Triage priority for the data-quality dashboard: severity first, then age relative to
 * the SLA. Issues touching patients in a locked cohort get a boost because they may
 * affect an analysis that is already running.
 */
export function priorityScore(issue: DataQualityIssueView, today: Date, patientsInLockedCohorts: Set<string> = new Set()): number {
  if (issue.status === "RESOLVED" || issue.status === "DISMISSED") return 0;
  const age = ageInDays(issue.detectedDate, today);
  const slaPressure = Math.min(1.5, age / SLA_DAYS[issue.severity]) * 20;
  const lockedBoost = issue.patientId !== null && patientsInLockedCohorts.has(issue.patientId) ? 25 : 0;
  return Math.round(SEVERITY_WEIGHT[issue.severity] + slaPressure + lockedBoost);
}

export function triage(
  issues: DataQualityIssueView[],
  today: Date,
  patientsInLockedCohorts: Set<string> = new Set(),
): Array<DataQualityIssueView & { priority: number; overdue: boolean }> {
  return issues
    .map((issue) => ({
      ...issue,
      priority: priorityScore(issue, today, patientsInLockedCohorts),
      overdue: isOverdue(issue, today),
    }))
    .filter((issue) => issue.priority > 0)
    .sort((a, b) => b.priority - a.priority || a.detectedDate.localeCompare(b.detectedDate));
}
