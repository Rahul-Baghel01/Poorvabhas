"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, History, Search } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { RequirePermission } from "@/components/shell/RequirePermission";
import { Badge, Button, EmptyState, ErrorState, Input, LoadingState, PageHeader, Select } from "@/components/ui/primitives";
import { api, qs } from "@/lib/api";
import { fmtDateTime, type Tone } from "@/lib/format";
import type { AuditEntry } from "@/lib/types";

const TONES: Record<string, Tone> = {
  REVIEW_COMPLETED: "green",
  REVIEW_STARTED: "amber",
  SIF_CLASSIFIED: "red",
  TAXONOMY_CHANGED: "amber",
  SETTINGS_CHANGED: "amber",
  MODEL_CHANGED: "cyan",
  IMPORT_COMPLETED: "cyan",
  REPORT_CREATED: "cyan",
};

export default function AuditPage() {
  const [eventType, setEventType] = React.useState("");
  const [search, setSearch] = React.useState("");
  const [page, setPage] = React.useState(1);
  const q = useQuery({
    queryKey: ["audit", eventType, search, page],
    queryFn: () => api<{ items: AuditEntry[]; total: number; pages: number; event_types: string[] }>(`/audit${qs({ event_type: eventType, search, page, page_size: 30 })}`),
    placeholderData: keepPreviousData,
  });
  const [open, setOpen] = React.useState<number | null>(null);

  return (
    <RequirePermission perm="audit">
      <PageHeader eyebrow="Administration / traceability" title="Audit log" subtitle="Every analysis, classification, mapping, review decision, taxonomy and model change — who, what and when." />
      <div className="mb-4 flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
          <label htmlFor="a-search" className="sr-only">
            Search audit log
          </label>
          <Input id="a-search" type="search" value={search} onChange={(e) => (setSearch(e.target.value), setPage(1))} placeholder="Search summary, report ID or actor…" className="pl-9" />
        </div>
        <label htmlFor="a-type" className="sr-only">
          Event type
        </label>
        <Select id="a-type" value={eventType} onChange={(e) => (setEventType(e.target.value), setPage(1))} className="sm:w-56">
          <option value="">All events</option>
          {(q.data?.event_types ?? []).map((t) => (
            <option key={t}>{t}</option>
          ))}
        </Select>
      </div>
      <section className="rounded-md border border-border bg-surface" aria-label="Audit events">
        <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
          <p className="label-tech">{q.data ? `${q.data.total} events` : "Loading"}</p>
          {q.data && q.data.pages > 1 ? (
            <div className="flex items-center gap-2">
              <Button size="sm" variant="ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} aria-label="Previous page">
                <ChevronLeft className="size-4" />
              </Button>
              <span className="num font-mono text-[12px] text-fg-2">
                {page}/{q.data.pages}
              </span>
              <Button size="sm" variant="ghost" disabled={page >= q.data.pages} onClick={() => setPage((p) => p + 1)} aria-label="Next page">
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
          <EmptyState icon={History} title="No audit events match" />
        ) : (
          <ul className="divide-y divide-border">
            {q.data.items.map((e) => (
              <li key={e.id} className="px-4 py-3">
                <div className="flex flex-col gap-1.5 md:flex-row md:items-center md:gap-4">
                  <span className="num w-44 shrink-0 font-mono text-[11.5px] text-muted">{fmtDateTime(e.created_at)}</span>
                  <span className="w-44 shrink-0">
                    <Badge tone={TONES[e.event_type] ?? "neutral"}>{e.event_type}</Badge>
                  </span>
                  <span className="min-w-0 flex-1 text-[13px] text-fg">
                    {e.entity_type === "report" && e.entity_id ? (
                      <Link href={`/reports/${e.entity_id}`} className="mr-1.5 font-mono text-cyan hover:underline">
                        {e.entity_id}
                      </Link>
                    ) : null}
                    {e.summary}
                  </span>
                  <span className="shrink-0 text-[12px] text-fg-2">{e.actor}</span>
                  {Object.keys(e.details ?? {}).length ? (
                    <Button size="sm" variant="ghost" onClick={() => setOpen(open === e.id ? null : e.id)} aria-expanded={open === e.id}>
                      Details
                    </Button>
                  ) : null}
                </div>
                {open === e.id ? <pre className="mt-2 max-h-72 overflow-auto rounded-sm border border-border bg-bg p-3 font-mono text-[11.5px] text-fg-2">{JSON.stringify(e.details, null, 2)}</pre> : null}
              </li>
            ))}
          </ul>
        )}
      </section>
    </RequirePermission>
  );
}
