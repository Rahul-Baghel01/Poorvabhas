"use client";

import { useMutation } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, Download, FileUp, UploadCloud } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { Badge, Button, ErrorState, Notice, PageHeader, Panel } from "@/components/ui/primitives";
import { API_BASE, api } from "@/lib/api";
import { useInvalidateAll } from "@/lib/hooks";
import { cn } from "@/lib/format";

interface Validation {
  ok: boolean;
  token: string;
  filename: string;
  rows_detected: number;
  valid_rows: number;
  invalid_rows: number;
  errors: { line: number; report_id: string | null; errors: string[] }[];
  preview: Record<string, string | null>[];
  new_sites: string[];
  optional_columns_present: string[];
}
interface Committed {
  imported: number;
  analyzed: number;
  sif_signal: number;
  review_required: number;
  report_ids: string[];
  patterns: { patterns: number; method: string } | null;
  seconds: number;
}

const STEPS = ["Upload", "Validate", "Preview", "Import", "Analyze", "Classify", "Map", "Store", "Update dashboard"];
const REQUIRED = ["report_id", "report_type", "date", "site", "location", "activity", "equipment", "description"];
const OPTIONAL = ["worker_role", "contractor", "injury_severity", "shift", "weather"];

function Stepper({ reached }: { reached: number }) {
  return (
    <ol className="flex flex-wrap items-center gap-x-1 gap-y-2" aria-label="Import progress">
      {STEPS.map((s, i) => (
        <li key={s} className="flex items-center gap-1">
          <span className={cn("flex items-center gap-1.5 rounded-xs border px-2 py-1 font-mono text-[10.5px] uppercase tracking-wider", i < reached ? "border-green/40 bg-green/10 text-green" : i === reached ? "border-cyan/50 bg-cyan/10 text-cyan" : "border-border text-muted")} aria-current={i === reached ? "step" : undefined}>
            {i < reached ? <CheckCircle2 className="size-3" aria-hidden /> : <span className="num">{i + 1}</span>}
            {s}
          </span>
          {i < STEPS.length - 1 ? <span className="text-muted" aria-hidden>›</span> : null}
        </li>
      ))}
    </ol>
  );
}

function Stat({ label, value, tone }: { label: string; value: number | string; tone?: string }) {
  return (
    <div className="rounded-sm border border-border bg-surface-2 px-3 py-2.5">
      <p className="label-tech">{label}</p>
      <p className={cn("num mt-1 font-mono text-[24px] font-semibold", tone ?? "text-fg")}>{value}</p>
    </div>
  );
}

export default function ImportPage() {
  const invalidate = useInvalidateAll();
  const [file, setFile] = React.useState<File | null>(null);
  const [drag, setDrag] = React.useState(false);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const validate = useMutation({
    mutationFn: async (f: File) => {
      const fd = new FormData();
      fd.append("file", f);
      return api<Validation>("/imports/validate", { method: "POST", body: fd });
    },
  });
  const commit = useMutation({
    mutationFn: (token: string) => api<Committed>(`/imports/${token}/commit`, { method: "POST" }),
    onSuccess: () => invalidate(),
  });

  const v = validate.data;
  const c = commit.data;
  const reached = c ? 9 : commit.isPending ? 4 : v ? 3 : validate.isPending ? 1 : file ? 1 : 0;

  function pick(f: File | null | undefined) {
    if (!f) return;
    setFile(f);
    commit.reset();
    validate.mutate(f);
  }

  return (
    <div>
      <PageHeader
        eyebrow="Ingestion / bulk CSV"
        title="Import data"
        subtitle="Upload reports as CSV. Every row is validated before anything is stored; valid rows are analysed by the same engine as manual entries."
        actions={
          <a href={`${API_BASE}/imports/template`} download>
            <Button>
              <Download className="size-4" aria-hidden /> CSV template
            </Button>
          </a>
        }
      />
      <div className="mb-5">
        <Stepper reached={reached} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex min-w-0 flex-col gap-5">
          <Panel title="Upload" id="upload">
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDrag(true);
              }}
              onDragLeave={() => setDrag(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDrag(false);
                pick(e.dataTransfer.files?.[0]);
              }}
              className={cn("flex flex-col items-center justify-center gap-3 rounded-sm border border-dashed px-6 py-10 text-center transition-colors", drag ? "border-cyan bg-cyan/5" : "border-border-strong bg-bg/50")}
            >
              <UploadCloud className="size-8 text-muted" aria-hidden />
              <p className="text-[14px] text-fg">Drop a .csv file here</p>
              <p className="text-[12px] text-muted">UTF-8, up to 5 MB / 5,000 rows</p>
              <input ref={inputRef} id="csv" type="file" accept=".csv,text/csv" className="sr-only" onChange={(e) => pick(e.target.files?.[0])} aria-label="Choose CSV file" />
              <Button onClick={() => inputRef.current?.click()} loading={validate.isPending}>
                <FileUp className="size-4" aria-hidden /> Choose file
              </Button>
              {file ? <p className="font-mono text-[12px] text-fg-2">{file.name}</p> : null}
            </div>
          </Panel>

          {validate.isError ? <ErrorState title="CSV rejected" error={validate.error} /> : null}

          {v ? (
            <Panel title="Validation" subtitle={v.filename} id="validation" accent={v.invalid_rows ? "amber" : "green"}>
              <div className="grid grid-cols-3 gap-3">
                <Stat label="Rows detected" value={v.rows_detected} />
                <Stat label="Valid rows" value={v.valid_rows} tone="text-green" />
                <Stat label="Invalid rows" value={v.invalid_rows} tone={v.invalid_rows ? "text-amber" : "text-muted"} />
              </div>
              {v.new_sites.length ? (
                <Notice tone="cyan" className="mt-3" title="New sites will be created">
                  {v.new_sites.join(", ")} (no exposure hours; ranked by rate only).
                </Notice>
              ) : null}
              {v.errors.length ? (
                <div className="mt-4">
                  <p className="label-tech mb-2">Invalid rows (not imported)</p>
                  <div className="max-h-64 overflow-auto rounded-sm border border-border">
                    <table className="w-full text-[12px]">
                      <thead className="sticky top-0 bg-surface-2">
                        <tr className="text-left">
                          <th scope="col" className="label-tech px-3 py-2 font-normal">Line</th>
                          <th scope="col" className="label-tech px-3 py-2 font-normal">Report ID</th>
                          <th scope="col" className="label-tech px-3 py-2 font-normal">Problems</th>
                        </tr>
                      </thead>
                      <tbody>
                        {v.errors.map((e) => (
                          <tr key={e.line} className="border-t border-border/60">
                            <td className="num px-3 py-1.5 font-mono text-fg-2">{e.line}</td>
                            <td className="px-3 py-1.5 font-mono text-fg-2">{e.report_id ?? "—"}</td>
                            <td className="px-3 py-1.5 text-amber">{e.errors.join("; ")}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : null}
            </Panel>
          ) : null}

          {v && v.preview.length ? (
            <Panel title="Preview" subtitle={`First ${v.preview.length} valid rows`} id="preview">
              <div className="-mx-4 overflow-x-auto px-4">
                <table className="w-full min-w-[900px] text-[12px]">
                  <thead>
                    <tr className="border-b border-border text-left">
                      {["report_id", "report_type", "date", "site", "location", "activity", "description"].map((h) => (
                        <th key={h} scope="col" className="label-tech py-2 pr-3 font-normal">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {v.preview.map((r) => (
                      <tr key={r.report_id} className="border-b border-border/60 align-top">
                        <td className="py-1.5 pr-3 font-mono text-fg">{r.report_id}</td>
                        <td className="py-1.5 pr-3 text-fg-2">{r.report_type}</td>
                        <td className="num py-1.5 pr-3 font-mono text-fg-2">{r.date}</td>
                        <td className="py-1.5 pr-3 text-fg-2">{r.site}</td>
                        <td className="py-1.5 pr-3 text-fg-2">{r.location}</td>
                        <td className="py-1.5 pr-3 text-fg-2">{r.activity}</td>
                        <td className="max-w-[360px] py-1.5 pr-3 text-fg-2">
                          <span className="line-clamp-2">{r.description}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="mt-4 flex items-center justify-end gap-3">
                <p className="text-[12px] text-muted">{v.valid_rows} rows will be stored and analysed.</p>
                <Button variant="primary" disabled={!v.valid_rows || !!c} loading={commit.isPending} onClick={() => commit.mutate(v.token)}>
                  Import & analyse {v.valid_rows} rows
                </Button>
              </div>
              {commit.isError ? <p className="mt-2 text-right text-[12.5px] text-red">{(commit.error as Error).message}</p> : null}
            </Panel>
          ) : null}

          {c ? (
            <Panel title="Import complete" id="done" accent="green">
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <Stat label="Imported" value={c.imported} />
                <Stat label="Analyzed" value={c.analyzed} tone="text-cyan" />
                <Stat label="SIF signal" value={c.sif_signal} tone="text-red" />
                <Stat label="Review required" value={c.review_required} tone="text-amber" />
              </div>
              <p className="mt-3 text-[12.5px] text-fg-2">
                Completed in {c.seconds}s. {c.patterns ? `Patterns re-mined (${c.patterns.patterns} patterns, ${c.patterns.method}).` : ""} The command center now includes these reports.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Link href="/">
                  <Button variant="primary">
                    View command center <ArrowRight className="size-4" aria-hidden />
                  </Button>
                </Link>
                <Link href="/review">
                  <Button>Review queue</Button>
                </Link>
                {c.report_ids[0] ? (
                  <Link href={`/reports/${c.report_ids[0]}`}>
                    <Button variant="ghost">Open {c.report_ids[0]}</Button>
                  </Link>
                ) : null}
              </div>
            </Panel>
          ) : null}
        </div>

        <aside className="flex flex-col gap-5">
          <Panel title="Required columns">
            <ul className="flex flex-wrap gap-1.5">
              {REQUIRED.map((c) => (
                <li key={c}>
                  <Badge tone="cyan">{c}</Badge>
                </li>
              ))}
            </ul>
            <p className="label-tech mb-2 mt-4">Optional</p>
            <ul className="flex flex-wrap gap-1.5">
              {OPTIONAL.map((c) => (
                <li key={c}>
                  <Badge>{c}</Badge>
                </li>
              ))}
            </ul>
            <ul className="mt-4 flex flex-col gap-1.5 text-[12px] text-fg-2">
              <li>• report_type: Unsafe Act, Unsafe Condition, Near Miss, Incident (UA/UC/NM accepted)</li>
              <li>• date: YYYY-MM-DD (DD-MM-YYYY and DD/MM/YYYY accepted); not in the future</li>
              <li>• report_id must be unique; description ≥ 15 characters</li>
            </ul>
          </Panel>
          <Notice tone="amber" title="Data handling">
            This prototype runs in a demo environment. Do not upload confidential production data unless the deployment has been approved for it.
          </Notice>
        </aside>
      </div>
    </div>
  );
}
