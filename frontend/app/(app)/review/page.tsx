"use client";

import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, ChevronLeft, ChevronRight, ClipboardCheck, ExternalLink } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import * as React from "react";

import { DecisionForm, type DecisionPayload } from "@/components/report/DecisionForm";
import { Quote } from "@/components/report/EvidenceText";
import { AnswerBadge, ConfidenceTag, ControlAnswerBadge, LsrTag, PriorityBadge, SclBadge, SifBadge } from "@/components/ui/badges";
import { Button, EmptyState, ErrorState, LoadingState, PageHeader, Select } from "@/components/ui/primitives";
import { api, qs } from "@/lib/api";
import { useInvalidateAll } from "@/lib/hooks";
import { REVIEW_CATEGORY_META, SCL_META, cn, fmtDate } from "@/lib/format";
import type { Paged, ReviewItem } from "@/lib/types";

interface Stats {
  open: number;
  closed: number;
  categories: { code: string; label: string; count: number }[];
}

const GATE_SHORT: Record<string, string> = { high_energy: "High energy", high_energy_event: "Energy event", direct_control: "Direct control", serious_injury: "Serious injury" };

function ReviewCard({ item, onDone }: { item: ReviewItem; onDone: (msg: string) => void }) {
  const r = item.report;
  const a = item.analysis;
  const invalidate = useInvalidateAll();
  const m = useMutation({
    mutationFn: (p: DecisionPayload) => api<{ status: string }>(`/review/${item.id}/decision`, { method: "POST", json: p }),
    onSuccess: (res, p) => {
      invalidate();
      onDone(p.action === "NOTE" ? `Note saved on ${r.report_id}` : `${r.report_id}: decision recorded (${res.status.replace("_", " ").toLowerCase()})`);
    },
  });
  return (
    <motion.article layout initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, x: 24, transition: { duration: 0.2 } }} className="relative rounded-md border border-border bg-surface" aria-labelledby={`rv-${item.id}`}>
      <span className="absolute left-0 top-0 h-full w-[3px] rounded-l-md bg-amber" aria-hidden />
      <header className="flex flex-col gap-2 border-b border-border px-4 py-3 pl-5 md:flex-row md:items-center md:justify-between">
        <div className="flex flex-wrap items-center gap-2.5">
          <h2 id={`rv-${item.id}`} className="font-mono text-[14px] font-semibold">
            <Link href={`/reports/${r.report_id}`} className="inline-flex items-center gap-1 text-fg hover:text-cyan">
              {r.report_id} <ExternalLink className="size-3 text-muted" aria-hidden />
            </Link>
          </h2>
          <span className="rounded-xs border border-amber/50 bg-amber/10 px-1.5 py-[1px] font-mono text-[10.5px] uppercase tracking-wider text-amber">{item.category_label}</span>
          {item.source === "MANUAL" ? <span className="text-[11.5px] text-muted">requested by {item.requested_by}</span> : null}
        </div>
        <div className="flex flex-wrap items-center gap-3 text-[12px] text-fg-2">
          <span>
            {r.report_type} · {fmtDate(r.date)} · {r.activity} · {r.site}
          </span>
          <PriorityBadge level={r.priority_level} score={r.priority_score} />
        </div>
      </header>
      <div className="grid gap-4 p-4 pl-5 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <div className="flex min-w-0 flex-col gap-3">
          <div>
            <p className="label-tech mb-1">Reason for review</p>
            <ul className="flex flex-col gap-1">
              {item.reasons.map((x, i) => (
                <li key={i} className="text-[12.5px] text-fg-2">
                  <span className="text-amber">{x.label}:</span> {x.detail}
                </li>
              ))}
            </ul>
          </div>
          <blockquote className="rounded-sm border border-border bg-bg/60 px-3 py-2.5 text-[13.5px] leading-relaxed text-fg">{r.description}</blockquote>
          {a ? (
            <div className="grid grid-cols-2 gap-2">
              {a.gates.map((g) => (
                <div key={g.key} className={cn("rounded-sm border px-2.5 py-2", g.used_in_path ? "border-border" : "border-dashed border-border opacity-60")}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[12px] text-fg">{GATE_SHORT[g.key]}</span>
                    {g.key === "direct_control" ? <ControlAnswerBadge answer={g.answer} /> : <AnswerBadge answer={g.answer} />}
                  </div>
                  <div className="mt-1 min-h-4 truncate">{g.evidence[0] ? <Quote text={g.evidence[0].text} source={g.evidence[0].source} /> : <span className="text-[11.5px] text-amber">no evidence</span>}</div>
                </div>
              ))}
            </div>
          ) : null}
        </div>
        <div className="flex min-w-0 flex-col gap-3">
          <dl className="grid grid-cols-2 gap-3 rounded-sm border border-border bg-surface-2 p-3 sm:grid-cols-4 lg:grid-cols-2 2xl:grid-cols-4">
            <div>
              <dt className="label-tech">SCL class</dt>
              <dd className="mt-1">
                <SclBadge scl={r.scl_class} />
                {a && a.scl_class === "UNDETERMINED" && a.scl_candidates.length ? <span className="block text-[11px] text-muted">{a.scl_candidates.map((c) => SCL_META[c]?.label ?? c).join(" / ")}</span> : null}
              </dd>
            </div>
            <div>
              <dt className="label-tech">SIF classification</dt>
              <dd className="mt-1">
                <SifBadge signal={r.sif_signal} />
              </dd>
            </div>
            <div>
              <dt className="label-tech">Evidence confidence</dt>
              <dd className="mt-1">
                <ConfidenceTag value={a?.confidence ?? r.confidence} />
              </dd>
            </div>
            <div>
              <dt className="label-tech">Classifier</dt>
              <dd className="num mt-1 font-mono text-[12px] text-fg-2">{a?.ml_probability !== null && a?.ml_probability !== undefined ? `P=${a.ml_probability.toFixed(2)}` : "n/a"}</dd>
            </div>
            <div className="col-span-2 sm:col-span-4 lg:col-span-2 2xl:col-span-4">
              <dt className="label-tech">Suggested LSR — proposed crosswalk · subject to HSE expert validation</dt>
              <dd className="mt-1">
                <LsrTag code={a?.suggested_lsr?.code ?? r.primary_lsr} name={a?.suggested_lsr?.name ?? r.lsr_name} />
              </dd>
            </div>
          </dl>
          <p className="text-[12px] text-fg-2">
            <span className="label-tech mr-1">Suggested action</span> {item.suggested_action}
          </p>
          <DecisionForm idPrefix={`rv${item.id}`} current={{ scl_class: r.scl_class, sif_potential: r.sif_potential, primary_lsr: r.primary_lsr }} onSubmit={(p) => m.mutate(p)} busy={m.isPending} error={m.error ? (m.error as Error).message : null} />
        </div>
      </div>
    </motion.article>
  );
}

export default function ReviewQueuePage() {
  const [category, setCategory] = React.useState<string>("");
  const [sort, setSort] = React.useState("priority");
  const [page, setPage] = React.useState(1);
  const [toast, setToast] = React.useState<string | null>(null);
  const stats = useQuery({ queryKey: ["review-stats"], queryFn: () => api<Stats>("/review/stats") });
  const q = useQuery({ queryKey: ["review", category, page, sort], queryFn: () => api<Paged<ReviewItem>>(`/review${qs({ category, page, page_size: 8, sort })}`), placeholderData: keepPreviousData });

  React.useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  return (
    <div>
      <PageHeader
        eyebrow="Human-in-the-loop / reviewer workspace"
        title="HSE review queue"
        subtitle="Cases the engine will not decide alone: low confidence, borderline gates, missing facts, conflicting rules, or classifier disagreement. Reviewer decisions are authoritative and may be stored as labelled feedback examples for controlled retraining."
      />

      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-7" role="tablist" aria-label="Review categories">
        <button role="tab" aria-selected={category === ""} onClick={() => (setCategory(""), setPage(1))} className={cn("rounded-md border px-3 py-2.5 text-left transition-colors", category === "" ? "border-amber/60 bg-amber/10" : "border-border bg-surface hover:border-border-strong")}>
          <span className="label-tech block">All open</span>
          <span className="num mt-1 block font-mono text-[22px] font-semibold text-amber">{stats.data?.open ?? "—"}</span>
        </button>
        {(stats.data?.categories ?? []).map((c) => (
          <button key={c.code} role="tab" aria-selected={category === c.code} onClick={() => (setCategory(c.code), setPage(1))} title={REVIEW_CATEGORY_META[c.code]?.hint} className={cn("rounded-md border px-3 py-2.5 text-left transition-colors", category === c.code ? "border-amber/60 bg-amber/10" : "border-border bg-surface hover:border-border-strong")}>
            <span className="label-tech block truncate">{c.label}</span>
            <span className={cn("num mt-1 block font-mono text-[22px] font-semibold", c.count ? "text-fg" : "text-muted")}>{c.count}</span>
          </button>
        ))}
      </div>

      <div className="mb-4 flex items-center justify-between gap-3">
        <p className="label-tech" aria-live="polite">
          {q.data ? `${q.data.total} open item${q.data.total === 1 ? "" : "s"}` : "Loading"} {stats.data ? `· ${stats.data.closed} closed` : ""}
        </p>
        <div className="flex items-center gap-2">
          <label htmlFor="rv-sort" className="sr-only">
            Sort
          </label>
          <Select id="rv-sort" value={sort} onChange={(e) => setSort(e.target.value)} className="w-44">
            <option value="priority">Highest priority</option>
            <option value="newest">Newest</option>
            <option value="oldest">Oldest</option>
          </Select>
          {q.data && q.data.pages > 1 ? (
            <>
              <Button size="sm" variant="ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} aria-label="Previous page">
                <ChevronLeft className="size-4" />
              </Button>
              <span className="num font-mono text-[12px] text-fg-2">
                {page}/{q.data.pages}
              </span>
              <Button size="sm" variant="ghost" disabled={page >= q.data.pages} onClick={() => setPage((p) => p + 1)} aria-label="Next page">
                <ChevronRight className="size-4" />
              </Button>
            </>
          ) : null}
        </div>
      </div>

      <AnimatePresence>
        {toast ? (
          <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-sm border border-green/50 bg-[#0d1712] px-4 py-3 text-[13px] text-fg shadow-lg" role="status">
            <CheckCircle2 className="size-4 text-green" aria-hidden /> {toast}
          </motion.div>
        ) : null}
      </AnimatePresence>

      {q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : !q.data ? (
        <LoadingState rows={6} />
      ) : q.data.items.length === 0 ? (
        <div className="rounded-md border border-border bg-surface">
          <EmptyState icon={ClipboardCheck} title="Nothing to review in this category" description="All cases here have a human decision." />
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <AnimatePresence mode="popLayout" initial={false}>
            {q.data.items.map((it) => (
              <ReviewCard key={it.id} item={it} onDone={setToast} />
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
