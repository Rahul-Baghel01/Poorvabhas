"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowRight, ClipboardCheck, FileText, Layers, Network, Plus, ShieldAlert, Siren } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { HBarList, ReportsOverTime, SparkBars } from "@/components/charts/charts";
import { RankingTable } from "@/components/charts/RankingTable";
import { LsrTag, SifBadge, TrendBadge } from "@/components/ui/badges";
import { FadeIn } from "@/components/ui/motion";
import { Button, EmptyState, ErrorState, LoadingState, PageHeader, Panel, Select, Skeleton } from "@/components/ui/primitives";
import { api, qs } from "@/lib/api";
import { REVIEW_CATEGORY_META, SIF_SIGNAL_META, cn, pct } from "@/lib/format";
import type { Dashboard, Ranking } from "@/lib/types";

const WINDOWS = [
  { days: 30, label: "Last 30 days" },
  { days: 90, label: "Last 90 days" },
  { days: 180, label: "Last 180 days" },
  { days: 365, label: "Last 365 days" },
];

function Delta({ pctv, invert }: { pctv: number | null | undefined; invert?: boolean }) {
  if (pctv === null || pctv === undefined) return <span className="text-muted">no prior period data</span>;
  const up = pctv > 0;
  const bad = invert ? !up : up;
  return (
    <span className={cn(pctv === 0 ? "text-muted" : bad ? "text-red" : "text-green")}>
      {up ? "▲" : pctv < 0 ? "▼" : "■"} {Math.abs(pctv).toFixed(1)}% <span className="text-muted">vs prior period</span>
    </span>
  );
}

function Kpi({ label, value, icon: Icon, sub, tone = "neutral", href }: { label: string; value: React.ReactNode; icon: React.ElementType; sub?: React.ReactNode; tone?: "red" | "amber" | "cyan" | "green" | "neutral"; href?: string }) {
  const color = { red: "text-red", amber: "text-amber", cyan: "text-cyan", green: "text-green", neutral: "text-fg-2" }[tone];
  const inner = (
    <div className={cn("group relative flex h-full flex-col justify-between gap-3 rounded-md border border-border bg-surface p-4 transition-colors", href && "hover:border-border-strong hover:bg-surface-2")}>
      <div className="flex items-start justify-between gap-2">
        <p className="label-tech leading-snug">{label}</p>
        <Icon className={cn("size-4 shrink-0", color)} aria-hidden />
      </div>
      <p className={cn("num font-mono text-[30px] font-semibold leading-none tracking-tight", tone === "neutral" ? "text-fg" : color)}>{value}</p>
      <p className="min-h-4 text-[11.5px] leading-snug text-muted">{sub}</p>
    </div>
  );
  return href ? (
    <Link href={href} className="block h-full">
      {inner}
    </Link>
  ) : (
    inner
  );
}

export default function CommandCenter() {
  const [days, setDays] = React.useState(90);
  const [dim, setDim] = React.useState<"site" | "activity" | "location">("site");
  const q = useQuery({ queryKey: ["dashboard", days], queryFn: () => api<Dashboard>(`/dashboard${qs({ days })}`) });
  const ranking = useQuery({ queryKey: ["ranking", dim, days], queryFn: () => api<Ranking>(`/ranking${qs({ dimension: dim, days })}`), enabled: dim !== "site" });
  const d = q.data;

  return (
    <div>
      <PageHeader
        eyebrow={`HSE intelligence / ${WINDOWS.find((w) => w.days === days)?.label ?? `last ${days} days`}`}
        title="Command center"
        subtitle="A clear view of the safety signals that need human attention."
        actions={
          <>
            <label htmlFor="window" className="sr-only">
              Time window
            </label>
            <Select id="window" value={days} onChange={(e) => setDays(Number(e.target.value))} className="w-40">
              {WINDOWS.map((w) => (
                <option key={w.days} value={w.days}>
                  {w.label}
                </option>
              ))}
            </Select>
            <Link href="/reports/new">
              <Button variant="primary">
                <Plus className="size-4" aria-hidden /> New report
              </Button>
            </Link>
          </>
        }
      />

      {q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : (
        <div className="flex flex-col gap-5">
          {/* KPIs */}
          <FadeIn>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
              {!d
                ? Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-[124px]" />)
                : (
                  <>
                    <Kpi label="Total reports" value={d.kpis.total_reports.value} icon={FileText} sub={<Delta pctv={d.kpis.total_reports.change_pct} invert />} href="/reports" />
                    <Kpi
                      label="SIF-potential reports"
                      value={d.kpis.sif_potential_reports.value}
                      icon={ShieldAlert}
                      tone="red"
                      sub={
                        <>
                          {pct(d.kpis.sif_potential_reports.share)} of reports{d.kpis.sif_potential_reports.sif_events ? ` · +${d.kpis.sif_potential_reports.sif_events} SIF event${d.kpis.sif_potential_reports.sif_events > 1 ? "s" : ""}` : ""}
                        </>
                      }
                      href="/reports?sif_signal=SIF_POTENTIAL"
                    />
                    <Kpi label="Recurring patterns" value={d.kpis.recurring_patterns.value} icon={Network} tone="cyan" sub={d.kpis.recurring_patterns.increasing ? `${d.kpis.recurring_patterns.increasing} with a detected increase` : "No statistically detected increase"} href="/patterns" />
                    <Kpi label="Review queue" value={d.kpis.review_queue.value} icon={ClipboardCheck} tone="amber" sub="Open items awaiting an HSE reviewer" href="/review" />
                    <Kpi label="High-priority signals" value={d.kpis.high_priority_signals.value} icon={Siren} tone="red" sub={<Delta pctv={d.kpis.high_priority_signals.change_pct} />} href="/reports?priority=CRITICAL,HIGH&sif_signal=SIF_POTENTIAL,SIF_EVENT" />
                    <Kpi
                      label="LSR coverage"
                      value={d.kpis.lsr_coverage.value === null ? "—" : pct(d.kpis.lsr_coverage.value)}
                      icon={Layers}
                      tone="green"
                      sub={`${d.kpis.lsr_coverage.mapped}/${d.kpis.lsr_coverage.sif_signals} SIF signals mapped · ${d.kpis.lsr_coverage.rules_observed}/9 rules seen`}
                    />
                  </>
                )}
            </div>
          </FadeIn>

          {/* Priority banner */}
          {d?.priority_banner.text ? (
            <FadeIn delay={0.05}>
              <div className="flex flex-col gap-3 rounded-md border border-red/40 bg-[linear-gradient(90deg,rgba(255,74,67,0.12),rgba(255,74,67,0.02))] px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between" role="status">
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-sm border border-red/40 bg-red/15">
                    <AlertTriangle className="size-4 text-red" aria-hidden />
                  </span>
                  <div>
                    <p className="label-tech !text-red">Priority signal</p>
                    <p className="mt-0.5 text-[14.5px] font-medium text-fg">{d.priority_banner.text}</p>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Link href="/reports?priority=CRITICAL,HIGH&sif_signal=SIF_POTENTIAL,SIF_EVENT&sort=priority_desc">
                    <Button variant="danger" size="sm">
                      View signals <ArrowRight className="size-3.5" aria-hidden />
                    </Button>
                  </Link>
                  <Link href="/review">
                    <Button size="sm">Review queue</Button>
                  </Link>
                </div>
              </div>
            </FadeIn>
          ) : null}

          {/* Row: distribution + time */}
          <div className="grid gap-5 xl:grid-cols-3">
            <Panel title="SIF potential distribution" subtitle="Current decision per report (AI or reviewer)" id="dist">
              {!d ? (
                <LoadingState />
              ) : (
                <HBarList
                  valueLabel="Reports"
                  rows={["SIF_EVENT", "SIF_POTENTIAL", "UNDETERMINED", "NON_SIF"].map((s) => ({
                    key: s,
                    label: (
                      <span className="inline-flex items-center gap-2">
                        <span className="size-2 rounded-[2px]" style={{ background: SIF_SIGNAL_META[s].color }} aria-hidden />
                        {SIF_SIGNAL_META[s].label}
                      </span>
                    ),
                    value: d.sif_distribution.find((x) => x.signal === s)?.count ?? 0,
                    color: SIF_SIGNAL_META[s].color,
                  }))}
                  color="#FF4A43"
                />
              )}
              {d ? (
                <div className="mt-4 grid grid-cols-4 gap-2 border-t border-border pt-3">
                  {["SIF_EVENT", "SIF_POTENTIAL", "UNDETERMINED", "NON_SIF"].map((s) => (
                    <Link key={s} href={`/reports?sif_signal=${s}`} className="rounded-xs px-1 py-1 text-center hover:bg-surface-2">
                      <span className="block font-mono text-[10px] uppercase tracking-wide text-muted">{SIF_SIGNAL_META[s].label}</span>
                      <span className="num block font-mono text-[16px] text-fg">{d.sif_distribution.find((x) => x.signal === s)?.count ?? 0}</span>
                    </Link>
                  ))}
                </div>
              ) : null}
            </Panel>
            <Panel title="Reports over time" subtitle="Weekly count of reports and SIF signals" className="xl:col-span-2" id="time">
              {!d ? <LoadingState rows={5} /> : <ReportsOverTime data={d.reports_over_time} />}
            </Panel>
          </div>

          {/* Row: LSR + activities */}
          <div className="grid gap-5 lg:grid-cols-2">
            <Panel title="Life-Saving Rules" subtitle="SIF-signal reports by proposed rule (proposed crosswalk — requires HSE expert validation)" id="lsr">
              {!d ? (
                <LoadingState rows={5} />
              ) : (
                <HBarList
                  valueLabel="SIF-signal reports"
                  rows={d.top_lsr.map((r) => ({ key: r.code, label: <LsrTag code={r.code} name={r.name} />, value: r.count }))}
                  emptyText="No SIF signals in this window"
                />
              )}
            </Panel>
            <Panel title="Top activities" subtitle="Reports per activity and how many carry a SIF signal" id="acts">
              {!d ? (
                <LoadingState rows={5} />
              ) : (
                <HBarList valueLabel="Reports" partLabel="SIF signal" rows={d.top_activities.map((a) => ({ key: a.activity, label: a.activity, value: a.total, part: a.sif }))} />
              )}
            </Panel>
          </div>

          {/* Row: ranking + patterns */}
          <div className="grid gap-5 xl:grid-cols-5">
            <Panel
              title="SIF precursor density ranking"
              subtitle="Adjusted for volume and exposure: highest adjusted signal first"
              className="xl:col-span-3"
              id="rank"
              actions={
                <div className="flex rounded-sm border border-border p-0.5" role="tablist" aria-label="Ranking dimension">
                  {(["site", "activity", "location"] as const).map((k) => (
                    <button key={k} role="tab" aria-selected={dim === k} onClick={() => setDim(k)} className={cn("rounded-xs px-2.5 py-1 font-mono text-[10.5px] uppercase tracking-wider", dim === k ? "bg-surface-3 text-fg" : "text-muted hover:text-fg")}>
                      {k}
                    </button>
                  ))}
                </div>
              }
            >
              {dim === "site" ? (
                !d ? <LoadingState rows={6} /> : <RankingTable data={d.site_ranking} compact />
              ) : ranking.isError ? (
                <ErrorState error={ranking.error} onRetry={() => ranking.refetch()} />
              ) : !ranking.data ? (
                <LoadingState rows={6} />
              ) : (
                <RankingTable data={{ ...ranking.data, items: ranking.data.items.slice(0, 8) }} compact />
              )}
            </Panel>
            <Panel title="Pattern alerts" subtitle="Recurring precursor combinations mined from the data" className="xl:col-span-2" id="patterns" actions={<Link href="/patterns" className="text-[12px] text-cyan hover:underline">All patterns</Link>}>
              {!d ? (
                <LoadingState rows={5} />
              ) : d.patterns.length === 0 ? (
                <EmptyState icon={Network} title="No recurring patterns detected" description="Patterns appear once enough precursor reports share activity, barrier and energy." />
              ) : (
                <ul className="flex flex-col divide-y divide-border">
                  {d.patterns.map((p) => (
                    <li key={p.id}>
                      <Link href={`/patterns/${p.id}`} className="flex items-center gap-3 py-2.5 hover:bg-surface-2/60">
                        <span className="w-10 shrink-0 font-mono text-[11px] text-muted">{p.code}</span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-[13px] text-fg">{p.name}</span>
                          <span className="mt-0.5 flex items-center gap-2 text-[11.5px] text-muted">
                            <span className="num font-mono text-fg-2">{p.occurrences}×</span> · {p.sites.slice(0, 2).join(", ")}
                          </span>
                        </span>
                        <span className="hidden sm:block">
                          <SparkBars counts={p.counts} label={`${p.code} occurrences per period`} />
                        </span>
                        <TrendBadge trend={p.trend} />
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>

          {/* Review queue */}
          <Panel title="Review queue" subtitle="Highest-priority open items" id="queue" accent="amber" actions={<Link href="/review" className="text-[12px] text-amber hover:underline">Open workspace</Link>}>
            {!d ? (
              <LoadingState />
            ) : d.review_queue.length === 0 ? (
              <EmptyState icon={ClipboardCheck} title="Review queue is clear" description="No reports currently need an HSE reviewer." />
            ) : (
              <div className="-mx-4 overflow-x-auto px-4">
                <table className="w-full min-w-[720px] text-[12.5px]">
                  <thead>
                    <tr className="border-b border-border text-left">
                      {["Report", "Reason for review", "Activity", "Site", "SIF signal", "Priority"].map((h) => (
                        <th key={h} scope="col" className="label-tech py-2 pr-3 font-normal">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {d.review_queue.map((r) => (
                      <tr key={r.review_id} className="border-b border-border/60">
                        <td className="py-2.5 pr-3">
                          <Link href={`/reports/${r.report_id}`} className="font-mono text-cyan hover:underline">
                            {r.report_id}
                          </Link>
                        </td>
                        <td className="py-2.5 pr-3 text-amber">{REVIEW_CATEGORY_META[r.category]?.label ?? r.category}</td>
                        <td className="py-2.5 pr-3 text-fg-2">{r.activity}</td>
                        <td className="py-2.5 pr-3 text-fg-2">{r.site}</td>
                        <td className="py-2.5 pr-3">
                          <SifBadge signal={r.sif_signal} />
                        </td>
                        <td className="num py-2.5 font-mono text-fg">{Math.round(r.priority_score)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </div>
      )}
    </div>
  );
}
