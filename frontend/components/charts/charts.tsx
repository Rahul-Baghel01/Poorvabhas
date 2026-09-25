"use client";

import * as React from "react";
import { Area, Bar, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { cn } from "@/lib/format";

const AXIS = { stroke: "#394346", tick: { fill: "#8a9597", fontSize: 11, fontFamily: "var(--font-plex-mono)" } };
const GRID = "#1f2729";

export const SERIES = { sif: "#FF4A43", total: "#6B7678", accent: "#27C7C9", amber: "#F2B233" };

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

/* ------------------------------------------------------------------ legend */
export function Legend({ items }: { items: { label: string; color: string; kind?: "line" | "area" | "bar" | "dash" }[] }) {
  return (
    <ul className="flex flex-wrap items-center gap-x-4 gap-y-1" aria-label="Legend">
      {items.map((i) => (
        <li key={i.label} className="flex items-center gap-2 text-[12px] text-fg-2">
          {i.kind === "line" ? (
            <span className="h-[2px] w-4 rounded" style={{ background: i.color }} aria-hidden />
          ) : i.kind === "dash" ? (
            <span className="w-4 border-t-2 border-dashed" style={{ borderColor: i.color }} aria-hidden />
          ) : (
            <span className="size-2.5 rounded-[2px]" style={{ background: i.color }} aria-hidden />
          )}
          {i.label}
        </li>
      ))}
    </ul>
  );
}

/* ------------------------------------------------------------------ reports over time */
export function ReportsOverTime({ data }: { data: { week_start: string; total: number; sif: number }[] }) {
  const summary = `Weekly reports: ${data.reduce((a, b) => a + b.total, 0)} total, ${data.reduce((a, b) => a + b.sif, 0)} with a SIF signal.`;
  return (
    <figure className="flex flex-col gap-3">
      <Legend items={[{ label: "All reports", color: SERIES.total, kind: "area" }, { label: "SIF signal (potential + event)", color: SERIES.sif, kind: "line" }]} />
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
                      { label: "SIF signal", value: payload.find((p) => p.dataKey === "sif")?.value as number, color: SERIES.sif },
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

/* ------------------------------------------------------------------ horizontal bar list (HTML) */
export interface HBarRow {
  key: string;
  label: React.ReactNode;
  value: number;
  part?: number; // highlighted portion (e.g. SIF-signal share of total)
  href?: string;
  suffix?: React.ReactNode;
  color?: string;
}

export function HBarList({ rows, color = SERIES.accent, partColor = SERIES.sif, restColor = "#3a4446", valueLabel, partLabel, emptyText = "No data in window" }: {
  rows: HBarRow[];
  color?: string;
  partColor?: string;
  restColor?: string;
  valueLabel: string;
  partLabel?: string;
  emptyText?: string;
}) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  if (!rows.length) return <p className="py-6 text-center text-[13px] text-muted">{emptyText}</p>;
  return (
    <div className="flex flex-col gap-2.5">
      {partLabel ? <Legend items={[{ label: partLabel, color: partColor }, { label: `Other ${valueLabel.toLowerCase()}`, color: restColor }]} /> : null}
      <ul className="flex flex-col gap-2.5">
        {rows.map((r) => {
          const w = (r.value / max) * 100;
          const pw = r.part !== undefined && r.value ? (r.part / r.value) * w : 0;
          const title = r.part !== undefined ? `${r.part} ${partLabel?.toLowerCase() ?? ""} of ${r.value} ${valueLabel.toLowerCase()}` : `${r.value} ${valueLabel.toLowerCase()}`;
          return (
            <li key={r.key} className="group grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1" title={title}>
              <span className="truncate text-[12.5px] text-fg-2 group-hover:text-fg">{r.label}</span>
              <span className="num text-right font-mono text-[12px] text-fg">
                {r.part !== undefined ? (
                  <>
                    <span className="text-fg">{r.part}</span>
                    <span className="text-muted"> / {r.value}</span>
                  </>
                ) : (
                  r.value
                )}
                {r.suffix}
              </span>
              <div className="col-span-2 flex h-2 gap-[2px]" aria-hidden>
                {r.part !== undefined ? (
                  <>
                    {pw > 0 ? <div className="h-full rounded-l-[2px] transition-[width]" style={{ width: `${pw}%`, background: partColor }} /> : null}
                    {w - pw > 0 ? <div className={cn("h-full rounded-r-[2px] transition-[width]", pw === 0 && "rounded-l-[2px]")} style={{ width: `${w - pw}%`, background: restColor }} /> : null}
                  </>
                ) : (
                  <div className="h-full rounded-[2px] transition-[width]" style={{ width: `${w}%`, background: r.color ?? color }} />
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/* ------------------------------------------------------------------ sparkline bars (SVG) */
export function SparkBars({ counts, color = SERIES.sif, height = 28, label }: { counts: number[]; color?: string; height?: number; label: string }) {
  const max = Math.max(1, ...counts);
  const w = 4;
  const gap = 2;
  const width = counts.length * (w + gap) - gap;
  return (
    <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" aria-label={label} className="block w-full min-w-0 max-w-[140px]" style={{ height, width: Math.min(width, 140) }}>
      <title>{label}</title>
      {counts.map((c, i) => {
        const h = c === 0 ? 1 : Math.max(2, (c / max) * height);
        return <rect key={i} x={i * (w + gap)} y={height - h} width={w} height={h} rx={1} fill={c === 0 ? "#2a3335" : color} />;
      })}
    </svg>
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
