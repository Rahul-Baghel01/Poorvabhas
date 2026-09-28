import {
  ArrowDownRight,
  ArrowUpRight,
  CircleCheck,
  CircleHelp,
  ClipboardCheck,
  Construction,
  Container,
  Crosshair,
  Flame,
  Gauge,
  Lock,
  Minus,
  Mountain,
  PencilLine,
  ShieldOff,
  Truck,
} from "lucide-react";

import { Badge } from "@/components/ui/primitives";
import { LSR_SHORT, PRIORITY_META, SCL_META, SIF_SIGNAL_META, STATUS_META, TREND_META, cn, confidenceLevel } from "@/lib/format";

export const LSR_ICON: Record<string, React.ElementType> = {
  BYPASSING_SAFETY_CONTROLS: ShieldOff,
  CONFINED_SPACE: Container,
  DRIVING: Truck,
  ENERGY_ISOLATION: Lock,
  HOT_WORK: Flame,
  LINE_OF_FIRE: Crosshair,
  SAFE_MECHANICAL_LIFTING: Construction,
  WORK_AUTHORIZATION: ClipboardCheck,
  WORKING_AT_HEIGHT: Mountain,
  PROCESS_SAFETY_NA: Gauge,
};

export function SifBadge({ signal }: { signal: string | null | undefined }) {
  const m = SIF_SIGNAL_META[signal || "PENDING"] ?? SIF_SIGNAL_META.PENDING;
  return (
    <Badge tone={m.tone} dot>
      {m.short}
    </Badge>
  );
}

export function StatusBadge({ status }: { status: string | null | undefined }) {
  const m = STATUS_META[status || "PENDING"] ?? STATUS_META.PENDING;
  const Icon = status === "HUMAN_CONFIRMED" ? CircleCheck : status === "HUMAN_REJECTED" ? PencilLine : null;
  return (
    <Badge tone={m.tone}>
      {Icon ? <Icon className="size-3" aria-hidden /> : null}
      {m.label}
    </Badge>
  );
}

export function PriorityBadge({ level, score }: { level: string | null | undefined; score?: number | null }) {
  if (!level) return <span className="text-muted">—</span>;
  const m = PRIORITY_META[level];
  return (
    <span className="inline-flex items-center gap-2">
      <Badge tone={m.tone} className={level === "CRITICAL" ? "border-red bg-red/20" : undefined}>
        {m.label}
      </Badge>
      {score !== undefined && score !== null ? <span className="num font-mono text-[12px] text-fg-2">{Math.round(score)}</span> : null}
    </span>
  );
}

export function SclBadge({ scl }: { scl: string | null | undefined }) {
  if (!scl) return <span className="text-muted">—</span>;
  const m = SCL_META[scl];
  return (
    <span title={m?.description} className="font-mono text-[12px] font-medium tracking-wide text-fg">
      {m?.label ?? scl}
    </span>
  );
}

export function LsrTag({ code, name, className }: { code: string | null | undefined; name?: string | null; className?: string }) {
  if (!code) return <span className="text-muted">—</span>;
  const Icon = LSR_ICON[code] ?? Gauge;
  return (
    <span className={cn("inline-flex min-w-0 items-center gap-1.5 text-[12.5px] text-fg-2", className)}>
      <Icon className="size-3.5 shrink-0 text-cyan" aria-hidden />
      <span className="truncate">{name || LSR_SHORT[code] || code}</span>
    </span>
  );
}

export function ConfidenceTag({ value }: { value: number | null | undefined }) {
  const lvl = confidenceLevel(value);
  if (!lvl || value === null || value === undefined) return <span className="text-muted">—</span>;
  const color = lvl === "HIGH" ? "bg-green" : lvl === "MEDIUM" ? "bg-amber" : "bg-red";
  return (
    <span className="inline-flex items-center gap-2" title={`${lvl.toLowerCase()} confidence`}>
      <span className="flex gap-[2px]" aria-hidden>
        {[0, 1, 2].map((i) => (
          <span key={i} className={cn("h-2.5 w-1 rounded-[1px]", i < (lvl === "HIGH" ? 3 : lvl === "MEDIUM" ? 2 : 1) ? color : "bg-surface-3")} />
        ))}
      </span>
      <span className="num font-mono text-[12px] text-fg-2">{value.toFixed(2)}</span>
      <span className="sr-only">{lvl.toLowerCase()} confidence</span>
    </span>
  );
}

export function AnswerBadge({ answer }: { answer: string }) {
  const tone = answer === "YES" ? "red" : answer === "NO" ? "green" : "amber";
  return <Badge tone={tone}>{answer === "INSUFFICIENT" ? "Insufficient info" : answer}</Badge>;
}

export function ControlAnswerBadge({ answer }: { answer: string }) {
  // For the control gate, "NO" (no control) is the hazardous answer.
  const tone = answer === "NO" ? "red" : answer === "YES" ? "green" : "amber";
  return <Badge tone={tone}>{answer === "INSUFFICIENT" ? "Insufficient info" : answer}</Badge>;
}

export function TrendBadge({ trend }: { trend: string }) {
  const m = TREND_META[trend] ?? TREND_META.STABLE;
  const Icon = trend === "INCREASING" ? ArrowUpRight : trend === "DECREASING" ? ArrowDownRight : trend === "STABLE" ? Minus : CircleHelp;
  return (
    <Badge tone={m.tone}>
      <Icon className="size-3" aria-hidden />
      {m.label}
    </Badge>
  );
}
