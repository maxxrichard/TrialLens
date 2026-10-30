import { DataQualityIssueView, isOverdue, median, priorityScore, summarizeCohort, suppressSmallCells, triage } from "../src/logic";
import { patient } from "./fixtures";

describe("summarizeCohort", () => {
  it("summarises demographics, biomarkers and data availability", () => {
    const summary = summarizeCohort([
      patient({ patientId: "a", ageYears: 70, latestMmse: 26 }),
      patient({ patientId: "b", ageYears: 74, sex: "M", amyloidStatus: "NEGATIVE", apoeE4Carrier: false, latestMmse: 28 }),
      patient({ patientId: "c", ageYears: null, amyloidStatus: "UNKNOWN", consentGenetics: false, latestMmse: null }),
    ]);
    expect(summary.nPatients).toBe(3);
    expect(summary.medianAge).toBe(72);
    expect(summary.shareFemale).toBeCloseTo(0.667);
    expect(summary.shareAmyloidPositive).toBe(0.5);
    expect(summary.shareApoeE4Carrier).toBe(0.5); // c has no genetics consent and is not counted
    expect(summary.medianMmse).toBe(27);
    expect(summary.dataAvailability.genetics).toBe(2);
    expect(summary.diagnosisCounts).toEqual({ MCI: 3 });
  });

  it("handles empty cohorts", () => {
    const summary = summarizeCohort([]);
    expect(summary.medianAge).toBeNull();
    expect(summary.shareFemale).toBeNull();
  });
});

describe("helpers", () => {
  it("computes medians", () => {
    expect(median([3, 1, 2])).toBe(2);
    expect(median([4, 1, 2, 3])).toBe(2.5);
    expect(median([])).toBeNull();
  });

  it("suppresses small cells", () => {
    expect(suppressSmallCells({ a: 0, b: 3, c: 5 })).toEqual({ a: 0, b: null, c: 5 });
  });
});

describe("data-quality triage", () => {
  const today = new Date("2026-03-10T12:00:00Z");
  const issue = (overrides: Partial<DataQualityIssueView>): DataQualityIssueView => ({
    issueId: "i",
    ruleCode: "BIOMARKER_QC_FAIL",
    severity: "HIGH",
    status: "OPEN",
    detectedDate: "2026-03-08",
    patientId: "p1",
    ...overrides,
  });

  it("flags issues past their SLA", () => {
    expect(isOverdue(issue({ severity: "CRITICAL", detectedDate: "2026-03-01" }), today)).toBe(true);
    expect(isOverdue(issue({ severity: "LOW", detectedDate: "2026-03-01" }), today)).toBe(false);
    expect(isOverdue(issue({ severity: "CRITICAL", detectedDate: "2026-03-01", status: "RESOLVED" }), today)).toBe(false);
  });

  it("prioritises severity, SLA pressure and locked cohorts", () => {
    const locked = new Set(["p-locked"]);
    expect(priorityScore(issue({ status: "DISMISSED" }), today)).toBe(0);
    expect(priorityScore(issue({ patientId: "p-locked" }), today, locked)).toBeGreaterThan(priorityScore(issue({}), today, locked));
    const ordered = triage(
      [
        issue({ issueId: "low", severity: "LOW" }),
        issue({ issueId: "critical", severity: "CRITICAL" }),
        issue({ issueId: "done", status: "RESOLVED" }),
        issue({ issueId: "medium", severity: "MEDIUM" }),
      ],
      today,
    );
    expect(ordered.map((i) => i.issueId)).toEqual(["critical", "medium", "low"]);
  });
});
