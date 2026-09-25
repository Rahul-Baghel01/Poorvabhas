"use client";

import * as React from "react";

import type { EntityOut } from "@/lib/types";
import { ENTITY_LABELS, cn, segmentText, type Tone } from "@/lib/format";

export const HIGHLIGHT_TYPES: { type: string; tone: Tone; label: string }[] = [
  { type: "energy_source", tone: "red", label: "Energy" },
  { type: "failure_mode", tone: "amber", label: "Barrier failure" },
  { type: "barrier", tone: "cyan", label: "Barrier / control" },
  { type: "control", tone: "cyan", label: "Admin control" },
  { type: "activity", tone: "green", label: "Activity" },
  { type: "human_behavior", tone: "amber", label: "Behaviour" },
  { type: "equipment", tone: "neutral", label: "Equipment" },
  { type: "environmental_context", tone: "neutral", label: "Context" },
  { type: "injury_outcome", tone: "neutral", label: "Injury" },
];

const TONE_CLASS: Record<Tone, string> = {
  red: "text-[#ff7a74] bg-red/10",
  "red-deep": "text-[#ff7a74] bg-red/10",
  amber: "text-amber bg-amber/10",
  cyan: "text-cyan bg-cyan/10",
  green: "text-green bg-green/10",
  neutral: "text-fg bg-white/[0.04]",
};

export function spansFrom(entities: EntityOut[], focus?: string | null) {
  const spans: { start: number; end: number; tone: Tone; label: string }[] = [];
  const order = HIGHLIGHT_TYPES.map((h) => h.type);
  const sorted = [...entities].sort((a, b) => order.indexOf(a.entity_type) - order.indexOf(b.entity_type));
  for (const e of sorted) {
    const h = HIGHLIGHT_TYPES.find((x) => x.type === e.entity_type);
    if (!h) continue;
    const key = `${e.entity_type}:${e.canonical}`;
    if (focus && focus !== key) continue;
    const tone: Tone = e.entity_type === "barrier" && (e.polarity === "failed" || e.polarity === "absent") ? "amber" : h.tone;
    for (const ev of e.evidence) {
      if (ev.start !== null && ev.end !== null && ev.source !== "structured_field") {
        spans.push({ start: ev.start, end: ev.end, tone, label: `${ENTITY_LABELS[e.entity_type] ?? e.entity_type}: ${e.canonical ?? e.value}${e.polarity ? ` (${e.polarity})` : ""} · ${(e.confidence * 100).toFixed(0)}%` });
      }
    }
  }
  return spans;
}

export function EvidenceText({ text, entities, focus, className }: { text: string; entities: EntityOut[]; focus?: string | null; className?: string }) {
  // Priority order in spansFrom means failure/energy spans win overlaps over generic ones.
  const segments = React.useMemo(() => segmentText(text, spansFrom(entities, focus)), [text, entities, focus]);
  return (
    <p className={cn("text-[15px] leading-[1.85] text-fg", className)}>
      {segments.map((s, i) =>
        s.span ? (
          <mark key={i} className={cn("ev rounded-[2px] px-0.5", TONE_CLASS[s.span.tone])} title={s.span.label} aria-label={`${s.text} — ${s.span.label}`}>
            {s.text}
          </mark>
        ) : (
          <React.Fragment key={i}>{s.text}</React.Fragment>
        ),
      )}
    </p>
  );
}

export function EvidenceLegend() {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1.5" aria-label="Highlight legend">
      {HIGHLIGHT_TYPES.slice(0, 6).map((h) => (
        <li key={h.type} className="flex items-center gap-1.5 text-[11.5px] text-fg-2">
          <span className={cn("h-[3px] w-3 rounded-full", { red: "bg-red", amber: "bg-amber", cyan: "bg-cyan", green: "bg-green", neutral: "bg-fg-2", "red-deep": "bg-red" }[h.tone])} aria-hidden />
          {h.label}
        </li>
      ))}
    </ul>
  );
}

/** A quote of evidence from the original report, or the structured field it came from. */
export function Quote({ text, source }: { text: string; source?: string }) {
  if (source === "structured_field") {
    return (
      <span className="inline-flex items-center gap-1.5 text-[12.5px] text-fg-2">
        <span className="rounded-xs border border-border px-1 font-mono text-[10px] uppercase text-muted">field</span>
        {text}
      </span>
    );
  }
  return <q className="text-[12.5px] italic text-fg before:text-muted after:text-muted">{text}</q>;
}
