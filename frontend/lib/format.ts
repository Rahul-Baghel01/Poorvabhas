import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export type Tone = "red" | "amber" | "cyan" | "green" | "neutral" | "red-deep";

export const SIF_SIGNAL_META: Record<string, { label: string; short: string; tone: Tone; color: string }> = {
  SIF_EVENT: { label: "SIF Event", short: "SIF EVENT", tone: "red-deep", color: "#C9362D" },
  SIF_POTENTIAL: { label: "SIF-potential", short: "SIF-POTENTIAL", tone: "red", color: "#FF4A43" },
  UNDETERMINED: { label: "Undetermined", short: "UNDETERMINED", tone: "amber", color: "#F2B233" },
  NON_SIF: { label: "Non-SIF", short: "NON-SIF", tone: "neutral", color: "#6B7678" },
  PENDING: { label: "Pending", short: "PENDING", tone: "neutral", color: "#6B7678" },
};

export const STATUS_META: Record<string, { label: string; tone: Tone }> = {
  // Stored status values are unchanged; HUMAN_REJECTED means the reviewer overturned the engine output.
  AI_ANALYZED: { label: "Engine analyzed", tone: "cyan" },
  REVIEW_REQUIRED: { label: "Review required", tone: "amber" },
  HUMAN_CONFIRMED: { label: "Expert confirmed", tone: "green" },
  HUMAN_REJECTED: { label: "Expert corrected", tone: "green" },
  PENDING: { label: "Pending", tone: "neutral" },
};

export const PRIORITY_META: Record<string, { label: string; tone: Tone }> = {
  CRITICAL: { label: "Critical", tone: "red" },
  HIGH: { label: "High", tone: "red" },
  MEDIUM: { label: "Medium", tone: "amber" },
  LOW: { label: "Low", tone: "neutral" },
};

export const SCL_META: Record<string, { label: string; description: string }> = {
  HSIF: { label: "HSIF", description: "High-energy incident with serious injury or fatality" },
  PSIF: { label: "PSIF", description: "High-energy incident, no direct control, no serious injury" },
  EXPOSURE: { label: "Exposure", description: "High energy present, no direct control, no release" },
  CAPACITY: { label: "Capacity", description: "High-energy incident absorbed by a direct control" },
  SUCCESS: { label: "Success", description: "High energy controlled by a direct control" },
  LSIF: { label: "LSIF", description: "Serious injury from low energy" },
  LOW_SEVERITY: { label: "Low Severity", description: "Low energy, no serious injury" },
  UNDETERMINED: { label: "Undetermined", description: "Evidence insufficient to resolve the SCL path" },
};

export const LSR_SHORT: Record<string, string> = {
  BYPASSING_SAFETY_CONTROLS: "Bypassing Safety Controls",
  CONFINED_SPACE: "Confined Space",
  DRIVING: "Driving",
  ENERGY_ISOLATION: "Energy Isolation",
  HOT_WORK: "Hot Work",
  LINE_OF_FIRE: "Line of Fire",
  SAFE_MECHANICAL_LIFTING: "Safe Mechanical Lifting",
  WORK_AUTHORIZATION: "Work Authorization",
  WORKING_AT_HEIGHT: "Working at Height",
  PROCESS_SAFETY_NA: "Process Safety / No Applicable Rule",
};

export const REVIEW_CATEGORY_META: Record<string, { label: string; hint: string }> = {
  LOW_CONFIDENCE: { label: "Low confidence", hint: "Overall confidence below threshold" },
  BORDERLINE: { label: "Borderline", hint: "A decision gate rests on weak evidence" },
  INSUFFICIENT_INFORMATION: { label: "Insufficient information", hint: "Required facts are not stated" },
  RULE_CONFLICT: { label: "Rule conflict", hint: "Conflicting controls or ambiguous rule mapping" },
  MODEL_RULE_DISAGREEMENT: { label: "Classifier / engine disagreement", hint: "Classifier disagrees with the SCL engine" },
  MANUAL_REQUEST: { label: "Manual request", hint: "Sent to reviewer by an HSE officer" },
};

/** Display names for the stored audit event codes (codes are unchanged for traceability). */
export const EVENT_LABELS: Record<string, string> = {
  REPORT_CREATED: "Report created",
  REPORT_ANALYZED: "Report analyzed",
  SIF_CLASSIFIED: "SCL classified",
  RULE_MAPPED: "LSR mapped",
  REVIEW_STARTED: "Review requested / note",
  REVIEW_COMPLETED: "Review decision",
  TAXONOMY_CHANGED: "Taxonomy updated",
  SETTINGS_CHANGED: "Settings updated",
  MODEL_CHANGED: "Model retrained / re-analysis",
  PATTERNS_MINED: "Patterns mined",
  IMPORT_COMPLETED: "Import completed",
  DATASET_SEEDED: "Synthetic dataset seeded",
  USER_LOGIN: "Sign-in",
};

export const TREND_META: Record<string, { label: string; tone: Tone }> = {
  INCREASING: { label: "Increasing", tone: "red" },
  DECREASING: { label: "Decreasing", tone: "green" },
  STABLE: { label: "Stable", tone: "neutral" },
  INSUFFICIENT_HISTORY: { label: "Insufficient history", tone: "neutral" },
};

export const ENTITY_LABELS: Record<string, string> = {
  activity: "Activity",
  site: "Site",
  location: "Location",
  equipment: "Equipment",
  energy_source: "Energy source",
  hazard: "Hazard",
  barrier: "Barrier (direct control)",
  control: "Control (administrative)",
  failure_mode: "Failure mode",
  human_behavior: "Human behaviour",
  report_type: "Report type",
  injury_outcome: "Injury outcome",
  environmental_context: "Environmental context",
};

export const ENTITY_TONE: Record<string, Tone> = {
  energy_source: "red",
  hazard: "red",
  barrier: "cyan",
  control: "cyan",
  failure_mode: "amber",
  human_behavior: "amber",
  activity: "green",
  equipment: "neutral",
  environmental_context: "neutral",
  injury_outcome: "neutral",
};

export const TONE_TEXT: Record<Tone, string> = {
  red: "text-red",
  "red-deep": "text-red",
  amber: "text-amber",
  cyan: "text-cyan",
  green: "text-green",
  neutral: "text-fg-2",
};

export function pct(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${(v * 100).toFixed(digits)}%`;
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso.length === 10 ? iso + "T00:00:00" : iso);
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function titleCase(s: string | null | undefined): string {
  if (!s) return "";
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function confidenceLevel(c: number | null | undefined): "HIGH" | "MEDIUM" | "LOW" | null {
  if (c === null || c === undefined) return null;
  return c >= 0.75 ? "HIGH" : c >= 0.55 ? "MEDIUM" : "LOW";
}

/** Split text into plain and highlighted segments. Overlapping spans: earliest-start, longest wins. */
export function segmentText(text: string, spans: { start: number; end: number; tone: Tone; label: string }[]) {
  const sorted = spans
    .filter((s) => s.start >= 0 && s.end <= text.length && s.end > s.start)
    .sort((a, b) => a.start - b.start || b.end - a.end);
  const out: { text: string; span?: { tone: Tone; label: string } }[] = [];
  let pos = 0;
  for (const s of sorted) {
    if (s.start < pos) continue;
    if (s.start > pos) out.push({ text: text.slice(pos, s.start) });
    out.push({ text: text.slice(s.start, s.end), span: { tone: s.tone, label: s.label } });
    pos = s.end;
  }
  if (pos < text.length) out.push({ text: text.slice(pos) });
  return out;
}
