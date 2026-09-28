"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, FileSearch, Filter, Plus, Search, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import * as React from "react";

import { ConfidenceTag, LsrTag, PriorityBadge, SclBadge, SifBadge, StatusBadge } from "@/components/ui/badges";
import { Button, EmptyState, ErrorState, Input, LoadingState, PageHeader, Select } from "@/components/ui/primitives";
import { api, qs } from "@/lib/api";
import { LSR_SHORT, PRIORITY_META, SCL_META, SIF_SIGNAL_META, STATUS_META, cn, fmtDate } from "@/lib/format";
import type { Paged, ReportRow } from "@/lib/types";

interface Facets {
  report_types: string[];
  sites: { code: string; name: string }[];
  sif_signals: string[];
  priority_levels: string[];
  scl_classes: string[];
  statuses: string[];
}

const FILTER_KEYS = ["report_type", "site", "sif_signal", "priority", "scl_class", "lsr", "status", "date_from", "date_to", "activity"] as const;

function useDebounced<T>(v: T, ms = 300) {
  const [d, setD] = React.useState(v);
  React.useEffect(() => {
    const t = setTimeout(() => setD(v), ms);
    return () => clearTimeout(t);
  }, [v, ms]);
  return d;
}

function Registry() {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const [search, setSearch] = React.useState(sp.get("search") ?? "");
  const debounced = useDebounced(search);
  const [showFilters, setShowFilters] = React.useState(FILTER_KEYS.some((k) => sp.get(k)));

  const params: Record<string, string> = {};
  for (const k of FILTER_KEYS) {
    const v = sp.get(k);
    if (v) params[k] = v;
  }
  const page = Number(sp.get("page") || 1);
  const sort = sp.get("sort") || "date_desc";

  const setParam = React.useCallback(
    (updates: Record<string, string | null>) => {
      const next = new URLSearchParams(sp.toString());
      for (const [k, v] of Object.entries(updates)) {
        if (v) next.set(k, v);
        else next.delete(k);
      }
      if (!("page" in updates)) next.delete("page");
      router.replace(`${pathname}?${next.toString()}`, { scroll: false });
    },
    [sp, router, pathname],
  );

  React.useEffect(() => {
    if ((sp.get("search") ?? "") !== debounced) setParam({ search: debounced || null });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced]);

  const facets = useQuery({ queryKey: ["facets"], queryFn: () => api<Facets>("/reports/facets"), staleTime: 300_000 });
  const q = useQuery({
    queryKey: ["reports", params, sp.get("search"), page, sort],
    queryFn: () => api<Paged<ReportRow>>(`/reports${qs({ ...params, search: sp.get("search"), page, page_size: 25, sort })}`),
    placeholderData: keepPreviousData,
  });

  const active = Object.keys(params).length;
  const f = facets.data;

  const sel = (key: (typeof FILTER_KEYS)[number], label: string, options: { value: string; label: string }[]) => (
    <div className="flex min-w-0 flex-col gap-1">
      <label htmlFor={`f-${key}`} className="label-tech">
        {label}
      </label>
      <Select id={`f-${key}`} value={params[key] && !params[key].includes(",") ? params[key] : params[key] ? "__multi" : ""} onChange={(e) => setParam({ [key]: e.target.value === "__multi" ? params[key] : e.target.value || null })}>
        <option value="">All</option>
        {params[key]?.includes(",") ? <option value="__multi">{params[key].split(",").length} selected</option> : null}
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </Select>
    </div>
  );

  return (
    <div>
      <PageHeader
        eyebrow="Registry / all sources · synthetic / proxy data"
        title="Safety reports"
        subtitle="Every unsafe-act, unsafe-condition, near-miss and incident report with its SIF reasoning and review status."
        actions={
          <Link href="/reports/new">
            <Button variant="primary">
              <Plus className="size-4" aria-hidden /> New report
            </Button>
          </Link>
        }
      />

      <div className="mb-4 flex flex-col gap-3 rounded-md border border-border bg-surface p-3">
        <div className="flex flex-col gap-2 sm:flex-row">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
            <label htmlFor="search" className="sr-only">
              Search reports
            </label>
            <Input id="search" type="search" placeholder="Search report ID, site, location, activity, equipment or description…" value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9" />
          </div>
          <div className="flex gap-2">
            <label htmlFor="sort" className="sr-only">
              Sort
            </label>
            <Select id="sort" value={sort} onChange={(e) => setParam({ sort: e.target.value })} className="w-48">
              <option value="date_desc">Newest first</option>
              <option value="date_asc">Oldest first</option>
              <option value="priority_desc">Highest priority</option>
              <option value="confidence_asc">Lowest confidence</option>
              <option value="report_id">Report ID</option>
            </Select>
            <Button onClick={() => setShowFilters((s) => !s)} aria-expanded={showFilters} aria-controls="filters">
              <Filter className="size-4" aria-hidden /> Filters{active ? <span className="num rounded-xs bg-cyan/15 px-1.5 font-mono text-[11px] text-cyan">{active}</span> : null}
            </Button>
          </div>
        </div>
        {showFilters ? (
          <div id="filters" className="grid grid-cols-2 gap-3 border-t border-border pt-3 md:grid-cols-4 xl:grid-cols-8">
            {sel("report_type", "Report type", (f?.report_types ?? []).map((v) => ({ value: v, label: v })))}
            {sel("site", "Site", (f?.sites ?? []).map((s) => ({ value: s.name, label: s.name })))}
            {sel("sif_signal", "SIF signal", (f?.sif_signals ?? []).map((v) => ({ value: v, label: SIF_SIGNAL_META[v]?.label ?? v })))}
            {sel("priority", "Priority", (f?.priority_levels ?? []).map((v) => ({ value: v, label: PRIORITY_META[v]?.label ?? v })))}
            {sel("scl_class", "SCL class", (f?.scl_classes ?? []).map((v) => ({ value: v, label: SCL_META[v]?.label ?? v })))}
            {sel("lsr", "IOGP rule", Object.entries(LSR_SHORT).map(([k, v]) => ({ value: k, label: v })))}
            {sel("status", "Review status", (f?.statuses ?? []).map((v) => ({ value: v, label: STATUS_META[v]?.label ?? v })))}
            <div className="col-span-2 grid grid-cols-2 gap-2 md:col-span-1 xl:col-span-1">
              <div className="flex flex-col gap-1">
                <label htmlFor="f-from" className="label-tech">
                  From
                </label>
                <Input id="f-from" type="date" value={params.date_from ?? ""} onChange={(e) => setParam({ date_from: e.target.value || null })} className="px-2 text-[12px]" />
              </div>
              <div className="flex flex-col gap-1">
                <label htmlFor="f-to" className="label-tech">
                  To
                </label>
                <Input id="f-to" type="date" value={params.date_to ?? ""} onChange={(e) => setParam({ date_to: e.target.value || null })} className="px-2 text-[12px]" />
              </div>
            </div>
            {active ? (
              <div className="col-span-full">
                <Button size="sm" variant="ghost" onClick={() => setParam(Object.fromEntries(FILTER_KEYS.map((k) => [k, null])))}>
                  <X className="size-3.5" aria-hidden /> Clear filters
                </Button>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      <section className="rounded-md border border-border bg-surface" aria-label="Report results">
        <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
          <p className="label-tech" aria-live="polite">
            {q.data ? `${q.data.total} report${q.data.total === 1 ? "" : "s"}` : "Loading reports"}
            {q.isFetching && q.data ? " · updating" : ""}
          </p>
          {q.data && q.data.pages > 1 ? (
            <div className="flex items-center gap-2">
              <Button size="sm" variant="ghost" disabled={page <= 1} onClick={() => setParam({ page: String(page - 1) })} aria-label="Previous page">
                <ChevronLeft className="size-4" />
              </Button>
              <span className="num font-mono text-[12px] text-fg-2">
                {page} / {q.data.pages}
              </span>
              <Button size="sm" variant="ghost" disabled={page >= q.data.pages} onClick={() => setParam({ page: String(page + 1) })} aria-label="Next page">
                <ChevronRight className="size-4" />
              </Button>
            </div>
          ) : null}
        </div>

        {q.isError ? (
          <div className="p-4">
            <ErrorState error={q.error} onRetry={() => q.refetch()} />
          </div>
        ) : !q.data ? (
          <div className="p-4">
            <LoadingState rows={8} />
          </div>
        ) : q.data.items.length === 0 ? (
          <EmptyState icon={FileSearch} title="No reports found" description="Try a different search term or clear some filters." />
        ) : (
          <>
            {/* desktop table */}
            <div className="hidden overflow-x-auto md:block">
              <table className="w-full min-w-[1080px] text-[12.5px]">
                <thead>
                  <tr className="border-b border-border text-left">
                    {["Report", "Type / date", "Activity", "Site / location", "SIF signal / SCL class", "LSR", "Priority", "Confidence", "Status"].map((h) => (
                      <th key={h} scope="col" className="label-tech px-4 py-2.5 font-normal first:pl-4">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className={cn(q.isFetching && "opacity-70")}>
                  {q.data.items.map((r) => (
                    <tr key={r.id} className="group border-b border-border/60 hover:bg-surface-2">
                      <td className="px-4 py-3 align-top">
                        <Link href={`/reports/${r.report_id}`} className="font-mono text-[12.5px] text-cyan hover:underline">
                          {r.report_id}
                        </Link>
                        <p className="mt-1 line-clamp-1 max-w-[260px] text-[11.5px] text-muted" title={r.description}>
                          {r.description}
                        </p>
                      </td>
                      <td className="px-4 py-3 align-top">
                        <p className="text-fg">{r.report_type}</p>
                        <p className="num font-mono text-[11.5px] text-muted">{fmtDate(r.date)}</p>
                      </td>
                      <td className="px-4 py-3 align-top text-fg-2">{r.activity}</td>
                      <td className="px-4 py-3 align-top">
                        <p className="text-fg">{r.site}</p>
                        <p className="text-[11.5px] text-muted">{r.location}</p>
                      </td>
                      <td className="px-4 py-3 align-top">
                        <SifBadge signal={r.sif_signal} />
                        <p className="mt-1" title="SCL class (Safety Classification and Learning)">
                          <span className="mr-1 font-mono text-[9.5px] uppercase tracking-wider text-muted">SCL</span>
                          <SclBadge scl={r.scl_class} />
                        </p>
                      </td>
                      <td className="max-w-[190px] px-4 py-3 align-top">
                        <LsrTag code={r.primary_lsr} name={r.lsr_name} />
                      </td>
                      <td className="px-4 py-3 align-top">
                        <PriorityBadge level={r.priority_level} score={r.priority_score} />
                      </td>
                      <td className="px-4 py-3 align-top">
                        <ConfidenceTag value={r.confidence} />
                      </td>
                      <td className="px-4 py-3 align-top">
                        <StatusBadge status={r.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {/* mobile cards */}
            <ul className="divide-y divide-border md:hidden">
              {q.data.items.map((r) => (
                <li key={r.id}>
                  <Link href={`/reports/${r.report_id}`} className="block px-4 py-3 hover:bg-surface-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-[12.5px] text-cyan">{r.report_id}</span>
                      <SifBadge signal={r.sif_signal} />
                    </div>
                    <p className="mt-1 text-[13px] text-fg">
                      {r.activity} · {r.site}
                    </p>
                    <p className="mt-1 line-clamp-2 text-[12px] text-muted">{r.description}</p>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <StatusBadge status={r.status} />
                      <PriorityBadge level={r.priority_level} score={r.priority_score} />
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>
    </div>
  );
}

export default function ReportsPage() {
  return (
    <React.Suspense fallback={<LoadingState rows={8} />}>
      <Registry />
    </React.Suspense>
  );
}
