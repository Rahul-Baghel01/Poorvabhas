"use client";

import { ArrowRight, Network } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { AnswerBadge, ControlAnswerBadge, SifBadge } from "@/components/ui/badges";
import { Quote } from "@/components/report/EvidenceText";
import type { Analysis, Evidence, Gate, ReportDetail } from "@/lib/types";
import { SCL_META } from "@/lib/format";

type Row = {
  key: string;
  dimension: string;
  points: number;
  max: number;
  check: React.ReactNode;
  finding: string;
  support: Evidence[];
  crossReport?: React.ReactNode;
};

const field = (text: string): Evidence => ({ text, start: null, end: null, confidence: 1, source: "structured_field" });

/** Evidence for each aggravating-context factor, mirroring the engine's rules in nlp/scoring.py (compute_priority). */
function contextEvidence(factor: string, a: Analysis, r: ReportDetail["report"]): Evidence[] {
  const spans = (type: string, canon: string[]) => a.entities.filter((e) => e.entity_type === type && canon.includes(e.canonical ?? "")).flatMap((e) => e.evidence);
  switch (factor) {
    case "contractor workforce":
      return r.contractor ? [field(`Contractor: ${r.contractor}`)] : [];
    case "night / low light":
      return [...(String(r.shift).toLowerCase() === "night" ? [field(`Shift: ${r.shift}`)] : []), ...spans("environmental_context", ["night / low light"])];
    case "adverse weather":
      return [...(r.weather ? [field(`Weather: ${r.weather}`)] : []), ...spans("environmental_context", ["adverse weather"])];
    case "SIMOPS":
      return spans("environmental_context", ["simultaneous operations"]);
    case "multiple energy sources":
      return a.entities.filter((e) => e.entity_type === "energy_source").flatMap((e) => e.evidence);
    case "person in line of fire":
      return spans("human_behavior", ["entered danger zone", "pedestrian exposure"]);
    default:
      return [];
  }
}

function gateCheck(g: Gate | undefined, label: string) {
  if (!g) return <span className="text-muted">{label} — not evaluated</span>;
  const Answer = g.key === "direct_control" ? ControlAnswerBadge : AnswerBadge;
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <span>{label}</span>
      <Answer answer={g.answer} />
    </span>
  );
}

function dedupe(evidence: Evidence[]): Evidence[] {
  const seen = new Set<string>();
  return evidence.filter((e) => e.text && !seen.has(e.text) && seen.add(e.text));
}

/** Priority → evidence dimension → triggered check → finding → supporting report text, built only from stored analysis output. */
function buildRows(a: Analysis, r: ReportDetail["report"], patterns: ReportDetail["patterns"]): Row[] {
  const gate = (k: Gate["key"]) => a.scl.gates.find((g) => g.key === k);
  const rows: Row[] = [];
  for (const p of a.priority_breakdown) {
    if (p.points <= 0) continue;
    const base = { key: p.key, dimension: p.label, points: p.points, max: p.max };
    if (p.key === "energy_exposure") {
      const g = gate("high_energy");
      rows.push({ ...base, check: gateCheck(g, "Q1 · High energy present?"), finding: g?.rationale || p.rationale, support: dedupe(g?.evidence ?? []) });
    } else if (p.key === "barrier_failure") {
      const g = gate("direct_control");
      rows.push({ ...base, check: gateCheck(g, "Q3 · Direct control in place?"), finding: g?.rationale || p.rationale, support: dedupe(g?.evidence ?? []) });
    } else if (p.key === "precursor_severity") {
      const onPath = a.scl.gates.filter((g) => g.used_in_path);
      rows.push({
        ...base,
        check: (
          <span className="inline-flex flex-wrap items-center gap-1.5">
            <span>SCL class {SCL_META[a.scl.scl_class]?.label ?? a.scl.scl_class}</span>
            <SifBadge signal={a.scl.sif_signal} />
          </span>
        ),
        finding: a.scl.scl_description,
        support: dedupe(onPath.flatMap((g) => g.evidence)).slice(0, 3),
      });
    } else if (p.key === "recurrence") {
      rows.push({
        ...base,
        check: <span>Pattern check · similar precursor reports (90 days)</span>,
        finding: p.rationale,
        support: [],
        crossReport: patterns.length ? (
          <span className="flex flex-col gap-1">
            {patterns.map((pt) => (
              <Link key={pt.id} href={`/patterns/${pt.id}`} className="inline-flex items-center gap-1.5 text-cyan hover:underline">
                <Network className="size-3.5 shrink-0" aria-hidden /> {pt.code} {pt.name} · {pt.occurrences} reports
              </Link>
            ))}
          </span>
        ) : (
          <span className="text-muted">Cross-report evidence (similar earlier reports), not a sentence in this report.</span>
        ),
      });
    } else if (p.key === "exposure_context") {
      const factors = p.rationale.split(", ").filter(Boolean);
      rows.push({ ...base, check: <span>Aggravating exposure context</span>, finding: p.rationale, support: dedupe(factors.flatMap((f) => contextEvidence(f, a, r))).slice(0, 4) });
    } else {
      rows.push({ ...base, check: <span>{p.label}</span>, finding: p.rationale, support: [] });
    }
  }
  return rows;
}

export function WhyTrail({ analysis, report, patterns }: { analysis: Analysis; report: ReportDetail["report"]; patterns: ReportDetail["patterns"] }) {
  const rows = buildRows(analysis, report, patterns);
  if (!rows.length) return <p className="text-[12.5px] text-muted">No priority factor was triggered for this report.</p>;
  return (
    <ol className="flex flex-col gap-3" aria-label="Why trail">
      {rows.map((row) => (
        <li key={row.key} className="rounded-sm border border-border bg-bg/50 p-3">
          <div className="flex items-center justify-between gap-2">
            <p className="label-tech !text-fg">{row.dimension}</p>
            <a href="#priority" className="num font-mono text-[12px] text-fg-2 hover:text-fg" title="Contribution to the priority score">
              +{row.points.toFixed(1)}
              <span className="text-muted">/{row.max}</span>
            </a>
          </div>
          <dl className="mt-2 grid gap-2 text-[12.5px] md:grid-cols-[minmax(0,1fr)_14px_minmax(0,1fr)_14px_minmax(0,1.3fr)]">
            <div>
              <dt className="font-mono text-[9.5px] uppercase tracking-wider text-muted">Triggered check</dt>
              <dd className="mt-1 text-fg">
                <a href="#scl" className="hover:underline">
                  {row.check}
                </a>
              </dd>
            </div>
            <ArrowRight className="mt-5 hidden size-3.5 text-muted md:block" aria-hidden />
            <div>
              <dt className="font-mono text-[9.5px] uppercase tracking-wider text-muted">Finding</dt>
              <dd className="mt-1 text-fg-2">{row.finding}</dd>
            </div>
            <ArrowRight className="mt-5 hidden size-3.5 text-muted md:block" aria-hidden />
            <div>
              <dt className="font-mono text-[9.5px] uppercase tracking-wider text-muted">Supporting report text</dt>
              <dd className="mt-1 flex flex-col gap-1">
                {row.crossReport ??
                  (row.support.length ? (
                    row.support.map((e, i) => (
                      <a key={i} href="#orig" className="hover:underline" title="Show in the original report">
                        <Quote text={e.text} source={e.source} />
                      </a>
                    ))
                  ) : (
                    <span className="text-amber">Not stated in the report</span>
                  ))}
              </dd>
            </div>
          </dl>
        </li>
      ))}
    </ol>
  );
}
