"use client";

import { CheckCircle2, CircleHelp, CircleX, PencilLine, StickyNote } from "lucide-react";
import * as React from "react";

import { Button, Field, Select, Textarea } from "@/components/ui/primitives";
import { LSR_SHORT, SCL_META, cn } from "@/lib/format";

export type DecisionAction = "CONFIRM" | "REJECT" | "CHANGE" | "INSUFFICIENT" | "NOTE";

export interface DecisionPayload {
  action: DecisionAction;
  scl_class?: string | null;
  sif_potential?: boolean | null;
  primary_lsr?: string | null;
  reason?: string | null;
  note?: string | null;
}

const ACTIONS: { key: DecisionAction; label: string; icon: React.ElementType; hint: string }[] = [
  { key: "CONFIRM", label: "Confirm", icon: CheckCircle2, hint: "The AI classification is correct" },
  { key: "CHANGE", label: "Change", icon: PencilLine, hint: "Correct the SCL class, SIF potential or Life-Saving Rule" },
  { key: "REJECT", label: "Reject", icon: CircleX, hint: "The AI classification is wrong" },
  { key: "INSUFFICIENT", label: "Insufficient info", icon: CircleHelp, hint: "The report cannot be classified as written" },
  { key: "NOTE", label: "Add note", icon: StickyNote, hint: "Record a note without closing the review" },
];

export function DecisionForm({ idPrefix, current, onSubmit, busy, error }: {
  idPrefix: string;
  current: { scl_class: string | null; sif_potential: boolean | null; primary_lsr: string | null };
  onSubmit: (p: DecisionPayload) => void;
  busy?: boolean;
  error?: string | null;
}) {
  const [action, setAction] = React.useState<DecisionAction>("CONFIRM");
  const [scl, setScl] = React.useState<string>("");
  const [sif, setSif] = React.useState<string>("");
  const [lsr, setLsr] = React.useState<string>("");
  const [reason, setReason] = React.useState("");
  const [note, setNote] = React.useState("");
  const needsReason = action === "REJECT" || action === "CHANGE";
  const changeInvalid = action === "CHANGE" && !scl && !sif && !lsr;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const p: DecisionPayload = { action, reason: reason || null, note: note || null };
    if (action === "CHANGE" || action === "REJECT") {
      if (scl) p.scl_class = scl;
      if (sif) p.sif_potential = sif === "true";
      if (lsr) p.primary_lsr = lsr;
    }
    onSubmit(p);
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3" aria-label="Reviewer decision">
      <fieldset>
        <legend className="label-tech mb-2">Reviewer action</legend>
        <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-5">
          {ACTIONS.map((a) => {
            const Icon = a.icon;
            const on = action === a.key;
            return (
              <label
                key={a.key}
                title={a.hint}
                className={cn(
                  "flex cursor-pointer items-center justify-center gap-1.5 rounded-sm border px-2 py-2 text-[12px] transition-colors has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-cyan",
                  on ? (a.key === "CONFIRM" ? "border-green/60 bg-green/10 text-green" : a.key === "REJECT" ? "border-red/60 bg-red/10 text-red" : "border-amber/60 bg-amber/10 text-amber") : "border-border text-fg-2 hover:border-border-strong hover:text-fg",
                )}
              >
                <input type="radio" name={`${idPrefix}-action`} value={a.key} checked={on} onChange={() => setAction(a.key)} className="sr-only" />
                <Icon className="size-3.5" aria-hidden />
                {a.label}
              </label>
            );
          })}
        </div>
      </fieldset>

      {action === "CHANGE" || action === "REJECT" ? (
        <div className="grid gap-2 sm:grid-cols-3">
          <Field label="SCL class" htmlFor={`${idPrefix}-scl`}>
            <Select id={`${idPrefix}-scl`} value={scl} onChange={(e) => setScl(e.target.value)}>
              <option value="">Keep ({current.scl_class ? SCL_META[current.scl_class]?.label ?? current.scl_class : "—"})</option>
              {Object.entries(SCL_META).map(([k, v]) => (
                <option key={k} value={k}>
                  {v.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="SIF potential" htmlFor={`${idPrefix}-sif`}>
            <Select id={`${idPrefix}-sif`} value={sif} onChange={(e) => setSif(e.target.value)}>
              <option value="">{action === "REJECT" ? "Derive / flip" : "Derive from class"}</option>
              <option value="true">Yes — SIF potential</option>
              <option value="false">No — not SIF potential</option>
            </Select>
          </Field>
          <Field label="Life-Saving Rule" htmlFor={`${idPrefix}-lsr`}>
            <Select id={`${idPrefix}-lsr`} value={lsr} onChange={(e) => setLsr(e.target.value)}>
              <option value="">Keep ({current.primary_lsr ? LSR_SHORT[current.primary_lsr] : "—"})</option>
              {Object.entries(LSR_SHORT).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </Select>
          </Field>
        </div>
      ) : null}

      {action !== "NOTE" ? (
        <Field label={needsReason ? "Reason (required)" : "Reason"} htmlFor={`${idPrefix}-reason`}>
          <Textarea id={`${idPrefix}-reason`} value={reason} onChange={(e) => setReason(e.target.value)} className="min-h-16" placeholder={needsReason ? "Why is the AI classification wrong?" : "Optional rationale"} required={needsReason} />
        </Field>
      ) : null}
      <Field label={action === "NOTE" ? "Note (required)" : "Note"} htmlFor={`${idPrefix}-note`}>
        <Textarea id={`${idPrefix}-note`} value={note} onChange={(e) => setNote(e.target.value)} className="min-h-14" placeholder="Follow-up, context, actions assigned…" required={action === "NOTE"} />
      </Field>
      {error ? (
        <p role="alert" className="text-[12.5px] text-red">
          {error}
        </p>
      ) : null}
      <div className="flex items-center justify-between gap-3">
        <p className="text-[11.5px] text-muted">Decision, identity and timestamp are recorded in the audit log and stored as a feedback example.</p>
        <Button type="submit" variant={action === "CONFIRM" ? "primary" : "amber"} loading={busy} disabled={changeInvalid || (needsReason && !reason.trim()) || (action === "NOTE" && !note.trim())}>
          {action === "NOTE" ? "Save note" : "Record decision"}
        </Button>
      </div>
    </form>
  );
}
