"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Save } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { RequirePermission } from "@/components/shell/RequirePermission";
import { Badge, Button, ErrorState, Input, KV, LoadingState, Notice, PageHeader, Panel } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { SCL_META, cn } from "@/lib/format";

interface SettingsOut {
  engine: {
    priority_weights: Record<string, number>;
    priority_thresholds: Record<string, number>;
    review_thresholds: Record<string, number>;
    sif_potential_classes: string[];
    recurrence_window_days: number;
    pattern_min_cluster_size: number;
    use_classifier: boolean;
  };
  environment: { environment: string; demo_mode: boolean; data_mode: string; label: string | null };
  database: { dialect: string; pgvector: boolean; counts: Record<string, number> };
  models: Record<string, string>;
  security: { auth: string; password_hashing: string; roles: string[]; token_minutes: number; secure_cookie: boolean };
  audit: { event_types: string[] };
}

const WEIGHT_LABELS: Record<string, string> = {
  energy_exposure: "Energy exposure",
  barrier_failure: "Barrier / control failure",
  precursor_severity: "Precursor severity (SCL)",
  recurrence: "Recurrence",
  exposure_context: "Exposure / context",
};

function useSave(key: string) {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (value: unknown) => api(`/settings/${key}`, { method: "PUT", json: { value } }), onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }) });
}

function Weights({ initial }: { initial: Record<string, number> }) {
  const [w, setW] = React.useState(initial);
  const save = useSave("priority_weights");
  const total = Object.values(w).reduce((a, b) => a + (Number(b) || 0), 0);
  return (
    <div className="flex flex-col gap-3">
      {Object.keys(WEIGHT_LABELS).map((k) => (
        <div key={k} className="grid grid-cols-[1fr_90px] items-center gap-3">
          <label htmlFor={`w-${k}`} className="text-[13px] text-fg-2">
            {WEIGHT_LABELS[k]}
          </label>
          <Input id={`w-${k}`} type="number" min={0} max={100} step={1} value={w[k]} onChange={(e) => setW({ ...w, [k]: Number(e.target.value) })} className="h-8 text-right font-mono" />
        </div>
      ))}
      <div className="flex items-center justify-between border-t border-border pt-3">
        <p className={cn("num font-mono text-[13px]", Math.abs(total - 100) < 0.01 ? "text-green" : "text-red")}>Total {total} / 100</p>
        <div className="flex items-center gap-2">
          {save.isError ? <span className="text-[12px] text-red">{(save.error as Error).message}</span> : null}
          {save.isSuccess ? <Badge tone="green">Saved</Badge> : null}
          <Button size="sm" variant="amber" disabled={Math.abs(total - 100) > 0.01} loading={save.isPending} onClick={() => save.mutate(w)}>
            <Save className="size-3.5" aria-hidden /> Save weights
          </Button>
        </div>
      </div>
    </div>
  );
}

function Thresholds({ initial }: { initial: Record<string, number> }) {
  const [t, setT] = React.useState(initial);
  const save = useSave("priority_thresholds");
  return (
    <div className="flex flex-col gap-3">
      {["CRITICAL", "HIGH", "MEDIUM"].map((k) => (
        <div key={k} className="grid grid-cols-[1fr_90px] items-center gap-3">
          <label htmlFor={`t-${k}`} className="text-[13px] text-fg-2">
            {k} ≥
          </label>
          <Input id={`t-${k}`} type="number" min={1} max={100} value={t[k]} onChange={(e) => setT({ ...t, [k]: Number(e.target.value) })} className="h-8 text-right font-mono" />
        </div>
      ))}
      <div className="flex items-center justify-end gap-2 border-t border-border pt-3">
        {save.isError ? <span className="text-[12px] text-red">{(save.error as Error).message}</span> : null}
        {save.isSuccess ? <Badge tone="green">Saved</Badge> : null}
        <Button size="sm" variant="amber" loading={save.isPending} onClick={() => save.mutate(t)}>
          <Save className="size-3.5" aria-hidden /> Save thresholds
        </Button>
      </div>
    </div>
  );
}

function EngineSettings({ s }: { s: SettingsOut["engine"] }) {
  const clf = useSave("use_classifier");
  const cls = useSave("sif_potential_classes");
  const [classes, setClasses] = React.useState(s.sif_potential_classes);
  return (
    <div className="flex flex-col gap-4">
      <label className="flex items-center justify-between gap-3">
        <span>
          <span className="block text-[13px] text-fg">Classifier second opinion</span>
          <span className="block text-[12px] text-muted">TF-IDF + Logistic Regression; disagreements route to review</span>
        </span>
        <input type="checkbox" checked={s.use_classifier} onChange={(e) => clf.mutate(e.target.checked)} className="size-4 accent-cyan" />
      </label>
      <fieldset>
        <legend className="text-[13px] text-fg">SIF-potential definition</legend>
        <p className="mb-2 text-[12px] text-muted">SCL classes counted as SIF-potential (prototype default: PSIF + Exposure)</p>
        <div className="flex flex-wrap gap-2">
          {["HSIF", "PSIF", "EXPOSURE", "CAPACITY", "SUCCESS", "LSIF", "LOW_SEVERITY"].map((c) => (
            <label key={c} className={cn("flex cursor-pointer items-center gap-1.5 rounded-xs border px-2 py-1 text-[12px]", classes.includes(c) ? "border-red/50 bg-red/10 text-fg" : "border-border text-fg-2")}>
              <input type="checkbox" className="accent-red" checked={classes.includes(c)} onChange={(e) => setClasses(e.target.checked ? [...classes, c] : classes.filter((x) => x !== c))} />
              {SCL_META[c].label}
            </label>
          ))}
        </div>
        <div className="mt-2 flex justify-end">
          <Button size="sm" variant="amber" disabled={JSON.stringify([...classes].sort()) === JSON.stringify([...s.sif_potential_classes].sort()) || !classes.length} loading={cls.isPending} onClick={() => cls.mutate(classes)}>
            Save definition
          </Button>
        </div>
      </fieldset>
      <dl className="grid grid-cols-2 gap-3 border-t border-border pt-3">
        <KV k="Recurrence window" v={`${s.recurrence_window_days} days`} />
        <KV k="Min pattern size" v={`${s.pattern_min_cluster_size} reports`} />
        <KV k="Low-confidence threshold" v={s.review_thresholds.low_confidence} />
        <KV k="Borderline gate threshold" v={s.review_thresholds.borderline_gate} />
      </dl>
    </div>
  );
}

export default function SettingsPage() {
  const q = useQuery({ queryKey: ["settings"], queryFn: () => api<SettingsOut>("/settings") });
  return (
    <RequirePermission perm="settings">
      <PageHeader eyebrow="Administration / configuration" title="Settings" subtitle="Engine configuration, scoring model, data mode and system information. Changes apply to new analyses and are audited." />
      {q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : !q.data ? (
        <LoadingState rows={8} />
      ) : (
        <div className="flex flex-col gap-5">
          {q.data.environment.label ? (
            <Notice tone="amber" title={q.data.environment.label}>
              All reports, sites, exposure hours and contractors in this environment are synthetic. No OIL production data is present.
            </Notice>
          ) : null}
          <div className="grid gap-5 xl:grid-cols-3">
            <Panel title="Analysis engine" id="s-engine">
              <EngineSettings s={q.data.engine} />
            </Panel>
            <Panel title="Scoring model" subtitle="100-point priority weights (must total 100)" id="s-weights">
              <Weights initial={q.data.engine.priority_weights} />
            </Panel>
            <Panel title="Priority levels" subtitle="Score thresholds" id="s-thresh">
              <Thresholds initial={q.data.engine.priority_thresholds} />
            </Panel>
          </div>
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
            <Panel title="Data mode" id="s-data">
              <dl className="flex flex-col gap-3">
                <KV k="Mode" v={<Badge tone="amber">{q.data.environment.data_mode}</Badge>} />
                <KV k="Reports" v={`${q.data.database.counts.reports} (${q.data.database.counts.synthetic_reports} synthetic)`} />
              </dl>
            </Panel>
            <Panel title="Environment" id="s-env">
              <dl className="flex flex-col gap-3">
                <KV k="Environment" v={<Badge tone="amber">{q.data.environment.demo_mode ? "Demo environment" : q.data.environment.environment}</Badge>} />
                <KV k="External AI services" v="None — fully local" />
              </dl>
            </Panel>
            <Panel title="Database" id="s-db">
              <dl className="flex flex-col gap-3">
                <KV k="Engine" v={q.data.database.dialect} />
                <KV k="Vector search" v={q.data.database.pgvector ? "pgvector enabled" : "JSON fallback"} />
                <KV k="Decisions / audit events" v={`${q.data.database.counts.decisions} / ${q.data.database.counts.audit_events}`} />
              </dl>
            </Panel>
            <Panel title="Model version" id="s-model">
              <dl className="flex flex-col gap-3">
                {Object.entries(q.data.models).map(([k, v]) => (
                  <KV key={k} k={k.replace(/_/g, " ")} v={v} mono />
                ))}
              </dl>
            </Panel>
          </div>
          <div className="grid gap-5 md:grid-cols-2">
            <Panel title="Security" id="s-sec">
              <dl className="grid grid-cols-2 gap-3">
                <KV k="Authentication" v={q.data.security.auth} />
                <KV k="Passwords" v={q.data.security.password_hashing} />
                <KV k="Roles" v={q.data.security.roles.join(", ")} />
                <KV k="Session length" v={`${q.data.security.token_minutes / 60} h`} />
              </dl>
            </Panel>
            <Panel title="Audit" id="s-audit" actions={<Link href="/audit" className="text-[12px] text-cyan hover:underline">Open audit log</Link>}>
              <p className="mb-2 text-[12.5px] text-fg-2">Recorded event types:</p>
              <ul className="flex flex-wrap gap-1.5">
                {q.data.audit.event_types.map((e) => (
                  <li key={e}>
                    <Badge>{e}</Badge>
                  </li>
                ))}
              </ul>
            </Panel>
          </div>
        </div>
      )}
    </RequirePermission>
  );
}
