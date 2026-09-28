"use client";

import { Info } from "lucide-react";

import type { RankItem, Ranking } from "@/lib/types";
import { cn, pct } from "@/lib/format";

function CiBar({ value, lo, hi, max }: { value: number; lo: number; hi: number; max: number }) {
  const x = (v: number) => `${Math.min(100, (v / max) * 100)}%`;
  return (
    <div className="relative h-4 w-full min-w-24" aria-hidden>
      <div className="absolute top-1/2 h-px w-full -translate-y-1/2 bg-surface-3" />
      <div className="absolute top-1/2 h-[6px] -translate-y-1/2 rounded-[1px] bg-red/25" style={{ left: x(lo), width: `calc(${x(hi)} - ${x(lo)})` }} />
      <div className="absolute top-1/2 h-3 w-[3px] -translate-x-1/2 -translate-y-1/2 rounded-[1px] bg-red" style={{ left: x(value) }} />
    </div>
  );
}

export function RankingTable({ data, compact }: { data: Ranking; compact?: boolean }) {
  const density = data.items.some((i) => i.eb_density !== null && i.eb_density !== undefined);
  const hiMax = Math.max(0.0001, ...data.items.map((i) => (density ? i.eb_density_ci90?.[1] ?? 0 : i.eb_rate_ci90[1] * 100)));
  if (!data.items.length) return <p className="py-6 text-center text-[13px] text-muted">{data.note || "No reports in the selected window"}</p>;
  const dimLabel = data.dimension === "site" ? "Site" : data.dimension === "activity" ? "Activity" : "Location";
  return (
    <div className="flex flex-col gap-3">
      <div className="-mx-4 overflow-x-auto px-4">
        <table className="w-full min-w-[640px] border-collapse text-[12.5px]">
          <caption className="sr-only">
            {dimLabel} ranking by {data.method.score}
          </caption>
          <thead>
            <tr className="border-b border-border text-left">
              <th scope="col" className="label-tech py-2 pr-2 font-normal">#</th>
              <th scope="col" className="label-tech py-2 pr-3 font-normal">{dimLabel}</th>
              <th scope="col" className="label-tech py-2 pr-3 text-right font-normal">Reports</th>
              <th scope="col" className="label-tech py-2 pr-3 text-right font-normal">SIF-potential</th>
              <th scope="col" className="label-tech py-2 pr-3 text-right font-normal">Raw rate</th>
              {density && !compact ? <th scope="col" className="label-tech py-2 pr-3 text-right font-normal">Raw / 100k h</th> : null}
              <th scope="col" className="label-tech py-2 pr-3 text-right font-normal">{density ? "Adj. / 100k h" : "Adj. rate"}</th>
              <th scope="col" className="label-tech w-[22%] py-2 font-normal">
                90% interval
              </th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((it: RankItem) => {
              const val = density ? (it.eb_density ?? 0) : it.eb_rate * 100;
              const lo = density ? (it.eb_density_ci90?.[0] ?? 0) : it.eb_rate_ci90[0] * 100;
              const hi = density ? (it.eb_density_ci90?.[1] ?? 0) : it.eb_rate_ci90[1] * 100;
              return (
                <tr key={it.key} className={cn("border-b border-border/60 align-middle", it.rank === 1 && "bg-red/[0.04]")}>
                  <td className="num py-2.5 pr-2 font-mono text-muted">{String(it.rank).padStart(2, "0")}</td>
                  <td className="py-2.5 pr-3">
                    <span className="font-medium text-fg">{it.label}</span>
                    {it.site ? <span className="ml-1.5 text-muted">· {it.site}</span> : null}
                    {it.notes.length ? (
                      <span className={cn("mt-0.5 block text-[11.5px]", it.rank === 1 ? "text-red" : "text-muted")}>{it.notes.join(" · ")}</span>
                    ) : null}
                  </td>
                  <td className="num py-2.5 pr-3 text-right font-mono text-fg-2">{it.total_reports}</td>
                  <td className="num py-2.5 pr-3 text-right font-mono text-fg">{it.sif_potential_reports}</td>
                  <td className="num py-2.5 pr-3 text-right font-mono text-fg-2">{pct(it.raw_rate, 1)}</td>
                  {density && !compact ? <td className="num py-2.5 pr-3 text-right font-mono text-fg-2">{it.raw_density?.toFixed(2) ?? "—"}</td> : null}
                  <td className="num py-2.5 pr-3 text-right font-mono font-semibold text-fg">{density ? val.toFixed(2) : `${val.toFixed(1)}%`}</td>
                  <td className="py-2.5" title={`90% credible interval ${lo.toFixed(2)} – ${hi.toFixed(2)}`}>
                    <CiBar value={val} lo={lo} hi={hi} max={hiMax} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="flex gap-2 text-[11.5px] leading-relaxed text-muted">
        <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
        <span>
          Ranked by {data.method.score}. Empirical-Bayes shrinkage pulls small samples toward the dataset rate
          {data.method.rate_prior?.dataset_rate !== undefined && data.method.rate_prior?.dataset_rate !== null ? ` (${pct(data.method.rate_prior.dataset_rate, 1)})` : ""}, so a site does not top the list on a handful of reports. {data.method.exposure_note} A higher rank means a stronger precursor signal in this dataset, not a verdict that a site is unsafe.
        </span>
      </p>
    </div>
  );
}
