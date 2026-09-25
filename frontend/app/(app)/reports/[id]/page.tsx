"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ClipboardCheck, FileX, History, Network, RefreshCw, Send, X } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import * as React from "react";

import { LsrTag, PriorityBadge, SifBadge, StatusBadge } from "@/components/ui/badges";
import { FadeIn } from "@/components/ui/motion";
import { Badge, Button, EmptyState, ErrorState, KV, LoadingState, Notice, Panel, Textarea } from "@/components/ui/primitives";
import { ConfidenceBreakdown, MappingPanel, PipelineTrace, PriorityBreakdown } from "@/components/report/Breakdowns";
import { DecisionForm, type DecisionPayload } from "@/components/report/DecisionForm";
import { EvidenceLegend, EvidenceText } from "@/components/report/EvidenceText";
import { ExtractionTable } from "@/components/report/ExtractionTable";
import { SclGates } from "@/components/report/SclGates";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useInvalidateAll } from "@/lib/hooks";
import { SCL_META, fmtDate, fmtDateTime } from "@/lib/format";
import type { ReportDetail, ReportRow } from "@/lib/types";

function SendToReview({ reportId, onDone }: { reportId: string; onDone: () => void }) {
  const [open, setOpen] = React.useState(false);
  const [reason, setReason] = React.useState("");
  const m = useMutation({
    mutationFn: () => api(`/reports/${reportId}/request-review`, { method: "POST", json: { reason } }),
    onSuccess: () => {
      setOpen(false);
      setReason("");
      onDone();
    },
  });
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <Button size="sm">
          <Send className="size-3.5" aria-hidden /> Send to reviewer
        </Button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/70" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(92vw,480px)] -translate-x-1/2 -translate-y-1/2 rounded-md border border-border bg-surface p-5">
          <Dialog.Title className="text-[16px] font-semibold">Send to HSE reviewer</Dialog.Title>
          <Dialog.Description className="mt-1 text-[13px] text-fg-2">The report enters the review queue as a manual request. The reviewer decides the final classification.</Dialog.Description>
          <form
            className="mt-4 flex flex-col gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              m.mutate();
            }}
          >
            <label htmlFor="rr-reason" className="label-tech">
              Reason for review
            </label>
            <Textarea id="rr-reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Borderline — confirm whether the barricade was effective" required minLength={3} />
            {m.error ? <p className="text-[12.5px] text-red">{(m.error as Error).message}</p> : null}
            <div className="flex justify-end gap-2">
              <Dialog.Close asChild>
                <Button type="button" variant="ghost">
                  Cancel
                </Button>
              </Dialog.Close>
              <Button type="submit" variant="amber" loading={m.isPending} disabled={reason.trim().length < 3}>
                Send to reviewer
              </Button>
            </div>
          </form>
          <Dialog.Close className="absolute right-3 top-3 rounded-sm p-1 text-muted hover:text-fg" aria-label="Close">
            <X className="size-4" />
          </Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export default function ReportDetailPage() {
  const { id } = useParams<{ id: string }>();
  const reportId = decodeURIComponent(id);
  const qc = useQueryClient();
  const invalidate = useInvalidateAll();
  const { can } = useAuth();
  const [focus, setFocus] = React.useState<string | null>(null);
  const [showTrace, setShowTrace] = React.useState(false);

  const q = useQuery({ queryKey: ["report", reportId], queryFn: () => api<ReportDetail>(`/reports/${encodeURIComponent(reportId)}`) });
  const similar = useQuery({ queryKey: ["similar", reportId], queryFn: () => api<{ method: string; items: (ReportRow & { similarity: number })[] }>(`/reports/${encodeURIComponent(reportId)}/similar?k=5`), enabled: !!q.data });

  const onChanged = React.useCallback(
    (data?: ReportDetail) => {
      if (data) qc.setQueryData(["report", reportId], data);
      else qc.invalidateQueries({ queryKey: ["report", reportId] });
      invalidate();
    },
    [qc, reportId, invalidate],
  );

  const reanalyze = useMutation({ mutationFn: () => api<{ detail: ReportDetail }>(`/reports/${encodeURIComponent(reportId)}/reanalyze`, { method: "POST" }), onSuccess: (r) => onChanged(r.detail) });
  const decide = useMutation({ mutationFn: (p: DecisionPayload) => api<ReportDetail>(`/reports/${encodeURIComponent(reportId)}/decision`, { method: "POST", json: p }), onSuccess: (d) => onChanged(d) });

  if (q.isError) {
    return q.error instanceof ApiError && q.error.status === 404 ? (
      <EmptyState icon={FileX} title={`Report ${reportId} not found`} action={<Link href="/reports" className="text-cyan hover:underline">Back to registry</Link>} />
    ) : (
      <ErrorState error={q.error} onRetry={() => q.refetch()} />
    );
  }
  if (!q.data) return <LoadingState rows={10} label="Loading report" />;

  const { report: r, analysis: a } = q.data;
  const human = r.decision_source === "HUMAN";

  return (
    <div className="flex flex-col gap-5">
      {/* header */}
      <FadeIn>
        <Link href="/reports" className="mb-3 inline-flex items-center gap-1.5 text-[12.5px] text-muted hover:text-fg">
          <ArrowLeft className="size-3.5" aria-hidden /> Safety reports
        </Link>
        <div className="flex flex-col gap-4 border-b border-border pb-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="label-tech">
              {r.report_type} · {fmtDate(r.date)} · {r.is_synthetic ? "synthetic demo record" : r.data_source.replace("_", " ")}
            </p>
            <h1 className="mt-1.5 font-mono text-[28px] font-semibold tracking-tight md:text-[32px]">{r.report_id}</h1>
            <div className="mt-2.5 flex flex-wrap items-center gap-2">
              <SifBadge signal={r.sif_signal} />
              <StatusBadge status={r.status} />
              <PriorityBadge level={r.priority_level} score={r.priority_score} />
              {human ? <Badge tone="green">Final decision: HSE reviewer</Badge> : <Badge tone="cyan">Final decision: pending human validation</Badge>}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {can("review") && !q.data.review ? <SendToReview reportId={r.report_id} onDone={() => onChanged()} /> : null}
            {can("analysis") ? (
              <Button size="sm" onClick={() => reanalyze.mutate()} loading={reanalyze.isPending}>
                <RefreshCw className="size-3.5" aria-hidden /> Re-analyse
              </Button>
            ) : null}
          </div>
        </div>
        <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4 xl:grid-cols-8">
          <KV k="Site" v={r.site} />
          <KV k="Location" v={r.location} />
          <KV k="Activity" v={r.activity} />
          <KV k="Equipment" v={r.equipment} />
          <KV k="Worker role" v={r.worker_role} />
          <KV k="Contractor" v={r.contractor} />
          <KV k="Injury severity" v={r.injury_severity} />
          <KV k="Shift / weather" v={[r.shift, r.weather].filter(Boolean).join(" · ") || null} />
        </dl>
      </FadeIn>

      {human && a && (a.sif_signal !== r.sif_signal || a.scl.scl_class !== r.scl_class || a.mapping.primary.code !== r.primary_lsr) ? (
        <Notice tone="green" title="Reviewer decision overrides the AI analysis">
          Current decision: {SCL_META[r.scl_class ?? ""]?.label ?? r.scl_class} · {r.sif_signal?.replace("_", " ").toLowerCase()} · {r.lsr_name}. The AI output below is preserved for traceability.
        </Notice>
      ) : null}

      {!a ? (
        <Panel>
          <EmptyState title="Analysis unavailable" description="This report has not been analysed yet." action={<Button onClick={() => reanalyze.mutate()}>Analyse now</Button>} />
        </Panel>
      ) : (
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
          <div className="flex min-w-0 flex-col gap-5">
            <Panel title="Original report" subtitle="Highlighted spans are the evidence the engine used" id="orig" actions={<EvidenceLegend />}>
              <EvidenceText text={r.description} entities={a.entities} focus={focus} />
              <div className="mt-4 rounded-sm border border-border bg-bg/60 px-3 py-2.5">
                <p className="label-tech mb-1">Reasoning summary</p>
                <p className="text-[13px] leading-relaxed text-fg-2">{a.reasoning_summary}</p>
              </div>
            </Panel>

            <Panel title="NLP extraction" subtitle="Every value with its source span and confidence. Nothing is invented; missing facts are reported as Not stated." id="nlp">
              <ExtractionTable entities={a.entities} notStated={a.not_stated} onFocus={setFocus} focus={focus} />
            </Panel>

            <Panel title="SCL decision" subtitle="Judge the hazard, not the outcome — four evidence gates resolve the Safety Classification and Learning class" id="scl" accent="red">
              <SclGates analysis={a} />
            </Panel>

            <Panel title="IOGP Life-Saving Rule mapping" subtitle="Proposed crosswalk" id="iogp" accent="cyan">
              <MappingPanel analysis={a} />
            </Panel>

            <Panel
              title="Analysis pipeline"
              subtitle={`Engine ${a.model_version} · analysed ${fmtDateTime(a.created_at)} · ${q.data.analysis_count} analysis run(s)`}
              id="trace"
              actions={
                <Button size="sm" variant="ghost" onClick={() => setShowTrace((s) => !s)} aria-expanded={showTrace}>
                  {showTrace ? "Hide" : "Show"} trace
                </Button>
              }
              bodyClassName={showTrace ? "p-4" : "hidden"}
            >
              {showTrace ? <PipelineTrace trace={a.pipeline_trace} /> : null}
            </Panel>
          </div>

          <aside className="flex min-w-0 flex-col gap-5" aria-label="Decision support">
            <Panel title="Review status" id="review" accent={q.data.review ? "amber" : human ? "green" : undefined}>
              {q.data.review ? (
                <div className="flex flex-col gap-3">
                  <div>
                    <Badge tone="amber">{q.data.review.category_label}</Badge>
                    <ul className="mt-2 flex flex-col gap-1.5">
                      {q.data.review.reasons.map((x, i) => (
                        <li key={i} className="text-[12.5px] text-fg-2">
                          <span className="text-amber">{x.label}:</span> {x.detail}
                        </li>
                      ))}
                    </ul>
                    <p className="mt-2 text-[12px] text-muted">Suggested action: {q.data.review.suggested_action}</p>
                  </div>
                  {can("review") ? (
                    <div className="border-t border-border pt-3">
                      <DecisionForm idPrefix="rd" current={{ scl_class: r.scl_class, sif_potential: r.sif_potential, primary_lsr: r.primary_lsr }} onSubmit={(p) => decide.mutate(p)} busy={decide.isPending} error={decide.error ? (decide.error as Error).message : null} />
                    </div>
                  ) : null}
                </div>
              ) : human ? (
                <p className="flex items-center gap-2 text-[13px] text-green">
                  <ClipboardCheck className="size-4" aria-hidden /> Validated by an HSE reviewer ({q.data.decisions[0]?.reviewer}).
                </p>
              ) : (
                <p className="text-[13px] text-fg-2">No automatic review trigger. The AI analysis still needs human validation before action; use “Send to reviewer” to request it.</p>
              )}
            </Panel>

            <Panel title="Priority score" id="priority">
              <PriorityBreakdown analysis={a} />
            </Panel>

            <Panel title="Confidence" subtitle="Explainable: combined from four evidence components" id="confidence">
              <ConfidenceBreakdown analysis={a} />
            </Panel>

            <Panel title="Recurring patterns" id="pat">
              {q.data.patterns.length ? (
                <ul className="flex flex-col gap-2">
                  {q.data.patterns.map((p) => (
                    <li key={p.id}>
                      <Link href={`/patterns/${p.id}`} className="flex items-start gap-2 text-[12.5px] text-fg-2 hover:text-fg">
                        <Network className="mt-0.5 size-3.5 shrink-0 text-cyan" aria-hidden />
                        <span>
                          <span className="font-mono text-muted">{p.code}</span> {p.name} <span className="text-muted">· {p.occurrences}×</span>
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[12.5px] text-muted">Not part of a mined recurring pattern. {a.context.recurrence_count ? `${a.context.recurrence_count} similar precursor report(s) in the recurrence window.` : ""}</p>
              )}
            </Panel>

            <Panel title="Similar reports" subtitle={similar.data ? `Embedding search · ${similar.data.method}` : undefined} id="similar">
              {!similar.data ? (
                <LoadingState rows={3} />
              ) : similar.data.items.length ? (
                <ul className="flex flex-col divide-y divide-border">
                  {similar.data.items.map((s) => (
                    <li key={s.id} className="py-2">
                      <Link href={`/reports/${s.report_id}`} className="block hover:bg-surface-2/50">
                        <p className="flex items-center justify-between gap-2">
                          <span className="font-mono text-[12px] text-cyan">{s.report_id}</span>
                          <span className="num font-mono text-[11px] text-muted">sim {s.similarity.toFixed(2)}</span>
                        </p>
                        <p className="mt-0.5 line-clamp-2 text-[12px] text-fg-2">{s.description}</p>
                        <p className="mt-1 flex items-center gap-2">
                          <SifBadge signal={s.sif_signal} />
                          <LsrTag code={s.primary_lsr} className="text-[11.5px]" />
                        </p>
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[12.5px] text-muted">No embedding available.</p>
              )}
            </Panel>

            <Panel title="Audit history" id="audit">
              {q.data.decisions.length ? (
                <div className="mb-3 flex flex-col gap-2">
                  {q.data.decisions.map((d) => (
                    <div key={d.id} className="rounded-sm border border-green/30 bg-green/[0.05] p-2.5 text-[12px]">
                      <p className="font-medium text-fg">
                        {d.action} · {d.reviewer}
                      </p>
                      <p className="text-muted">{fmtDateTime(d.created_at)}</p>
                      {d.decision && Object.keys(d.decision).length ? (
                        <p className="mt-1 text-fg-2">
                          AI: {String(d.original_prediction.scl_class)} / {String(d.original_prediction.sif_signal)} / {String(d.original_prediction.primary_lsr)} → Final: {String(d.decision.scl_class)} / {String(d.decision.sif_signal)} / {String(d.decision.primary_lsr)}
                        </p>
                      ) : null}
                      {d.reason ? <p className="mt-1 text-fg-2">Reason: {d.reason}</p> : null}
                      {d.note ? <p className="mt-1 text-fg-2">Note: {d.note}</p> : null}
                    </div>
                  ))}
                </div>
              ) : null}
              {q.data.audit.length ? (
                <ol className="flex flex-col gap-2.5 border-l border-border pl-3">
                  {q.data.audit.map((e) => (
                    <li key={e.id} className="relative text-[12px]">
                      <span className="absolute -left-[16.5px] top-1 size-2 rounded-full border border-border-strong bg-surface" aria-hidden />
                      <p className="font-mono text-[10.5px] uppercase tracking-wider text-muted">
                        {e.event_type} · {fmtDateTime(e.created_at)}
                      </p>
                      <p className="text-fg-2">
                        {e.summary} <span className="text-muted">— {e.actor}</span>
                      </p>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="flex items-center gap-2 text-[12.5px] text-muted">
                  <History className="size-3.5" aria-hidden /> Seeded synthetic record — analysed during dataset seeding (see Audit Log: DATASET_SEEDED).
                </p>
              )}
            </Panel>
          </aside>
        </div>
      )}
    </div>
  );
}
