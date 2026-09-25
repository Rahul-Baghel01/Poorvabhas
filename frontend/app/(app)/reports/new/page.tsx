"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, FlaskConical, Play, RotateCcw } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { PipelineTrace } from "@/components/report/Breakdowns";
import { EvidenceText } from "@/components/report/EvidenceText";
import { LsrTag, PriorityBadge, SclBadge, SifBadge } from "@/components/ui/badges";
import { Badge, Button, Field, Input, Notice, PageHeader, Panel, Select, Textarea } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useInvalidateAll } from "@/lib/hooks";
import type { ReportDetail, TraceStage } from "@/lib/types";

const STAGE_LABELS = ["Ingested", "Text processed", "Entities extracted", "Energy + control analysis", "SCL classification", "IOGP mapping", "Pattern check", "Priority", "Review decision"];

const EXAMPLES = [
  { label: "Isolation not verified", report_type: "Near Miss", site: "Digboi", location: "GGS-2 Digboi", activity: "Pump maintenance", equipment: "Booster pump", description: "During pump maintenance, isolation was not verified before opening the line. Residual pressure was observed and the task was stopped.", worker_role: "Fitter" },
  { label: "Hot work, no gas test", report_type: "Unsafe Act", site: "Duliajan", location: "OCS-4 Duliajan", activity: "Hot work", equipment: "Welding set", description: "During hot work, gas testing was not completed before welding began. Work was stopped when the issue was identified.", worker_role: "Welder" },
  { label: "Exclusion zone breach", report_type: "Unsafe Act", site: "Tengakhat", location: "Drilling Rig SR-5", activity: "Lifting", equipment: "Mobile crane", description: "During lifting operations, a worker entered the exclusion zone while a suspended load was moving.", worker_role: "Rigger" },
  { label: "Confined space", report_type: "Unsafe Act", site: "Moran", location: "OCS-1 Moran", activity: "Confined-space entry", equipment: "Crude storage tank", description: "Worker entered a confined space without atmospheric monitoring.", worker_role: "Tank Cleaner" },
  { label: "Vehicle + pedestrian", report_type: "Unsafe Condition", site: "Digboi", location: "Loading Gantry", activity: "Vehicle movement", equipment: "Tanker", description: "Vehicle movement occurred while a pedestrian was working nearby.", worker_role: "Loading Operator" },
];

type Form = {
  report_id: string;
  report_type: string;
  date: string;
  site: string;
  location: string;
  activity: string;
  equipment: string;
  description: string;
  worker_role: string;
  contractor: string;
  injury_severity: string;
  shift: string;
  weather: string;
};

const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
const EMPTY: Form = { report_id: "", report_type: "Near Miss", date: today(), site: "", location: "", activity: "", equipment: "", description: "", worker_role: "", contractor: "", injury_severity: "None", shift: "Day", weather: "" };

export default function NewReportPage() {
  const invalidate = useInvalidateAll();
  const [form, setForm] = React.useState<Form>(EMPTY);
  const [step, setStep] = React.useState<number | undefined>(undefined);
  const facets = useQuery({ queryKey: ["facets"], queryFn: () => api<{ sites: { name: string }[]; activities: string[]; injury_severities: string[] }>("/reports/facets"), staleTime: 300_000 });
  const set = (k: keyof Form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const m = useMutation({
    mutationFn: () =>
      api<{ report_id: string; trace: TraceStage[]; detail: ReportDetail }>("/reports", {
        method: "POST",
        json: Object.fromEntries(Object.entries(form).map(([k, v]) => [k, v === "" ? null : v])),
      }),
    onSuccess: () => {
      setStep(0);
      invalidate();
    },
  });

  React.useEffect(() => {
    if (step === undefined || !m.data) return;
    if (step >= m.data.trace.length) return;
    const t = setTimeout(() => setStep((s) => (s ?? 0) + 1), 320);
    return () => clearTimeout(t);
  }, [step, m.data]);

  const done = m.data && step !== undefined && step >= m.data.trace.length;
  const detail = m.data?.detail;
  const a = detail?.analysis;
  const placeholderTrace = STAGE_LABELS.map((l, i) => ({ stage: String(i), label: l, detail: "", ms: 0, status: "", data: {} }));

  return (
    <div>
      <PageHeader eyebrow="Ingestion / manual entry" title="New report" subtitle="Enter an unsafe act, unsafe condition, near miss or incident. The engine analyses it immediately; nothing is assumed that the text does not say." />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
        <Panel title="Report" subtitle="Fields marked * are required" id="form">
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <span className="label-tech mr-1 flex items-center gap-1.5">
              <FlaskConical className="size-3.5" aria-hidden /> Demo cases
            </span>
            {EXAMPLES.map((ex) => (
              <button
                key={ex.label}
                type="button"
                onClick={() => {
                  setForm({ ...EMPTY, ...ex, date: today() });
                  m.reset();
                  setStep(undefined);
                }}
                className="rounded-xs border border-border bg-surface-2 px-2 py-1 text-[12px] text-fg-2 hover:border-border-strong hover:text-fg"
              >
                {ex.label}
              </button>
            ))}
          </div>
          <form
            className="grid gap-4 md:grid-cols-2"
            onSubmit={(e) => {
              e.preventDefault();
              setStep(undefined);
              m.mutate();
            }}
          >
            <Field label="Report ID" htmlFor="report_id" hint="Leave blank to auto-assign (RPT-YYYY-NNNN)">
              <Input id="report_id" value={form.report_id} onChange={set("report_id")} placeholder="Auto" maxLength={40} />
            </Field>
            <Field label="Report type" htmlFor="report_type" required>
              <Select id="report_type" value={form.report_type} onChange={set("report_type")} required>
                {["Unsafe Act", "Unsafe Condition", "Near Miss", "Incident"].map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </Select>
            </Field>
            <Field label="Date" htmlFor="date" required>
              <Input id="date" type="date" value={form.date} max={today()} onChange={set("date")} required />
            </Field>
            <Field label="Site" htmlFor="site" required>
              <Input id="site" list="sites" value={form.site} onChange={set("site")} required placeholder="e.g. Digboi" />
              <datalist id="sites">
                {facets.data?.sites.map((s) => (
                  <option key={s.name} value={s.name} />
                ))}
              </datalist>
            </Field>
            <Field label="Location" htmlFor="location" required>
              <Input id="location" value={form.location} onChange={set("location")} required placeholder="e.g. GGS-2, Well Pad 41" />
            </Field>
            <Field label="Activity" htmlFor="activity" required>
              <Input id="activity" list="activities" value={form.activity} onChange={set("activity")} required placeholder="e.g. Pump maintenance" />
              <datalist id="activities">
                {facets.data?.activities.map((s) => (
                  <option key={s} value={s} />
                ))}
              </datalist>
            </Field>
            <Field label="Equipment" htmlFor="equipment">
              <Input id="equipment" value={form.equipment} onChange={set("equipment")} />
            </Field>
            <Field label="Worker role" htmlFor="worker_role">
              <Input id="worker_role" value={form.worker_role} onChange={set("worker_role")} />
            </Field>
            <Field label="Contractor" htmlFor="contractor">
              <Input id="contractor" value={form.contractor} onChange={set("contractor")} placeholder="Leave blank if company staff" />
            </Field>
            <Field label="Injury severity" htmlFor="injury_severity">
              <Select id="injury_severity" value={form.injury_severity} onChange={set("injury_severity")}>
                <option value="">Not stated</option>
                {(facets.data?.injury_severities ?? ["None", "First Aid", "Medical Treatment", "Restricted Work", "Lost Time Injury", "Serious Injury", "Fatality"]).map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </Select>
            </Field>
            <Field label="Shift" htmlFor="shift">
              <Select id="shift" value={form.shift} onChange={set("shift")}>
                <option value="">Not stated</option>
                <option>Day</option>
                <option>Night</option>
              </Select>
            </Field>
            <Field label="Weather" htmlFor="weather">
              <Input id="weather" value={form.weather} onChange={set("weather")} placeholder="e.g. Rain, High Wind" />
            </Field>
            <Field label="Description" htmlFor="description" required className="md:col-span-2" hint="Describe what was observed: activity, energy, controls, what happened. Minimum 15 characters.">
              <Textarea id="description" value={form.description} onChange={set("description")} required minLength={15} maxLength={5000} className="min-h-32" />
            </Field>
            {m.error ? (
              <div className="md:col-span-2">
                <Notice tone="red" title="Report not saved">
                  {(m.error as Error).message}
                </Notice>
              </div>
            ) : null}
            <div className="flex items-center justify-end gap-2 md:col-span-2">
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setForm({ ...EMPTY, date: today() });
                  m.reset();
                  setStep(undefined);
                }}
              >
                <RotateCcw className="size-4" aria-hidden /> Reset
              </Button>
              <Button type="submit" variant="primary" loading={m.isPending} className="px-6 font-mono uppercase tracking-[0.12em]">
                <Play className="size-4" aria-hidden /> Analyze report
              </Button>
            </div>
          </form>
        </Panel>

        <div className="flex flex-col gap-5">
          <Panel title="Live pipeline" subtitle={m.data ? "Stage timings measured by the engine" : "Runs locally — no external AI service"} id="pipeline" accent={done ? "green" : undefined}>
            <div aria-live="polite">
              <PipelineTrace trace={m.data?.trace ?? placeholderTrace} animate={m.data ? step : m.isPending ? 0 : -1} />
            </div>
          </Panel>

          {done && detail && a ? (
            <Panel title="Result" id="result" accent={a.sif_signal === "SIF_POTENTIAL" || a.sif_signal === "SIF_EVENT" ? "red" : a.sif_signal === "UNDETERMINED" ? "amber" : "neutral"}>
              <div className="flex flex-col gap-3">
                <p className="font-mono text-[18px] font-semibold">{detail.report.report_id}</p>
                <div className="flex flex-wrap items-center gap-2">
                  <SifBadge signal={a.sif_signal} />
                  <span className="text-[12px] text-muted">SCL</span> <SclBadge scl={a.scl.scl_class} />
                  <PriorityBadge level={a.priority_level} score={a.priority_score} />
                </div>
                <LsrTag code={a.mapping.primary.code} name={a.mapping.primary.name} />
                <div className="rounded-sm border border-border bg-bg/60 p-3">
                  <EvidenceText text={detail.report.description} entities={a.entities} className="text-[13.5px] leading-[1.8]" />
                </div>
                <p className="text-[12.5px] text-fg-2">{a.reasoning_summary}</p>
                {detail.review ? (
                  <Notice tone="amber" title={`Routed to human review — ${detail.review.category_label}`}>
                    {detail.review.reasons.map((r) => r.detail).join("; ")}
                  </Notice>
                ) : (
                  <Badge tone="cyan">AI analyzed — awaiting human validation</Badge>
                )}
                <Link href={`/reports/${detail.report.report_id}`}>
                  <Button variant="primary" className="w-full">
                    Open full investigation <ArrowRight className="size-4" aria-hidden />
                  </Button>
                </Link>
              </div>
            </Panel>
          ) : null}
        </div>
      </div>
    </div>
  );
}
