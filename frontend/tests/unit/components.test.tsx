import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { HBarList } from "@/components/charts/charts";
import { DecisionForm } from "@/components/report/DecisionForm";
import { EvidenceText } from "@/components/report/EvidenceText";
import { ControlAnswerBadge, SifBadge, TrendBadge } from "@/components/ui/badges";
import type { EntityOut } from "@/lib/types";

describe("badges", () => {
  it("labels SIF signals and trends in text, not colour alone", () => {
    render(<SifBadge signal="SIF_POTENTIAL" />);
    expect(screen.getByText("SIF POTENTIAL")).toBeInTheDocument();
    render(<TrendBadge trend="INSUFFICIENT_HISTORY" />);
    expect(screen.getByText("Insufficient history")).toBeInTheDocument();
    render(<ControlAnswerBadge answer="INSUFFICIENT" />);
    expect(screen.getByText("Insufficient info")).toBeInTheDocument();
  });
});

describe("EvidenceText", () => {
  it("highlights evidence spans with accessible labels", () => {
    const text = "Residual pressure was observed.";
    const ents: EntityOut[] = [
      { entity_type: "energy_source", value: "Residual pressure", canonical: "residual pressure", polarity: "present", confidence: 0.94, source: "description", evidence: [{ text: "Residual pressure", start: 0, end: 17, confidence: 0.94, source: "description" }] },
    ];
    const { container } = render(<EvidenceText text={text} entities={ents} />);
    const mark = container.querySelector("mark");
    expect(mark?.textContent).toBe("Residual pressure");
    expect(mark?.getAttribute("aria-label")).toContain("Energy source: residual pressure");
    expect(container.textContent).toBe(text);
  });
});

describe("HBarList", () => {
  it("shows values as text and an empty state", () => {
    render(<HBarList valueLabel="Reports" partLabel="SIF signal" rows={[{ key: "a", label: "Hot work", value: 14, part: 13 }]} />);
    expect(screen.getByText("Hot work")).toBeInTheDocument();
    expect(screen.getByText("13")).toBeInTheDocument();
    render(<HBarList valueLabel="Reports" rows={[]} emptyText="No SIF signals" />);
    expect(screen.getByText("No SIF signals")).toBeInTheDocument();
  });
});

describe("DecisionForm", () => {
  const current = { scl_class: "EXPOSURE", sif_potential: true, primary_lsr: "ENERGY_ISOLATION" };

  it("submits a confirm decision", () => {
    const onSubmit = vi.fn();
    render(<DecisionForm idPrefix="t1" current={current} onSubmit={onSubmit} />);
    fireEvent.click(screen.getByRole("button", { name: /record decision/i }));
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ action: "CONFIRM" }));
  });

  it("requires a reason and a change before a CHANGE decision can be submitted", () => {
    const onSubmit = vi.fn();
    render(<DecisionForm idPrefix="t2" current={current} onSubmit={onSubmit} />);
    fireEvent.click(screen.getByLabelText("Change"));
    const btn = screen.getByRole("button", { name: /record decision/i });
    expect(btn).toBeDisabled();
    fireEvent.change(screen.getByLabelText("SCL class"), { target: { value: "SUCCESS" } });
    expect(btn).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Reason \(required\)/), { target: { value: "Barricade was in place" } });
    expect(btn).not.toBeDisabled();
    fireEvent.click(btn);
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ action: "CHANGE", scl_class: "SUCCESS", reason: "Barricade was in place" }));
  });
});
