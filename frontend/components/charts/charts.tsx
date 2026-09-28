"use client";

import * as React from "react";

import { cn } from "@/lib/format";

export const SERIES = { sif: "#FF4A43", total: "#6B7678", accent: "#27C7C9", amber: "#F2B233" };

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
