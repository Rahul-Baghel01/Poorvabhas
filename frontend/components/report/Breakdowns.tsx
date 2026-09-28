"use client";

import { Info } from "lucide-react";

import { LSR_ICON, LsrTag } from "@/components/ui/badges";
import { Badge, Meter } from "@/components/ui/primitives";
import { Quote } from "@/components/report/EvidenceText";
import type { Analysis, ReportDetail } from "@/lib/types";
import { ENTITY_LABELS, cn } from "@/lib/format";

const PRIORITY_COLORS: Record<string, string> = {
  energy_exposure: "#FF4A43",
  barrier_failure: "#F2B233",
  precursor_severity: "#C9362D",
  recurrence: "#27C7C9",
  exposure_context: "#8a9597",
};

export function PriorityBreakdown({ analysis }: { analysis: Analysis }) {
  const parts = analysis.priority_breakdown;
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-end justify-between">
        <p className="num font-mono text-[34px] font-semibold leading-none text-fg">
          {Math.round(analysis.priority_score)}
          <span className="text-[14px] text-muted"> / 100</span>
        </p>
        <Badge tone={analysis.priority_level === "LOW" ? "neutral" : analysis.priority_level === "MEDIUM" ? "amber" : "red"}>{analysis.priority_level}</Badge>
      </div>
      <div className="flex h-2.5 gap-[2px] overflow-hidden rounded-[2px] bg-surface-3" role="img" aria-label={`Priority ${Math.round(analysis.priority_score)} of 100`}>
        {parts.map((p) => (p.points > 0 ? <div key={p.key} style={{ width: `${p.points}%`, background: PRIORITY_COLORS[p.key] }} title={`${p.label}: +${p.points}`} /> : null))}
      </div>
      <ul className="flex flex-col gap-2">
        {parts.map((p) => (
          <li key={p.key} className="grid grid-cols-[10px_1fr_auto] items-start gap-2">
            <span className="mt-1.5 size-2 rounded-[2px]" style={{ background: PRIORITY_COLORS[p.key] }} aria-hidden />
            <span>
              <span className="block text-[12.5px] text-fg">{p.label}</span>
              <span className="block text-[11.5px] leading-snug text-muted">{p.rationale}</span>
            </span>
            <span className="num font-mono text-[12.5px] text-fg">
              +{p.points.toFixed(1)}
              <span className="text-muted">/{p.max}</span>
            </span>
          </li>
        ))}
      </ul>
      <p className="text-[11px] text-muted">
        Priority ranks where to look first; it is a separate output from the SIF classification. It combines SIF-potential (precursor severity), energy exposure, control status, recurrence and context. Transparent additive model; weights in Settings → Priority scoring model.
      </p>
    </div>
  );
}

export function ConfidenceBreakdown({ analysis }: { analysis: Analysis }) {
  const b = analysis.confidence_breakdown;
  const tone = analysis.confidence_level === "HIGH" ? "green" : analysis.confidence_level === "MEDIUM" ? "amber" : "red";
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-end justify-between">
        <p className="num font-mono text-[34px] font-semibold leading-none text-fg">{analysis.confidence.toFixed(2)}</p>
        <Badge tone={tone}>{analysis.confidence_level}</Badge>
      </div>
      <p className="text-[11.5px] text-muted">How certain the engine is about the evidence it extracted and classified. Whether the report contains enough evidence is shown separately as Evidence coverage; the score applies it as one weighted component.</p>
      <ul className="flex flex-col gap-2.5">
        {b.components.map((c) => (
          <li key={c.key}>
            <div className="flex items-center justify-between text-[12.5px]">
              <span className="text-fg">
                {c.key === "completeness" ? "Coverage component" : c.label} <span className="text-muted">×{c.weight}</span>
              </span>
              <span className="num font-mono text-fg-2">{c.value.toFixed(2)}</span>
            </div>
            <Meter value={c.value} tone={c.value >= 0.75 ? "green" : c.value >= 0.55 ? "amber" : "red"} label={c.label} className="mt-1" />
            <p className="mt-1 text-[11px] text-muted">{c.explanation}</p>
          </li>
        ))}
      </ul>
      <div className="rounded-sm border border-border bg-bg/50 p-2.5 text-[12px] text-fg-2">
        <p className="label-tech mb-1">Classifier second opinion</p>
        {analysis.ml_probability !== null ? (
          <>
            <p>
              P(SIF-potential) = <span className="num font-mono text-fg">{analysis.ml_probability.toFixed(2)}</span>{" "}
              <span className="text-muted">({analysis.ml_model_version})</span>
            </p>
            {b.ml_agreement !== null ? <p className="mt-0.5">Agreement with SCL engine: {b.ml_agreement.toFixed(2)}</p> : null}
            {analysis.ml_explanation.length ? (
              <p className="mt-1.5 flex flex-wrap gap-1">
                {analysis.ml_explanation.slice(0, 6).map((t) => (
                  <span key={t.term} className={cn("rounded-xs border px-1 font-mono text-[10.5px]", t.weight > 0 ? "border-red/30 text-[#ff8a80]" : "border-green/30 text-green")} title={`weight ${t.weight}`}>
                    {t.term}
                  </span>
                ))}
              </p>
            ) : null}
          </>
        ) : (
          <p>Classifier unavailable — deterministic engine only.</p>
        )}
        {b.penalty_reasons.length ? <p className="mt-1.5 text-amber">Penalty ×{b.penalty}: {b.penalty_reasons.join(", ")}</p> : null}
      </div>
    </div>
  );
}

export function MappingPanel({ analysis }: { analysis: Analysis }) {
  const m = analysis.mapping;
  const Icon = LSR_ICON[m.primary.code];
  const evidence = m.primary.evidence.filter((e) => e.text || e.term);
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start gap-3 rounded-sm border border-cyan/40 bg-cyan/[0.06] p-3.5">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-sm border border-cyan/40 bg-bg">{Icon ? <Icon className="size-5 text-cyan" aria-hidden /> : null}</span>
        <div className="min-w-0 flex-1">
          <p className="label-tech">Suggested LSR — proposed crosswalk</p>
          <p className="mt-0.5 text-[17px] font-semibold text-fg">{m.primary.name}</p>
          <p className="num mt-0.5 font-mono text-[11.5px] text-fg-2">
            mapping confidence {m.confidence.toFixed(2)} · score {m.primary.score.toFixed(1)}
          </p>
        </div>
      </div>
      {m.secondary.length ? (
        <div>
          <p className="label-tech mb-1.5">Secondary rules</p>
          <ul className="flex flex-col gap-1.5">
            {m.secondary.map((s) => (
              <li key={s.code} className="flex items-center justify-between">
                <LsrTag code={s.code} name={s.name} />
                <span className="num font-mono text-[11.5px] text-muted">score {s.score.toFixed(1)}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <div>
        <p className="label-tech mb-1.5">Mapping evidence</p>
        {evidence.length ? (
          <ul className="flex flex-wrap gap-1.5">
            {evidence.slice(0, 10).map((e, i) => (
              <li key={i} className="rounded-xs border border-border bg-bg px-1.5 py-0.5 text-[11.5px] text-fg-2" title={e.kind}>
                <span className="mr-1 font-mono text-[9.5px] uppercase text-muted">{e.kind}</span>
                {e.kind === "signal" ? e.term : e.text || e.term}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[12px] text-muted">{m.ambiguity_note || "No rule keywords or signals matched."}</p>
        )}
      </div>
      {m.ambiguous ? <p className="text-[12px] text-amber">{m.ambiguity_note}</p> : null}
      <p className="flex gap-2 rounded-sm border border-amber/30 bg-amber/[0.06] px-2.5 py-2 text-[11.5px] text-fg-2">
        <Info className="mt-0.5 size-3.5 shrink-0 text-amber" aria-hidden />
        <span>
          <span className="font-semibold text-amber">{m.label}.</span> {m.disclaimer}. This SCL-to-IOGP mapping is the Poorvabhas team&apos;s proposal, not an official IOGP or OIL mapping. It is a separate output and does not determine the SIF classification.
        </span>
      </p>
    </div>
  );
}

export function PipelineTrace({ trace, animate }: { trace: { stage: string; label: string; detail: string; ms: number }[]; animate?: number }) {
  return (
    <ol className="flex flex-col" aria-label="Analysis pipeline">
      {trace.map((t, i) => {
        const shown = animate === undefined || i < animate;
        const current = animate !== undefined && i === animate;
        return (
          <li key={t.stage} className="grid grid-cols-[22px_1fr] gap-3">
            <div className="flex flex-col items-center">
              <span className={cn("mt-1 flex size-[14px] items-center justify-center rounded-full border-2", shown ? "border-green bg-green/20" : current ? "animate-pulse border-cyan" : "border-border")} aria-hidden>
                {shown ? <span className="size-1.5 rounded-full bg-green" /> : null}
              </span>
              {i < trace.length - 1 ? <span className={cn("w-px flex-1", shown ? "bg-green/40" : "bg-border")} aria-hidden /> : null}
            </div>
            <div className={cn("pb-3.5 transition-opacity", shown ? "opacity-100" : "opacity-35")}>
              <p className="flex items-center justify-between gap-2">
                <span className="font-mono text-[11.5px] uppercase tracking-[0.1em] text-fg">{t.label}</span>
                {shown ? <span className="num font-mono text-[10.5px] text-muted">{t.ms.toFixed(1)} ms</span> : null}
              </p>
              <p className="mt-0.5 text-[12.5px] text-fg-2">{shown ? t.detail : current ? "Processing…" : "Queued"}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export function EvidenceCoverage({ analysis, report }: { analysis: Analysis; report: ReportDetail["report"] }) {
  const onPath = analysis.scl.gates.filter((g) => g.used_in_path);
  const answered = onPath.filter((g) => g.answer !== "INSUFFICIENT");
  const unanswered = onPath.filter((g) => g.answer === "INSUFFICIENT");
  const fields: [string, string | null][] = [
    ["Activity", report.activity],
    ["Location", report.location],
    ["Equipment", report.equipment],
  ];
  const present = fields.filter(([, v]) => v).length;
  const coverage = analysis.confidence_breakdown.components.find((c) => c.key === "completeness")?.value ?? null;
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-end justify-between">
        <p className="num font-mono text-[34px] font-semibold leading-none text-fg">
          {answered.length}
          <span className="text-[14px] text-muted"> / {onPath.length} SCL gates</span>
        </p>
        {coverage !== null ? <Badge tone={coverage >= 0.75 ? "green" : coverage >= 0.55 ? "amber" : "red"}>{coverage.toFixed(2)}</Badge> : null}
      </div>
      {coverage !== null ? <Meter value={coverage} tone={coverage >= 0.75 ? "green" : coverage >= 0.55 ? "amber" : "red"} label="Evidence coverage" /> : null}
      <p className="text-[11.5px] text-muted">Whether the report states enough to decide: SCL gates on the decision path supported by report text, key fields present, and facts not stated.</p>
      <ul className="flex flex-col gap-1.5 text-[12.5px]">
        <li className="flex justify-between gap-2">
          <span className="text-fg-2">Key fields present</span>
          <span className="num font-mono text-fg">{present}/3</span>
        </li>
        {unanswered.length ? (
          <li className="text-amber">Insufficient information: {unanswered.map((g) => g.question).join(" · ")}</li>
        ) : null}
        {analysis.not_stated.length ? (
          <li className="text-fg-2">
            <span className="text-muted">Not stated:</span> {analysis.not_stated.map((t) => ENTITY_LABELS[t] ?? t).join(", ")}
          </li>
        ) : null}
      </ul>
    </div>
  );
}
