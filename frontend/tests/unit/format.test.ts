import { describe, expect, it } from "vitest";

import { confidenceLevel, pct, segmentText } from "@/lib/format";

describe("segmentText", () => {
  it("splits text around evidence spans without losing characters", () => {
    const text = "During pump maintenance, isolation was not verified.";
    const segs = segmentText(text, [
      { start: 7, end: 23, tone: "green", label: "activity" },
      { start: 25, end: 51, tone: "amber", label: "failure" },
    ]);
    expect(segs.map((s) => s.text).join("")).toBe(text);
    expect(segs.filter((s) => s.span).map((s) => s.text)).toEqual(["pump maintenance", "isolation was not verified"]);
  });

  it("drops overlapping and out-of-range spans instead of corrupting text", () => {
    const text = "Residual pressure was observed";
    const segs = segmentText(text, [
      { start: 0, end: 17, tone: "red", label: "energy" },
      { start: 9, end: 17, tone: "red", label: "overlap" },
      { start: 50, end: 60, tone: "red", label: "bad" },
    ]);
    expect(segs.map((s) => s.text).join("")).toBe(text);
    expect(segs.filter((s) => s.span)).toHaveLength(1);
  });
});

describe("formatting", () => {
  it("formats percentages and handles missing values", () => {
    expect(pct(0.5)).toBe("50%");
    expect(pct(null)).toBe("—");
  });
  it("maps confidence to levels", () => {
    expect(confidenceLevel(0.9)).toBe("HIGH");
    expect(confidenceLevel(0.6)).toBe("MEDIUM");
    expect(confidenceLevel(0.3)).toBe("LOW");
    expect(confidenceLevel(undefined)).toBeNull();
  });
});
