"use client";

import { Badge } from "@/components/ui/primitives";
import { Quote } from "@/components/report/EvidenceText";
import type { EntityOut } from "@/lib/types";
import { ENTITY_LABELS, ENTITY_TONE, cn } from "@/lib/format";

const ORDER = ["activity", "energy_source", "hazard", "barrier", "control", "failure_mode", "human_behavior", "equipment", "location", "site", "report_type", "injury_outcome", "environmental_context"];

function polarityTone(p: string | null) {
  return p === "failed" || p === "absent" ? "amber" : p === "present" ? "green" : p === "conflict" ? "red" : "neutral";
}

export function ExtractionTable({ entities, notStated, onFocus, focus }: { entities: EntityOut[]; notStated: string[]; onFocus?: (k: string | null) => void; focus?: string | null }) {
  const groups = ORDER.map((t) => ({ type: t, items: entities.filter((e) => e.entity_type === t) }));
  return (
    <div className="-mx-4 overflow-x-auto px-4">
      <table className="w-full min-w-[640px] text-[12.5px]">
        <caption className="sr-only">Extracted safety entities with evidence</caption>
        <thead>
          <tr className="border-b border-border text-left">
            {["Entity", "Value", "State", "Evidence (source text)", "Conf."].map((h) => (
              <th key={h} scope="col" className="label-tech py-2 pr-3 font-normal">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {groups.map((g) =>
            g.items.length === 0 ? (
              notStated.includes(g.type) ? (
                <tr key={g.type} className="border-b border-border/50">
                  <th scope="row" className="py-2 pr-3 text-left font-normal text-muted">
                    {ENTITY_LABELS[g.type]}
                  </th>
                  <td className="py-2 pr-3 text-muted" colSpan={4}>
                    Not stated
                  </td>
                </tr>
              ) : null
            ) : (
              g.items.map((e, i) => {
                const key = `${e.entity_type}:${e.canonical}`;
                const tone = ENTITY_TONE[e.entity_type] ?? "neutral";
                return (
                  <tr
                    key={`${g.type}-${i}`}
                    className={cn("border-b border-border/50 align-top", onFocus && "cursor-default hover:bg-surface-2", focus === key && "bg-surface-2")}
                    onMouseEnter={() => onFocus?.(key)}
                    onMouseLeave={() => onFocus?.(null)}
                  >
                    <th scope="row" className="py-2 pr-3 text-left font-normal">
                      {i === 0 ? <span className={cn("text-[12px]", { red: "text-red", amber: "text-amber", cyan: "text-cyan", green: "text-green", neutral: "text-fg-2", "red-deep": "text-red" }[tone])}>{ENTITY_LABELS[g.type]}</span> : <span className="sr-only">{ENTITY_LABELS[g.type]}</span>}
                    </th>
                    <td className="py-2 pr-3 text-fg">{e.canonical || e.value}</td>
                    <td className="py-2 pr-3">{e.polarity ? <Badge tone={polarityTone(e.polarity)}>{e.polarity}</Badge> : <span className="text-muted">—</span>}</td>
                    <td className="py-2 pr-3">
                      <div className="flex flex-col gap-0.5">
                        {e.evidence.slice(0, 2).map((ev, j) => (
                          <Quote key={j} text={ev.text} source={ev.source} />
                        ))}
                        {e.source === "rule" ? <span className="text-[11px] text-muted">derived by domain rule</span> : null}
                      </div>
                    </td>
                    <td className="num py-2 font-mono text-fg-2">{e.confidence.toFixed(2)}</td>
                  </tr>
                );
              })
            ),
          )}
        </tbody>
      </table>
    </div>
  );
}
