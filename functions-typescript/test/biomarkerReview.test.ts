import { relativeChange, reviewQueue, suggestReview } from "../src/logic";
import { measurement } from "./fixtures";

describe("suggestReview", () => {
  it("accepts an unremarkable measurement", () => {
    const s = suggestReview(measurement(), []);
    expect(s.suggestedDecision).toBe("ACCEPTED");
    expect(s.flags).toEqual([]);
    expect(s.rationale).toBe("no issues detected");
  });

  it("requests a repeat on QC failure or above ULOQ", () => {
    expect(suggestReview(measurement({ qcStatus: "FAIL" }), []).suggestedDecision).toBe("REPEAT_REQUESTED");
    const uloq = suggestReview(measurement({ aboveUloq: true }), []);
    expect(uloq.suggestedDecision).toBe("REPEAT_REQUESTED");
    expect(uloq.rationale).toContain("dilution");
  });

  it("compares with the previous valid measurement only", () => {
    const history = [
      measurement({ measurementId: "m1", measuredDate: "2023-01-01", value: 10 }),
      measurement({ measurementId: "m2", measuredDate: "2023-06-01", value: 100, qcStatus: "FAIL" }),
      measurement({ measurementId: "m3", measuredDate: "2025-01-01", value: 11 }), // later, ignored
    ];
    const s = suggestReview(measurement({ value: 16, measuredDate: "2024-01-01" }), history);
    expect(s.previousValue).toBe(10);
    expect(s.relativeChange).toBeCloseTo(0.6);
    expect(s.flags).toContain("LARGE_CHANGE_FROM_PREVIOUS");
    expect(s.suggestedDecision).toBe("ACCEPTED");
  });

  it("requests a repeat when a QC warning coincides with a large change", () => {
    const history = [measurement({ measurementId: "m1", measuredDate: "2023-01-01", value: 10 })];
    const s = suggestReview(measurement({ value: 30, qcStatus: "WARN" }), history);
    expect(s.suggestedDecision).toBe("REPEAT_REQUESTED");
  });

  it("reports values below LLOQ as censored", () => {
    const s = suggestReview(measurement({ belowLloq: true }), []);
    expect(s.flags).toEqual(["BELOW_LLOQ"]);
    expect(s.rationale).toBe("report as <LLOQ");
  });
});

describe("relativeChange", () => {
  it("handles zero baselines", () => {
    expect(relativeChange(0, 0)).toBe(0);
    expect(relativeChange(0, 1)).toBe(Number.POSITIVE_INFINITY);
    expect(relativeChange(20, 10)).toBe(0.5);
  });
});

describe("reviewQueue", () => {
  it("puts repeats first, then flagged results, then the rest", () => {
    const queue = reviewQueue([
      measurement({ measurementId: "clean", analyte: "GFAP" }),
      measurement({ measurementId: "flagged", analyte: "PTAU217", isAbnormal: true }),
      measurement({ measurementId: "repeat", analyte: "NFL", qcStatus: "FAIL" }),
    ]);
    expect(queue.map((s) => s.measurementId)).toEqual(["repeat", "flagged", "clean"]);
  });
});
