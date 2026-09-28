"use client";

import { CheckCircle2, CircleHelp, PencilLine, SlidersHorizontal, StickyNote } from "lucide-react";
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

type Choice = "CONFIRM" | "CORRECT" | "REFINE";
type Refinement = "INSUFFICIENT" | "NOTE";

const CHOICES: { key: Choice; label: string; icon: React.ElementType; hint: string }[] = [
  { key: "CONFIRM", label: "Confirm", icon: CheckCircle2, hint: "The engine classification is correct" },
  { key: "CORRECT", label: "Correct", icon: PencilLine, hint: "Set the correct SCL class, SIF-potential or Life-Saving Rule" },
  { key: "REFINE", label: "Refine", icon: SlidersHorizontal, hint: "Mark insufficient information, or add a note without closing the review" },
];

const REFINEMENTS: { key: Refinement; label: string; icon: React.ElementType; hint: string }[] = [
  { key: "INSUFFICIENT", label: "Insufficient information", icon: CircleHelp, hint: "The report cannot be classified as written" },
  { key: "NOTE", label: "Add note only", icon: StickyNote, hint: "Record a note; the review stays open" },
];

export function DecisionForm({ idPrefix, current, onSubmit, busy, error }: {
  idPrefix: string;
  current: { scl_class: string | null; sif_potential: boolean | null; primary_lsr: string | null };
  onSubmit: (p: DecisionPayload) => void;
  busy?: boolean;
  error?: string | null;
}) {
  const [choice, setChoice] = React.useState<Choice>("CONFIRM");
  const [refinement, setRefinement] = React.useState<Refinement>("INSUFFICIENT");
  const [scl, setScl] = React.useState<string>("");
  const [sif, setSif] = React.useState<string>("");
  const [lsr, setLsr] = React.useState<string>("");
  const [reason, setReason] = React.useState("");
  const [note, setNote] = React.useState("");
  const action: DecisionAction = choice === "CONFIRM" ? "CONFIRM" : choice === "CORRECT" ? "CHANGE" : refinement;
  const needsReason = action === "CHANGE";
  const changeInvalid = action === "CHANGE" && !scl && !sif && !lsr;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const p: DecisionPayload = { action, reason: reason || null, note: note || null };
    if (action === "CHANGE") {
      if (scl) p.scl_class = scl;
      if (sif) p.sif_potential = sif === "true";
      if (lsr) p.primary_lsr = lsr;
    }
    onSubmit(p);
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3" aria-label="Reviewer decision">
      <fieldset>
        <legend className="label-tech mb-2">HSE reviewer action</legend>
        <div className="grid grid-cols-3 gap-1.5">
          {CHOICES.map((a) => {
            const Icon = a.icon;
            const on = choice === a.key;
            return (
              <label
                key={a.key}
                title={a.hint}
                className={cn(
                  "flex cursor-pointer items-center justify-center gap-1.5 rounded-sm border px-2 py-2 text-[12px] transition-colors has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-cyan",
                  on ? (a.key === "CONFIRM" ? "border-green/60 bg-green/10 text-green" : "border-amber/60 bg-amber/10 text-amber") : "border-border text-fg-2 hover:border-border-strong hover:text-fg",
                )}
              >
                <input type="radio" name={`${idPrefix}-action`} value={a.key} checked={on} onChange={() => setChoice(a.key)} className="sr-only" />
                <Icon className="size-3.5" aria-hidden />
                {a.label}
              </label>
            );
          })}
        </div>
        <p className="mt-1.5 text-[11.5px] text-muted">{CHOICES.find((c) => c.key === choice)?.hint}.</p>
      </fieldset>

      {choice === "CORRECT" ? (
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
          <Field label="SIF-potential" htmlFor={`${idPrefix}-sif`}>
            <Select id={`${idPrefix}-sif`} value={sif} onChange={(e) => setSif(e.target.value)}>
              <option value="">Derive from SCL class</option>
              <option value="true">Yes — SIF-potential</option>
              <option value="false">No — not SIF-potential</option>
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

      {choice === "REFINE" ? (
        <fieldset>
          <legend className="sr-only">Refinement</legend>
          <div className="grid grid-cols-2 gap-1.5">
            {REFINEMENTS.map((r) => {
              const Icon = r.icon;
              const on = refinement === r.key;
              return (
                <label
                  key={r.key}
                  title={r.hint}
                  className={cn(
                    "flex cursor-pointer items-center justify-center gap-1.5 rounded-sm border px-2 py-1.5 text-[12px] transition-colors has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-cyan",
                    on ? "border-amber/60 bg-amber/10 text-amber" : "border-border text-fg-2 hover:border-border-strong hover:text-fg",
                  )}
                >
                  <input type="radio" name={`${idPrefix}-refine`} value={r.key} checked={on} onChange={() => setRefinement(r.key)} className="sr-only" />
                  <Icon className="size-3.5" aria-hidden />
                  {r.label}
                </label>
              );
            })}
          </div>
        </fieldset>
      ) : null}

      {action !== "NOTE" ? (
        <Field label={needsReason ? "Reason (required)" : "Reason"} htmlFor={`${idPrefix}-reason`}>
          <Textarea id={`${idPrefix}-reason`} value={reason} onChange={(e) => setReason(e.target.value)} className="min-h-16" placeholder={needsReason ? "Why is the engine classification wrong?" : "Optional rationale"} required={needsReason} />
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
        <p className="text-[11.5px] text-muted">
          {action === "NOTE"
            ? "The note is recorded in the audit log; the review stays open."
            : "Decision, reviewer and time are audited and stored as a labelled feedback example. Retraining is a separate, controlled admin action."}
        </p>
        <Button type="submit" variant={action === "CONFIRM" ? "primary" : "amber"} loading={busy} disabled={changeInvalid || (needsReason && !reason.trim()) || (action === "NOTE" && !note.trim())}>
          {action === "NOTE" ? "Save note" : "Record decision"}
        </Button>
      </div>
    </form>
  );
}
