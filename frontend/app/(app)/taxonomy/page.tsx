"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FlaskConical, Plus, Save, X } from "lucide-react";
import * as React from "react";

import { RequirePermission } from "@/components/shell/RequirePermission";
import { LSR_ICON } from "@/components/ui/badges";
import { Badge, Button, ErrorState, Input, LoadingState, Notice, PageHeader, Panel, Textarea } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { cn, fmtDateTime } from "@/lib/format";
import type { Mapping } from "@/lib/types";

interface Rule {
  id: number;
  code: string;
  rule_number: number | null;
  name: string;
  description: string;
  keywords: string[];
  phrases: string[];
  weight: number;
  is_active: boolean;
  is_fallback: boolean;
  updated_at: string;
  updated_by: string | null;
}

function TermEditor({ id, label, terms, onChange }: { id: string; label: string; terms: string[]; onChange: (t: string[]) => void }) {
  const [draft, setDraft] = React.useState("");
  const add = () => {
    const t = draft.trim();
    if (t && !terms.some((x) => x.toLowerCase() === t.toLowerCase())) onChange([...terms, t]);
    setDraft("");
  };
  return (
    <div>
      <label htmlFor={id} className="label-tech mb-1.5 block">
        {label} <span className="num text-muted">({terms.length})</span>
      </label>
      <ul className="mb-2 flex flex-wrap gap-1.5">
        {terms.map((t) => (
          <li key={t} className="flex items-center gap-1 rounded-xs border border-border bg-bg px-1.5 py-0.5 text-[12px] text-fg-2">
            {t}
            <button type="button" onClick={() => onChange(terms.filter((x) => x !== t))} className="text-muted hover:text-red" aria-label={`Remove ${t}`}>
              <X className="size-3" />
            </button>
          </li>
        ))}
      </ul>
      <div className="flex gap-2">
        <Input
          id={id}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
          placeholder={`Add ${label.toLowerCase().replace(/s$/, "")}…`}
          className="h-8 text-[12.5px]"
        />
        <Button type="button" size="sm" onClick={add} aria-label={`Add ${label}`}>
          <Plus className="size-3.5" />
        </Button>
      </div>
    </div>
  );
}

function RuleCard({ rule }: { rule: Rule }) {
  const qc = useQueryClient();
  const [kw, setKw] = React.useState(rule.keywords);
  const [ph, setPh] = React.useState(rule.phrases);
  const [weight, setWeight] = React.useState(rule.weight);
  const [active, setActive] = React.useState(rule.is_active);
  const dirty = JSON.stringify([kw, ph, weight, active]) !== JSON.stringify([rule.keywords, rule.phrases, rule.weight, rule.is_active]);
  const Icon = LSR_ICON[rule.code];
  const save = useMutation({
    mutationFn: () => api<Rule>(`/taxonomy/${rule.code}`, { method: "PUT", json: { keywords: kw, phrases: ph, weight, is_active: active } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["taxonomy"] }),
  });
  return (
    <article className={cn("flex flex-col gap-4 rounded-md border bg-surface p-4", active ? "border-border" : "border-dashed border-border opacity-75")} aria-labelledby={`rule-${rule.code}`}>
      <header className="flex items-start gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-sm border border-border bg-bg">{Icon ? <Icon className="size-4.5 text-cyan" aria-hidden /> : null}</span>
        <div className="min-w-0 flex-1">
          <p className="font-mono text-[10.5px] uppercase tracking-wider text-muted">{rule.rule_number ? `Life-Saving Rule ${rule.rule_number}` : "Fallback bucket"}</p>
          <h2 id={`rule-${rule.code}`} className="text-[15px] font-semibold">
            {rule.name}
          </h2>
          <p className="mt-1 text-[12.5px] text-fg-2">{rule.description}</p>
        </div>
        <label className={cn("flex shrink-0 cursor-pointer items-center gap-2 text-[12px]", rule.is_fallback && "cursor-not-allowed opacity-60")}>
          <input type="checkbox" className="peer sr-only" checked={active} disabled={rule.is_fallback} onChange={(e) => setActive(e.target.checked)} />
          <span className="relative h-5 w-9 rounded-full border border-border-strong bg-surface-3 transition-colors peer-checked:border-green/60 peer-checked:bg-green/30 peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-cyan after:absolute after:left-0.5 after:top-0.5 after:size-3.5 after:rounded-full after:bg-fg-2 after:transition-transform peer-checked:after:translate-x-4 peer-checked:after:bg-green" aria-hidden />
          <span className={active ? "text-green" : "text-muted"}>{active ? "Active" : "Inactive"}</span>
        </label>
      </header>
      <TermEditor id={`kw-${rule.code}`} label="Keywords" terms={kw} onChange={setKw} />
      <TermEditor id={`ph-${rule.code}`} label="Phrases" terms={ph} onChange={setPh} />
      <div>
        <label htmlFor={`w-${rule.code}`} className="label-tech mb-1.5 flex justify-between">
          <span>Weight</span>
          <span className="num font-mono text-fg">{weight.toFixed(2)}×</span>
        </label>
        <input id={`w-${rule.code}`} type="range" min={0.1} max={3} step={0.05} value={weight} onChange={(e) => setWeight(Number(e.target.value))} className="w-full accent-cyan" />
      </div>
      <footer className="flex items-center justify-between gap-2 border-t border-border pt-3">
        <p className="text-[11.5px] text-muted">
          Updated {fmtDateTime(rule.updated_at)} by {rule.updated_by ?? "—"}
        </p>
        <div className="flex items-center gap-2">
          {save.isError ? <span className="text-[12px] text-red">{(save.error as Error).message}</span> : null}
          {save.isSuccess && !dirty ? <Badge tone="green">Saved</Badge> : null}
          <Button size="sm" variant={dirty ? "amber" : "secondary"} disabled={!dirty} loading={save.isPending} onClick={() => save.mutate()}>
            <Save className="size-3.5" aria-hidden /> Save
          </Button>
        </div>
      </footer>
    </article>
  );
}

function TestConsole() {
  const [text, setText] = React.useState("Welder started grinding near the separator without a hot work permit; the gas detector had been removed.");
  const m = useMutation({ mutationFn: () => api<Mapping>("/taxonomy/test", { method: "POST", json: { text } }) });
  return (
    <Panel title="Test mapping" subtitle="Run the deterministic mapper on any text with the current taxonomy" id="test" accent="cyan">
      <div className="flex flex-col gap-3">
        <label htmlFor="test-text" className="sr-only">
          Text to map
        </label>
        <Textarea id="test-text" value={text} onChange={(e) => setText(e.target.value)} className="min-h-20" />
        <div className="flex justify-end">
          <Button onClick={() => m.mutate()} loading={m.isPending} disabled={text.trim().length < 5}>
            <FlaskConical className="size-4" aria-hidden /> Test
          </Button>
        </div>
        {m.data ? (
          <div className="flex flex-col gap-2 rounded-sm border border-border bg-bg/60 p-3">
            <p className="text-[13px]">
              Primary: <span className="font-semibold text-fg">{m.data.primary.name}</span> <span className="num font-mono text-[12px] text-muted">conf {m.data.confidence.toFixed(2)}</span>
            </p>
            <ul className="flex flex-col gap-1">
              {m.data.candidates.map((c) => (
                <li key={c.code} className="flex items-center justify-between text-[12px] text-fg-2">
                  <span>{c.name}</span>
                  <span className="num font-mono">{c.score.toFixed(1)}</span>
                </li>
              ))}
            </ul>
            <p className="text-[11.5px] text-muted">
              {m.data.label} — {m.data.disclaimer}
            </p>
          </div>
        ) : null}
        {m.isError ? <p className="text-[12.5px] text-red">{(m.error as Error).message}</p> : null}
      </div>
    </Panel>
  );
}

export default function TaxonomyPage() {
  const q = useQuery({ queryKey: ["taxonomy"], queryFn: () => api<{ items: Rule[]; warning: string; label: string; disclaimer: string }>("/taxonomy") });
  return (
    <RequirePermission perm="taxonomy">
      <PageHeader eyebrow="Administration / IOGP Life-Saving Rules" title="Taxonomy" subtitle="Keywords, phrases and weights used by the deterministic rule mapper. The nine IOGP Life-Saving Rules plus a process-safety / no-applicable-rule bucket." />
      <Notice tone="amber" title="Taxonomy changes affect the deterministic analysis engine." className="mb-5">
        Changes apply to new analyses immediately and are recorded in the audit log. Use Model / Analysis → “Re-analyse all” to apply them to existing reports. The rule mapping is a <strong>proposed IOGP LSR crosswalk</strong> requiring independent HSE expert validation; it is not an official IOGP or OIL mapping and does not decide the SIF classification.
      </Notice>
      {q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : !q.data ? (
        <LoadingState rows={8} />
      ) : (
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
          <div className="grid gap-4 lg:grid-cols-2">
            {q.data.items.map((r) => (
              <RuleCard key={`${r.code}-${r.updated_at}`} rule={r} />
            ))}
          </div>
          <div className="xl:sticky xl:top-20 xl:self-start">
            <TestConsole />
          </div>
        </div>
      )}
    </RequirePermission>
  );
}
