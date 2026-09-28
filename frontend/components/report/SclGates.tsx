"use client";

import { ArrowDown, ArrowRight, GitBranch } from "lucide-react";

import { AnswerBadge, ControlAnswerBadge, SifBadge } from "@/components/ui/badges";
import { Quote } from "@/components/report/EvidenceText";
import type { Analysis, Gate } from "@/lib/types";
import { SCL_META, cn } from "@/lib/format";

const GATE_ORDER: Gate["key"][] = ["high_energy", "high_energy_event", "direct_control", "serious_injury"];
const GATE_TITLE: Record<Gate["key"], string> = {
  high_energy: "High energy?",
  high_energy_event: "High-energy event?",
  direct_control: "Direct control?",
  serious_injury: "Serious injury?",
};

function GateCard({ gate, index }: { gate: Gate; index: number }) {
  const Answer = gate.key === "direct_control" ? ControlAnswerBadge : AnswerBadge;
  return (
    <div className={cn("relative flex h-full flex-col gap-2.5 rounded-sm border bg-bg/60 p-3.5", gate.used_in_path ? "border-border-strong" : "border-border border-dashed opacity-60")}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted">Gate Q{index + 1}</p>
          <p className="mt-0.5 text-[14px] font-semibold text-fg">{GATE_TITLE[gate.key]}</p>
        </div>
        <Answer answer={gate.answer} />
      </div>
      <p className="text-[12px] leading-snug text-fg-2">{gate.rationale}</p>
      {gate.evidence.length ? (
        <div className="flex flex-col gap-1 border-t border-border pt-2">
          <p className="label-tech">Evidence</p>
          {gate.evidence.slice(0, 3).map((e, i) => (
            <Quote key={i} text={e.text} source={e.source} />
          ))}
        </div>
      ) : (
        <p className="border-t border-border pt-2 text-[12px] text-amber">No supporting evidence in the report — not assumed.</p>
      )}
      <div className="mt-auto flex items-center justify-between pt-1">
        <span className="font-mono text-[10.5px] uppercase tracking-wider text-muted">{gate.used_in_path ? "On decision path" : "Not on path"}</span>
        <span className="num font-mono text-[11.5px] text-fg-2">conf {gate.confidence.toFixed(2)}</span>
      </div>
    </div>
  );
}

const ANSWER_TEXT: Record<string, string> = { YES: "Yes", NO: "No", INSUFFICIENT: "Not stated" };

/** The two SCL checks that decide SIF-potential, and the engine's outcome with its reason. */
function EnergyControlTest({ analysis }: { analysis: Analysis }) {
  const scl = analysis.scl;
  const energy = scl.gates.find((g) => g.key === "high_energy");
  const control = scl.gates.find((g) => g.key === "direct_control");
  const e = energy?.answer ?? "INSUFFICIENT";
  const c = control?.answer ?? "INSUFFICIENT";
  const reason =
    scl.sif_signal === "SIF_EVENT"
      ? "High energy was released and a serious injury or fatality occurred: an actual SIF Event (HSIF), routed to incident investigation."
      : scl.sif_potential === true
        ? "High energy was present and no direct control was in place: SIF-potential regardless of the injury outcome."
        : scl.sif_potential === false
          ? e === "NO"
            ? "No high-energy source is stated, so the report is not SIF-potential."
            : "High energy was present but a direct control was in place, so the report is not SIF-potential."
          : "The report does not contain enough evidence to answer both checks. Nothing is assumed; the case goes to an HSE reviewer.";
  return (
    <div className="grid gap-3 rounded-sm border border-border-strong bg-surface-2 p-3.5 md:grid-cols-[1fr_1fr_1.4fr]" aria-label="Energy and control test">
      <div>
        <p className="label-tech">1 · High energy present?</p>
        <p className="mt-1.5 flex items-center gap-2 text-[14px] font-semibold text-fg">
          <AnswerBadge answer={e} /> <span className="sr-only">{ANSWER_TEXT[e]}</span>
        </p>
      </div>
      <div>
        <p className="label-tech">2 · Direct control in place?</p>
        <p className="mt-1.5 flex items-center gap-2 text-[14px] font-semibold text-fg">
          <ControlAnswerBadge answer={c} /> <span className="sr-only">{ANSWER_TEXT[c]}</span>
        </p>
      </div>
      <div>
        <p className="label-tech">Result</p>
        <p className="mt-1.5">
          <SifBadge signal={scl.sif_signal} />
        </p>
        <p className="mt-1.5 text-[12px] leading-snug text-fg-2">{reason}</p>
      </div>
      <p className="text-[11px] text-muted md:col-span-3">SIF-potential is decided by energy and direct control, not by the reported injury severity. Injury outcome only separates an actual SIF Event (HSIF) from PSIF, and LSIF from Low Severity.</p>
    </div>
  );
}

export function SclGates({ analysis }: { analysis: Analysis }) {
  const scl = analysis.scl;
  const gates = GATE_ORDER.map((k) => scl.gates.find((g) => g.key === k)).filter(Boolean) as Gate[];
  const clsMeta = SCL_META[scl.scl_class];
  return (
    <div className="flex flex-col gap-4">
      <EnergyControlTest analysis={analysis} />
      <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-4">
        {gates.map((g, i) => (
          <GateCard key={g.key} gate={g} index={i} />
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2 rounded-sm border border-border bg-bg/50 px-3 py-2" aria-label="Decision path">
        <GitBranch className="size-4 text-muted" aria-hidden />
        <span className="label-tech mr-1">Decision path</span>
        {scl.decision_path.map((p, i) => {
          const [k, v] = p.split("=");
          return (
            <span key={p} className="flex items-center gap-2">
              <span className="rounded-xs border border-border bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-fg-2">
                {GATE_TITLE[k as Gate["key"]] ?? k} <span className={cn(v === "INSUFFICIENT" ? "text-amber" : "text-fg")}>{v === "INSUFFICIENT" ? "INSUFF." : v}</span>
              </span>
              {i < scl.decision_path.length - 1 ? <ArrowRight className="size-3 text-muted" aria-hidden /> : null}
            </span>
          );
        })}
      </div>

      <div className="flex items-center justify-center" aria-hidden>
        <ArrowDown className="size-4 text-muted" />
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-sm border border-border-strong bg-surface-2 p-4">
          <p className="label-tech">SCL class</p>
          <p className="mt-1.5 font-mono text-[26px] font-semibold tracking-tight text-fg">{clsMeta?.label ?? scl.scl_class}</p>
          <p className="mt-1 text-[12.5px] text-fg-2">{scl.scl_description || clsMeta?.description}</p>
          {scl.scl_class === "UNDETERMINED" && scl.candidates.length ? (
            <p className="mt-2 text-[12px] text-amber">Remaining candidates: {scl.candidates.map((c) => SCL_META[c]?.label ?? c).join(" · ")}</p>
          ) : null}
        </div>
        <div className={cn("rounded-sm border p-4", scl.sif_signal === "SIF_POTENTIAL" || scl.sif_signal === "SIF_EVENT" ? "border-red/50 bg-red/[0.07]" : scl.sif_signal === "UNDETERMINED" ? "border-amber/40 bg-amber/[0.06]" : "border-border bg-surface-2")}>
          <p className="label-tech">SIF-potential</p>
          <p className={cn("mt-1.5 font-mono text-[26px] font-semibold tracking-tight", scl.sif_potential === true ? "text-red" : scl.sif_potential === false ? "text-fg" : "text-amber")}>
            {scl.sif_potential === true ? "YES" : scl.sif_potential === false ? "NO" : "UNDETERMINED"}
          </p>
          <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[12.5px] text-fg-2">
            <SifBadge signal={scl.sif_signal} />
            <span>SIF-potential = SCL class PSIF or Exposure</span>
          </div>
          {scl.sif_signal === "SIF_EVENT" ? <p className="mt-1.5 text-[12px] text-fg-2">Actual serious outcome (HSIF): route to incident investigation.</p> : null}
        </div>
      </div>
      {scl.conflicts.length ? <p className="text-[12.5px] text-amber">Conflicts: {scl.conflicts.join("; ")}</p> : null}
    </div>
  );
}
