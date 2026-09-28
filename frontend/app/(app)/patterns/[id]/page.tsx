"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Info, Network } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams } from "next/navigation";

import { HBarList } from "@/components/charts/charts";
import { LsrTag, PriorityBadge, SifBadge, StatusBadge, TrendBadge } from "@/components/ui/badges";
import { EmptyState, ErrorState, KV, LoadingState, Notice, Panel } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { fmtDate, titleCase } from "@/lib/format";
import type { Dist, PatternOut } from "@/lib/types";

const TrendChart = dynamic(() => import("@/components/charts/timeseries").then((m) => m.TrendChart), { ssr: false, loading: () => <LoadingState rows={6} /> });

function DistPanel({ title, rows, color }: { title: string; rows: Dist[]; color?: string }) {
  return (
    <Panel title={title}>
      <HBarList valueLabel="Occurrences" color={color} rows={rows.slice(0, 8).map((r) => ({ key: r.name, label: titleCase(r.name), value: r.count }))} emptyText="Not stated" />
    </Panel>
  );
}

export default function PatternDetailPage() {
  const { id } = useParams<{ id: string }>();
  const q = useQuery({ queryKey: ["pattern", id], queryFn: () => api<PatternOut>(`/patterns/${id}`) });
  if (q.isError)
    return q.error instanceof ApiError && q.error.status === 404 ? (
      <EmptyState icon={Network} title="Pattern not found" description="Patterns are re-mined as data changes; this pattern may belong to an earlier run." action={<Link href="/patterns" className="text-cyan hover:underline">Back to Pattern explorer</Link>} />
    ) : (
      <ErrorState error={q.error} onRetry={() => q.refetch()} />
    );
  if (!q.data) return <LoadingState rows={10} />;
  const p = q.data;
  const td = p.trend_detail;
  return (
    <div className="flex flex-col gap-5">
      <div>
        <Link href="/patterns" className="mb-3 inline-flex items-center gap-1.5 text-[12.5px] text-muted hover:text-fg">
          <ArrowLeft className="size-3.5" aria-hidden /> Pattern explorer
        </Link>
        <p className="label-tech">Pattern {p.code} · {p.method === "hdbscan" ? "HDBSCAN cluster" : "frequency group"}</p>
        <h1 className="mt-1.5 text-[26px] font-semibold leading-tight md:text-[30px]">{p.name}</h1>
        <div className="mt-2.5 flex flex-wrap items-center gap-3">
          <TrendBadge trend={p.trend} />
          <LsrTag code={p.primary_lsr} name={p.lsr_name} />
        </div>
        <dl className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          <KV k="Occurrences" v={<span className="num font-mono text-[18px]">{p.occurrences}</span>} />
          <KV k="SIF-potential (incl. any SIF Event)" v={<span className="num font-mono text-[18px] text-red">{p.sif_occurrences}</span>} />
          <KV k="Cohesion" v={<span className="num font-mono">{p.cohesion.toFixed(2)}</span>} />
          <KV k="Confidence" v={<span className="num font-mono">{p.confidence.toFixed(2)}</span>} />
          <KV k="First seen" v={fmtDate(p.first_seen)} />
          <KV k="Last seen" v={fmtDate(p.last_seen)} />
        </dl>
      </div>

      <Panel title="Timeline" subtitle={`Occurrences per ${td.bucket} from actual report dates`} id="timeline" accent={p.trend === "INCREASING" ? "red" : undefined}>
        <TrendChart labels={td.labels} counts={td.counts} ewma={td.ewma} ucl={td.ewma_ucl} baseline={td.baseline_mean} bucket={td.bucket} />
        <div className="mt-3">
          {p.trend === "INSUFFICIENT_HISTORY" ? (
            <Notice tone="neutral" title="Insufficient history — no trend claimed">
              {td.reason}
            </Notice>
          ) : (
            <p className="flex gap-2 text-[12px] leading-relaxed text-fg-2">
              <Info className="mt-0.5 size-3.5 shrink-0 text-muted" aria-hidden />
              <span>
                <span className="font-medium text-fg">{titleCase(p.trend.toLowerCase())}.</span> Baseline {td.baseline_mean?.toFixed(2)} per {td.bucket}; recent {td.recent_mean?.toFixed(2)} per {td.bucket}. Peak CUSUM⁺ {Math.max(...(td.cusum_pos ?? [0])).toFixed(2)} vs decision limit h = {td.cusum_h?.toFixed(2)}; latest EWMA {td.ewma?.at(-1)?.toFixed(2)} vs upper limit {td.ewma_ucl?.toFixed(2)}. {td.method}.
              </span>
            </p>
          )}
        </div>
      </Panel>

      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
        <DistPanel title="Locations" rows={p.locations} color="#8a9597" />
        <DistPanel title="Activities" rows={p.activities} color="#32B978" />
        <DistPanel title="Failed barriers" rows={p.barriers} color="#F2B233" />
        <DistPanel title="Energy sources" rows={p.energy_sources} color="#FF4A43" />
      </div>
      <div className="grid gap-5 md:grid-cols-2">
        <Panel title="Sites">
          <HBarList valueLabel="Occurrences" color="#8a9597" rows={p.sites.map((s) => ({ key: s.name, label: s.name, value: s.count }))} />
        </Panel>
        <Panel title="Associated Life-Saving Rules" subtitle="Proposed IOGP LSR crosswalk — subject to HSE expert validation">
          <HBarList valueLabel="Occurrences" rows={p.associated_lsr.map((s) => ({ key: s.code, label: <LsrTag code={s.code} name={s.name} />, value: s.count }))} />
        </Panel>
      </div>

      <Panel title="Connected reports" subtitle={`${p.reports?.length ?? 0} reports in this pattern · membership = HDBSCAN cluster probability`} id="reports">
        <div className="-mx-4 overflow-x-auto px-4">
          <table className="w-full min-w-[860px] text-[12.5px]">
            <thead>
              <tr className="border-b border-border text-left">
                {["Report", "Date", "Site / location", "Description", "SIF", "Priority", "Status", "Member."].map((h) => (
                  <th key={h} scope="col" className="label-tech py-2 pr-3 font-normal">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(p.reports ?? []).map((r) => (
                <tr key={r.id} className="border-b border-border/60 align-top hover:bg-surface-2">
                  <td className="py-2.5 pr-3">
                    <Link href={`/reports/${r.report_id}`} className="font-mono text-cyan hover:underline">
                      {r.report_id}
                    </Link>
                  </td>
                  <td className="num py-2.5 pr-3 font-mono text-fg-2">{fmtDate(r.date)}</td>
                  <td className="py-2.5 pr-3 text-fg-2">
                    {r.site}
                    <span className="block text-[11.5px] text-muted">{r.location}</span>
                  </td>
                  <td className="max-w-[380px] py-2.5 pr-3 text-fg-2">
                    <span className="line-clamp-2">{r.description}</span>
                  </td>
                  <td className="py-2.5 pr-3">
                    <SifBadge signal={r.sif_signal} />
                  </td>
                  <td className="py-2.5 pr-3">
                    <PriorityBadge level={r.priority_level} score={r.priority_score} />
                  </td>
                  <td className="py-2.5 pr-3">
                    <StatusBadge status={r.status} />
                  </td>
                  <td className="num py-2.5 font-mono text-fg-2">{r.membership.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
