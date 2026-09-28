"use client";

// Recharts time-series charts. Kept apart from charts.tsx so Recharts is only downloaded by
// pages that draw one of these (loaded with next/dynamic on the dashboard and pattern detail).
import * as React from "react";
import { Area, Bar, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Legend, SERIES } from "./charts";

const AXIS = { stroke: "#394346", tick: { fill: "#8a9597", fontSize: 11, fontFamily: "var(--font-plex-mono)" } };
const GRID = "#1f2729";

function shortDate(iso: string) {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short" });
}

/* ------------------------------------------------------------------ tooltip */
function TipBox({ title, rows }: { title: string; rows: { label: string; value: React.ReactNode; color?: string }[] }) {
  return (
    <div className="min-w-40 rounded-sm border border-border-strong bg-[#0d1112]/95 px-3 py-2 shadow-lg shadow-black/40">
      <p className="mb-1.5 font-mono text-[10.5px] uppercase tracking-wider text-muted">{title}</p>
      {rows.map((r) => (
        <p key={r.label} className="flex items-center justify-between gap-4 text-[12.5px] text-fg-2">
          <span className="flex items-center gap-2">
            {r.color ? <span className="size-2 rounded-[2px]" style={{ background: r.color }} aria-hidden /> : null}
            {r.label}
          </span>
          <span className="num font-mono text-fg">{r.value}</span>
        </p>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ reports over time */
export function ReportsOverTime({ data }: { data: { week_start: string; total: number; sif: number }[] }) {
  const summary = `Weekly reports: ${data.reduce((a, b) => a + b.total, 0)} total, ${data.reduce((a, b) => a + b.sif, 0)} SIF-potential or SIF Event.`;
  return (
    <figure className="flex flex-col gap-3">
      <Legend items={[{ label: "All reports", color: SERIES.total, kind: "area" }, { label: "SIF-potential + SIF Event", color: SERIES.sif, kind: "line" }]} />
      <div className="h-[220px]" role="img" aria-label={summary}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="week_start" tickFormatter={shortDate} {...AXIS} tickLine={false} axisLine={false} minTickGap={24} />
            <YAxis allowDecimals={false} {...AXIS} tickLine={false} axisLine={false} width={48} />
            <Tooltip
              cursor={{ stroke: "#4a5558", strokeWidth: 1 }}
              content={({ active, payload, label }) =>
                active && payload?.length ? (
                  <TipBox
                    title={`Week of ${shortDate(String(label))}`}
                    rows={[
                      { label: "All reports", value: payload.find((p) => p.dataKey === "total")?.value as number, color: SERIES.total },
                      { label: "SIF-potential + Event", value: payload.find((p) => p.dataKey === "sif")?.value as number, color: SERIES.sif },
                    ]}
                  />
                ) : null
              }
            />
            <Area type="monotone" dataKey="total" stroke={SERIES.total} strokeWidth={2} fill={SERIES.total} fillOpacity={0.14} activeDot={{ r: 4, stroke: "#111617", strokeWidth: 2 }} isAnimationActive={false} />
            <Line type="monotone" dataKey="sif" stroke={SERIES.sif} strokeWidth={2} dot={false} activeDot={{ r: 4, stroke: "#111617", strokeWidth: 2 }} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="sr-only">{summary}</figcaption>
    </figure>
  );
}

/* ------------------------------------------------------------------ pattern trend (counts + EWMA + control limit) */
export function TrendChart({ labels, counts, ewma, ucl, baseline, bucket }: { labels: string[]; counts: number[]; ewma?: number[]; ucl?: number; baseline?: number; bucket: string }) {
  const data = labels.map((l, i) => ({ label: l, count: counts[i], ewma: ewma?.[i] }));
  const items = [{ label: `Occurrences per ${bucket}`, color: SERIES.sif, kind: "bar" as const }];
  if (ewma) items.push({ label: "EWMA", color: SERIES.accent, kind: "line" as const } as never);
  if (ucl !== undefined) items.push({ label: "EWMA upper control limit", color: SERIES.amber, kind: "dash" as const } as never);
  if (baseline !== undefined) items.push({ label: "Baseline mean", color: "#8a9597", kind: "dash" as const } as never);
  return (
    <figure className="flex flex-col gap-3">
      <Legend items={items} />
      <div className="h-[230px]" role="img" aria-label={`Occurrences per ${bucket}: ${counts.join(", ")}`}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -18 }} barCategoryGap={3}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="label" tickFormatter={shortDate} {...AXIS} tickLine={false} axisLine={false} minTickGap={20} />
            <YAxis allowDecimals={false} {...AXIS} tickLine={false} axisLine={false} width={48} />
            <Tooltip
              cursor={{ fill: "rgba(255,255,255,0.04)" }}
              content={({ active, payload, label }) =>
                active && payload?.length ? (
                  <TipBox
                    title={`${bucket} of ${shortDate(String(label))}`}
                    rows={[
                      { label: "Occurrences", value: payload.find((p) => p.dataKey === "count")?.value as number, color: SERIES.sif },
                      ...(ewma ? [{ label: "EWMA", value: Number(payload.find((p) => p.dataKey === "ewma")?.value ?? 0).toFixed(2), color: SERIES.accent }] : []),
                    ]}
                  />
                ) : null
              }
            />
            {baseline !== undefined ? <ReferenceLine y={baseline} stroke="#8a9597" strokeDasharray="4 4" /> : null}
            {ucl !== undefined ? <ReferenceLine y={ucl} stroke={SERIES.amber} strokeDasharray="4 4" /> : null}
            <Bar dataKey="count" fill={SERIES.sif} radius={[3, 3, 0, 0]} maxBarSize={28} isAnimationActive={false} />
            {ewma ? <Line type="monotone" dataKey="ewma" stroke={SERIES.accent} strokeWidth={2} dot={false} isAnimationActive={false} /> : null}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
