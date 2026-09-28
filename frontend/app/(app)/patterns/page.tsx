"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { MapPin, Network, RefreshCw } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { SparkBars } from "@/components/charts/charts";
import { RankingTable } from "@/components/charts/RankingTable";
import { LsrTag, TrendBadge } from "@/components/ui/badges";
import { FadeIn } from "@/components/ui/motion";
import { Button, EmptyState, ErrorState, LoadingState, PageHeader, Panel, Select } from "@/components/ui/primitives";
import { api, qs } from "@/lib/api";
import { useInvalidateAll } from "@/lib/hooks";
import { cn, fmtDateTime } from "@/lib/format";
import type { PatternOut, Ranking } from "@/lib/types";

function PatternCard({ p }: { p: PatternOut }) {
  const td = p.trend_detail;
  return (
    <Link href={`/patterns/${p.id}`} className={cn("group flex h-full min-w-0 flex-col gap-3 rounded-md border bg-surface p-4 transition-colors hover:bg-surface-2", p.trend === "INCREASING" ? "border-red/40" : "border-border hover:border-border-strong")}>
      <div className="flex items-start justify-between gap-2">
        <span className="font-mono text-[11px] tracking-wider text-muted">PATTERN {p.code}</span>
        <TrendBadge trend={p.trend} />
      </div>
      <h2 className="text-[15px] font-semibold leading-snug text-fg group-hover:text-white">{p.name}</h2>
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="num font-mono text-[26px] font-semibold leading-none text-fg">{p.occurrences}</p>
          <p className="mt-1 text-[11.5px] text-muted" title="Reports classified SIF-potential (PSIF / Exposure); includes any SIF Event (HSIF)">
            occurrences · {p.sif_occurrences} SIF-potential
          </p>
        </div>
        <SparkBars counts={td.counts} label={`${p.code}: occurrences per ${td.bucket}`} height={32} />
      </div>
      <div className="mt-auto flex flex-col gap-1.5 border-t border-border pt-3">
        <LsrTag code={p.primary_lsr} name={p.lsr_name} />
        <p className="flex items-center gap-1.5 truncate text-[12px] text-fg-2">
          <MapPin className="size-3.5 shrink-0 text-muted" aria-hidden />
          {p.locations.slice(0, 3).map((l) => l.name).join(", ")}
          {p.locations.length > 3 ? ` +${p.locations.length - 3}` : ""}
        </p>
      </div>
    </Link>
  );
}

export default function PatternsPage() {
  const invalidate = useInvalidateAll();
  const [dim, setDim] = React.useState<"site" | "activity" | "location">("site");
  const [days, setDays] = React.useState(365);
  const q = useQuery({ queryKey: ["patterns"], queryFn: () => api<{ items: PatternOut[]; method: string | null; mined_at: string | null }>("/patterns") });
  const ranking = useQuery({ queryKey: ["ranking", dim, days], queryFn: () => api<Ranking>(`/ranking${qs({ dimension: dim, days })}`) });
  const mine = useMutation({ mutationFn: () => api<{ patterns: number; method: string }>("/patterns/mine", { method: "POST" }), onSuccess: () => invalidate() });

  return (
    <div>
      <PageHeader
        eyebrow="Intelligence / recurring precursors · synthetic / proxy data"
        title="Pattern explorer"
        subtitle="Connecting recurring precursor signals across activity, location and failed barriers."
        actions={
          <Button onClick={() => mine.mutate()} loading={mine.isPending}>
            <RefreshCw className="size-4" aria-hidden /> Re-mine patterns
          </Button>
        }
      />
      {q.data?.mined_at ? (
        <p className="-mt-3 mb-4 font-mono text-[11px] uppercase tracking-wider text-muted">
          Mined {fmtDateTime(q.data.mined_at)} · method: {q.data.method === "hdbscan" ? "HDBSCAN (Jaccard distance)" : "frequency grouping"} · trends: EWMA + CUSUM on real report dates
        </p>
      ) : null}

      {q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : !q.data ? (
        <LoadingState rows={6} />
      ) : q.data.items.length === 0 ? (
        <Panel>
          <EmptyState icon={Network} title="No recurring patterns detected" description="Patterns appear when several precursor reports share an activity, failed barrier and energy source." />
        </Panel>
      ) : (
        <FadeIn>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
            {q.data.items.map((p) => (
              <PatternCard key={p.id} p={p} />
            ))}
          </div>
        </FadeIn>
      )}

      <Panel
        className="mt-6"
        title="SIF precursor density ranking"
        subtitle="Fair ranking: raw counts, raw rate, exposure-normalised density and empirical-Bayes adjusted score"
        id="ranking"
        actions={
          <div className="flex items-center gap-2">
            <div className="flex rounded-sm border border-border p-0.5" role="tablist" aria-label="Ranking dimension">
              {(["site", "activity", "location"] as const).map((k) => (
                <button key={k} role="tab" aria-selected={dim === k} onClick={() => setDim(k)} className={cn("rounded-xs px-2.5 py-1 font-mono text-[10.5px] uppercase tracking-wider", dim === k ? "bg-surface-3 text-fg" : "text-muted hover:text-fg")}>
                  {k}
                </button>
              ))}
            </div>
            <label htmlFor="rk-days" className="sr-only">
              Window
            </label>
            <Select id="rk-days" value={days} onChange={(e) => setDays(Number(e.target.value))} className="h-8 w-32 text-[12px]">
              <option value={90}>90 days</option>
              <option value={180}>180 days</option>
              <option value={365}>365 days</option>
            </Select>
          </div>
        }
      >
        {ranking.isError ? <ErrorState error={ranking.error} onRetry={() => ranking.refetch()} /> : !ranking.data ? <LoadingState rows={6} /> : <RankingTable data={ranking.data} />}
      </Panel>
    </div>
  );
}
