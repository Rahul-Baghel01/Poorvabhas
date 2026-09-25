"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, Cpu, RefreshCw } from "lucide-react";
import * as React from "react";

import { Badge, Button, ErrorState, LoadingState, Notice, PageHeader, Panel } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useInvalidateAll } from "@/lib/hooks";
import { cn, fmtDateTime, pct } from "@/lib/format";

interface Binary {
  n: number;
  accuracy: number;
  precision: number;
  recall: number;
  f1: number;
  roc_auc?: number;
  positives: number;
  confusion_matrix: { labels: string[]; matrix: number[][] };
}
interface Version {
  version: string;
  component: string;
  algorithm: string;
  params: Record<string, unknown>;
  metrics: Record<string, unknown> | null;
  evaluation_basis: string | null;
  n_train: number | null;
  n_test: number | null;
  is_active: boolean;
  notes: string | null;
  created_at: string;
}
interface Status {
  engine: { name: string; version: string; external_llm: boolean; stages: { key: string; label: string }[] };
  components: { key: string; name: string; status: string; detail: string }[];
  versions: Version[];
  feedback: { total: number; corrections: number; not_yet_used_for_training: number };
  human_review_evaluation: { status: string; n: number; required?: number; message?: string } & Partial<Binary> & { basis?: string };
}

function MetricGrid({ m }: { m: Binary }) {
  const cells: [string, number | undefined][] = [
    ["Accuracy", m.accuracy],
    ["Precision", m.precision],
    ["Recall", m.recall],
    ["F1", m.f1],
    ["ROC AUC", m.roc_auc],
  ];
  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
        {cells
          .filter(([, v]) => v !== undefined)
          .map(([k, v]) => (
            <div key={k} className="rounded-sm border border-border bg-bg/60 px-2.5 py-2">
              <p className="label-tech">{k}</p>
              <p className="num mt-0.5 font-mono text-[18px] text-fg">{(v as number).toFixed(3)}</p>
            </div>
          ))}
      </div>
      <div className="flex flex-wrap items-center gap-4">
        <table className="text-[12px]" aria-label="Confusion matrix">
          <thead>
            <tr>
              <th scope="col" className="p-1" />
              {m.confusion_matrix.labels.map((l) => (
                <th key={l} scope="col" className="label-tech px-2 py-1 font-normal">
                  pred. {l}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {m.confusion_matrix.matrix.map((row, i) => (
              <tr key={i}>
                <th scope="row" className="label-tech px-2 py-1 text-left font-normal">
                  true {m.confusion_matrix.labels[i]}
                </th>
                {row.map((v, j) => (
                  <td key={j} className={cn("num border border-border px-3 py-1.5 text-center font-mono", i === j ? "bg-green/10 text-green" : v ? "bg-red/10 text-red" : "text-muted")}>
                    {v}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        <p className="text-[12px] text-muted">
          n = {m.n} · {m.positives} SIF-potential
        </p>
      </div>
    </div>
  );
}

const FEEDBACK_FLOW = ["Prediction", "Confidence check", "Human review", "Correction", "Feedback example", "Dataset improvement", "Controlled retraining"];

export default function ModelPage() {
  const { can } = useAuth();
  const invalidate = useInvalidateAll();
  const q = useQuery({ queryKey: ["model"], queryFn: () => api<Status>("/model/status") });
  const train = useMutation({ mutationFn: () => api("/model/train", { method: "POST" }), onSuccess: () => invalidate() });
  const reanalyze = useMutation({ mutationFn: () => api<{ reanalyzed: number }>("/model/reanalyze-all", { method: "POST" }), onSuccess: () => invalidate() });

  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!q.data) return <LoadingState rows={10} />;
  const s = q.data;
  const clf = s.versions.find((v) => v.component === "sif_classifier" && v.is_active);
  const engine = s.versions.find((v) => v.component === "deterministic_engine");
  const history = s.versions.filter((v) => v.component === "sif_classifier");
  const eh = engine?.metrics?.synthetic_holdout as Record<string, unknown> | undefined;
  const hre = s.human_review_evaluation;

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        eyebrow="Administration / analysis engine"
        title="Model / analysis"
        subtitle="What the engine is made of, which versions are active, and only the metrics that have actually been computed."
        actions={
          can("model") ? (
            <>
              <Button onClick={() => reanalyze.mutate()} loading={reanalyze.isPending}>
                <RefreshCw className="size-4" aria-hidden /> Re-analyse all
              </Button>
              <Button variant="primary" onClick={() => train.mutate()} loading={train.isPending}>
                <Cpu className="size-4" aria-hidden /> Retrain classifier
              </Button>
            </>
          ) : null
        }
      />
      {train.isSuccess ? <Notice tone="green" title="Classifier retrained">A new version was trained on synthetic reference labels plus human feedback and activated. Existing analyses keep the version that produced them.</Notice> : null}
      {reanalyze.data ? <Notice tone="green" title="Re-analysis complete">{reanalyze.data.reanalyzed} reports re-analysed; human decisions were preserved.</Notice> : null}
      {train.isError || reanalyze.isError ? <Notice tone="red">{((train.error || reanalyze.error) as Error).message}</Notice> : null}

      <Panel title="Analysis engine" id="engine">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-[22px] font-semibold">{s.engine.name}</p>
            <p className="mt-1 font-mono text-[12px] text-fg-2">
              {s.engine.version} · runs fully locally · external LLM: <span className="text-green">none</span>
            </p>
          </div>
          <Badge tone="green" dot>
            Operational
          </Badge>
        </div>
        <ol className="mt-4 flex flex-wrap items-center gap-1.5" aria-label="Pipeline stages">
          {s.engine.stages.map((st, i) => (
            <li key={st.key} className="flex items-center gap-1.5">
              <span className="rounded-xs border border-border bg-bg px-2 py-1 font-mono text-[10.5px] uppercase tracking-wider text-fg-2">{st.label}</span>
              {i < s.engine.stages.length - 1 ? <ArrowRight className="size-3 text-muted" aria-hidden /> : null}
            </li>
          ))}
        </ol>
      </Panel>

      <Panel title="Components" id="components">
        <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {s.components.map((c) => (
            <li key={c.key} className="rounded-sm border border-border bg-bg/50 p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="text-[13.5px] font-medium text-fg">{c.name}</p>
                <Badge tone={c.status === "active" || c.status === "installed" ? "green" : c.status === "unavailable" ? "amber" : "neutral"}>{c.status}</Badge>
              </div>
              <p className="mt-1.5 text-[12px] leading-snug text-fg-2">{c.detail}</p>
            </li>
          ))}
        </ul>
      </Panel>

      <Notice tone="amber" title="How to read these metrics">
        All figures below are computed on the <strong>synthetic</strong> demo dataset against reference labels assigned by scenario design. They show the pipeline works end to end. They are <strong>not</strong> an estimate of real-world accuracy on OIL reports, which requires a labelled pilot dataset reviewed by HSE experts.
      </Notice>

      <div className="grid gap-5 xl:grid-cols-2">
        <Panel title="Deterministic SCL engine" subtitle={engine ? `${engine.version} · ${engine.algorithm}` : undefined} id="engine-eval" accent="red">
          {eh ? (
            <div className="flex flex-col gap-4">
              <div className="grid grid-cols-3 gap-2">
                <div className="rounded-sm border border-border bg-bg/60 px-2.5 py-2">
                  <p className="label-tech">Coverage</p>
                  <p className="num mt-0.5 font-mono text-[18px]">{pct(eh.coverage as number, 1)}</p>
                  <p className="text-[11px] text-muted">decided without review</p>
                </div>
                <div className="rounded-sm border border-border bg-bg/60 px-2.5 py-2">
                  <p className="label-tech">SCL agreement</p>
                  <p className="num mt-0.5 font-mono text-[18px]">{pct((eh.scl_class_agreement as { agreement: number })?.agreement, 1)}</p>
                  <p className="text-[11px] text-muted">n={(eh.scl_class_agreement as { n: number })?.n}</p>
                </div>
                <div className="rounded-sm border border-border bg-bg/60 px-2.5 py-2">
                  <p className="label-tech">LSR top-1</p>
                  <p className="num mt-0.5 font-mono text-[18px]">{pct((eh.lsr_top1_agreement as { agreement: number })?.agreement, 1)}</p>
                  <p className="text-[11px] text-muted">n={(eh.lsr_top1_agreement as { n: number })?.n}</p>
                </div>
              </div>
              <p className="text-[12.5px] text-fg-2">
                {String(eh.abstained_to_review)} of {String(eh.n_labelled)} held-out labelled reports were routed to human review instead of being decided (abstention by design). SIF-potential agreement on decided reports:
              </p>
              {eh.sif_potential_on_decided ? <MetricGrid m={eh.sif_potential_on_decided as Binary} /> : <p className="text-muted">Evaluation pending</p>}
              <p className="text-[11.5px] leading-relaxed text-muted">{engine?.evaluation_basis}</p>
            </div>
          ) : (
            <p className="text-[13px] text-muted">Evaluation pending</p>
          )}
        </Panel>

        <Panel title="SIF classifier (second opinion)" subtitle={clf ? `${clf.version} · ${clf.algorithm}` : "Not trained"} id="clf-eval" accent="cyan">
          {clf?.metrics ? (
            <div className="flex flex-col gap-4">
              <div>
                <p className="label-tech mb-2">Synthetic held-out split (n={clf.n_test})</p>
                <MetricGrid m={clf.metrics.synthetic_holdout as Binary} />
              </div>
              <div>
                <p className="label-tech mb-2">5-fold out-of-fold on training split (n={clf.n_train})</p>
                <MetricGrid m={clf.metrics.cross_validation_oof as Binary} />
              </div>
              <p className="text-[11.5px] leading-relaxed text-muted">{clf.evaluation_basis}</p>
              <p className="text-[11.5px] text-muted">{clf.notes}</p>
            </div>
          ) : (
            <p className="text-[13px] text-muted">{clf ? "Evaluation pending" : "No classifier trained — the deterministic engine runs alone."}</p>
          )}
        </Panel>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Panel title="Human-review evaluation" subtitle="Engine vs HSE reviewer decisions" id="human-eval" accent="amber">
          {hre.status === "pending" ? (
            <div>
              <p className="font-mono text-[18px] text-amber">Evaluation pending</p>
              <p className="mt-1 text-[12.5px] text-fg-2">{hre.message}</p>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              <MetricGrid m={hre as unknown as Binary} />
              <p className="text-[11.5px] text-muted">{hre.basis}</p>
            </div>
          )}
        </Panel>
        <Panel title="Model feedback loop" subtitle="Corrections are stored for controlled retraining — never auto-retrained per decision" id="feedback">
          <ol className="flex flex-wrap items-center gap-1.5">
            {FEEDBACK_FLOW.map((f, i) => (
              <li key={f} className="flex items-center gap-1.5">
                <span className="rounded-xs border border-border bg-bg px-2 py-1 text-[11.5px] text-fg-2">{f}</span>
                {i < FEEDBACK_FLOW.length - 1 ? <ArrowRight className="size-3 text-muted" aria-hidden /> : null}
              </li>
            ))}
          </ol>
          <div className="mt-4 grid grid-cols-3 gap-2">
            <div className="rounded-sm border border-border bg-bg/60 px-2.5 py-2">
              <p className="label-tech">Feedback examples</p>
              <p className="num font-mono text-[20px]">{s.feedback.total}</p>
            </div>
            <div className="rounded-sm border border-border bg-bg/60 px-2.5 py-2">
              <p className="label-tech">Corrections</p>
              <p className="num font-mono text-[20px] text-amber">{s.feedback.corrections}</p>
            </div>
            <div className="rounded-sm border border-border bg-bg/60 px-2.5 py-2">
              <p className="label-tech">Awaiting retrain</p>
              <p className="num font-mono text-[20px]">{s.feedback.not_yet_used_for_training}</p>
            </div>
          </div>
        </Panel>
      </div>

      <Panel title="Model versions" id="versions">
        <div className="-mx-4 overflow-x-auto px-4">
          <table className="w-full min-w-[760px] text-[12.5px]">
            <thead>
              <tr className="border-b border-border text-left">
                {["Version", "Component", "Algorithm", "Train n", "Created", "Status"].map((h) => (
                  <th key={h} scope="col" className="label-tech py-2 pr-3 font-normal">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[...(engine ? [engine] : []), ...history, ...s.versions.filter((v) => v.component === "embedder")].map((v) => (
                <tr key={v.version} className="border-b border-border/60">
                  <td className="py-2 pr-3 font-mono text-fg">{v.version}</td>
                  <td className="py-2 pr-3 text-fg-2">{v.component.replace(/_/g, " ")}</td>
                  <td className="py-2 pr-3 text-fg-2">{v.algorithm}</td>
                  <td className="num py-2 pr-3 font-mono text-fg-2">{v.n_train ?? "—"}</td>
                  <td className="py-2 pr-3 text-fg-2">{fmtDateTime(v.created_at)}</td>
                  <td className="py-2">{v.is_active ? <Badge tone="green">Active</Badge> : <Badge>Retired</Badge>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
