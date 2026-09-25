"use client";

import { AlertTriangle, CircleX, Inbox, LoaderCircle, RefreshCw } from "lucide-react";
import * as React from "react";

import { cn, type Tone } from "@/lib/format";

/* ------------------------------------------------------------------ Button */
type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "amber";
const BTN: Record<ButtonVariant, string> = {
  primary: "bg-fg text-bg hover:bg-white border-fg",
  secondary: "bg-surface-2 text-fg border-border hover:border-border-strong hover:bg-surface-3",
  ghost: "bg-transparent text-fg-2 border-transparent hover:text-fg hover:bg-surface-2",
  danger: "bg-red/10 text-red border-red/40 hover:bg-red/20",
  amber: "bg-amber text-bg border-amber hover:brightness-110",
};

export const Button = React.forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: "sm" | "md"; loading?: boolean }>(
  function Button({ className, variant = "secondary", size = "md", loading, disabled, children, ...props }, ref) {
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={cn(
          "inline-flex items-center justify-center gap-2 rounded-sm border font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
          size === "sm" ? "h-8 px-3 text-[12.5px]" : "h-9 px-4 text-[13px]",
          BTN[variant],
          className,
        )}
        {...props}
      >
        {loading ? <LoaderCircle className="size-4 animate-spin" aria-hidden /> : null}
        {children}
      </button>
    );
  },
);

/* ------------------------------------------------------------------ Badge */
const TONE_BADGE: Record<Tone, string> = {
  red: "text-red border-red/35 bg-red/10",
  "red-deep": "text-[#ff8a80] border-red-deep/60 bg-red-deep/25",
  amber: "text-amber border-amber/35 bg-amber/10",
  cyan: "text-cyan border-cyan/35 bg-cyan/10",
  green: "text-green border-green/35 bg-green/10",
  neutral: "text-fg-2 border-border-strong bg-surface-3",
};

export function Badge({ tone = "neutral", className, children, dot, ...rest }: React.HTMLAttributes<HTMLSpanElement> & { tone?: Tone; dot?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 whitespace-nowrap rounded-xs border px-1.5 py-[1px] font-mono text-[10.5px] font-medium uppercase tracking-[0.06em]", TONE_BADGE[tone], className)} {...rest}>
      {dot ? <span className="size-1.5 rounded-full bg-current" aria-hidden /> : null}
      {children}
    </span>
  );
}

/* ------------------------------------------------------------------ Panel */
export function Panel({ title, subtitle, actions, className, bodyClassName, children, id, accent }: {
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
  bodyClassName?: string;
  children?: React.ReactNode;
  id?: string;
  accent?: Tone;
}) {
  const accentBar = accent ? { red: "bg-red", "red-deep": "bg-red-deep", amber: "bg-amber", cyan: "bg-cyan", green: "bg-green", neutral: "bg-border-strong" }[accent] : null;
  return (
    <section id={id} aria-labelledby={title && id ? `${id}-title` : undefined} className={cn("relative min-w-0 rounded-md border border-border bg-surface", className)}>
      {accentBar ? <span className={cn("absolute left-0 top-0 h-full w-[2px] rounded-l-md", accentBar)} aria-hidden /> : null}
      {title || actions ? (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-4 py-3">
          <div className="min-w-0">
            {title ? (
              <h2 id={id ? `${id}-title` : undefined} className="label-tech !text-fg-2">
                {title}
              </h2>
            ) : null}
            {subtitle ? <p className="mt-1 text-[12px] text-muted">{subtitle}</p> : null}
          </div>
          {actions ? <div className="flex max-w-full flex-wrap items-center gap-2">{actions}</div> : null}
        </header>
      ) : null}
      <div className={cn("p-4", bodyClassName)}>{children}</div>
    </section>
  );
}

/* ------------------------------------------------------------------ Page header */
export function PageHeader({ eyebrow, title, subtitle, actions }: { eyebrow: string; title: string; subtitle?: string; actions?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div className="min-w-0">
        <p className="label-tech">{eyebrow}</p>
        <h1 className="mt-2 text-[28px] font-semibold leading-tight tracking-[-0.01em] text-fg md:text-[32px]">{title}</h1>
        {subtitle ? <p className="mt-2 max-w-2xl text-[14px] text-fg-2">{subtitle}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

/* ------------------------------------------------------------------ Form controls */
const CONTROL = "w-full rounded-sm border border-border bg-bg px-3 text-[13px] text-fg placeholder:text-muted/70 hover:border-border-strong focus:border-cyan/70 disabled:opacity-60";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(function Input({ className, ...p }, ref) {
  return <input ref={ref} className={cn(CONTROL, "h-9", className)} {...p} />;
});

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea({ className, ...p }, ref) {
  return <textarea ref={ref} className={cn(CONTROL, "min-h-24 py-2 leading-relaxed", className)} {...p} />;
});

export const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(function Select({ className, children, ...p }, ref) {
  return (
    <select ref={ref} className={cn(CONTROL, "h-9 appearance-none bg-[url('data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2210%22 height=%226%22><path d=%22M0 0l5 6 5-6z%22 fill=%22%238a9597%22/></svg>')] bg-[length:10px_6px] bg-[right_10px_center] bg-no-repeat pr-8", className)} {...p}>
      {children}
    </select>
  );
});

export function Field({ label, htmlFor, required, hint, error, children, className }: { label: string; htmlFor: string; required?: boolean; hint?: string; error?: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={htmlFor} className="label-tech !text-fg-2">
        {label}
        {required ? <span className="ml-1 text-red" aria-hidden>*</span> : null}
      </label>
      {children}
      {error ? (
        <p className="text-[12px] text-red" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p className="text-[12px] text-muted">{hint}</p>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ States */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-sm bg-surface-3", className)} aria-hidden />;
}

export function LoadingState({ label = "Loading", rows = 3 }: { label?: string; rows?: number }) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-2">
      <span className="sr-only">{label}…</span>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-8" />
      ))}
    </div>
  );
}

export function EmptyState({ title, description, action, icon: Icon = Inbox }: { title: string; description?: string; action?: React.ReactNode; icon?: React.ElementType }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-10 text-center">
      <Icon className="size-6 text-muted" aria-hidden />
      <p className="text-[14px] font-medium text-fg">{title}</p>
      {description ? <p className="max-w-md text-[13px] text-muted">{description}</p> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}

export function ErrorState({ error, onRetry, title = "Analysis unavailable" }: { error: unknown; onRetry?: () => void; title?: string }) {
  const msg = error instanceof Error ? error.message : String(error ?? "Unknown error");
  return (
    <div role="alert" className="flex flex-col items-center justify-center gap-2 rounded-md border border-red/30 bg-red/5 px-6 py-8 text-center">
      <CircleX className="size-6 text-red" aria-hidden />
      <p className="text-[14px] font-medium text-fg">{msg === "Database connection unavailable" ? msg : title}</p>
      <p className="max-w-md text-[13px] text-fg-2">{msg}</p>
      {onRetry ? (
        <Button size="sm" onClick={onRetry} className="mt-2">
          <RefreshCw className="size-3.5" aria-hidden /> Retry
        </Button>
      ) : null}
    </div>
  );
}

export function Notice({ tone = "amber", title, children, className }: { tone?: Tone; title?: string; children: React.ReactNode; className?: string }) {
  const map: Record<Tone, string> = { amber: "border-amber/35 bg-amber/[0.07] text-amber", red: "border-red/35 bg-red/[0.07] text-red", cyan: "border-cyan/35 bg-cyan/[0.07] text-cyan", green: "border-green/35 bg-green/[0.07] text-green", neutral: "border-border bg-surface-2 text-fg-2", "red-deep": "border-red/35 bg-red/[0.07] text-red" };
  return (
    <div className={cn("flex gap-3 rounded-sm border px-3 py-2.5 text-[13px]", map[tone], className)} role="note">
      <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="text-fg-2">
        {title ? <p className="font-medium text-fg">{title}</p> : null}
        {children}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ Meter */
export function Meter({ value, max = 1, tone = "cyan", label, className }: { value: number; max?: number; tone?: Tone; label: string; className?: string }) {
  const pctv = Math.max(0, Math.min(1, max ? value / max : 0));
  const bg = { red: "bg-red", "red-deep": "bg-red-deep", amber: "bg-amber", cyan: "bg-cyan", green: "bg-green", neutral: "bg-neutral-mark" }[tone];
  return (
    <div className={cn("h-1.5 w-full overflow-hidden rounded-full bg-surface-3", className)} role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={max} aria-valuenow={value}>
      <div className={cn("h-full rounded-full", bg)} style={{ width: `${pctv * 100}%` }} />
    </div>
  );
}

export function KV({ k, v, mono }: { k: string; v: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <dt className="label-tech">{k}</dt>
      <dd className={cn("truncate text-[13.5px] text-fg", mono && "font-mono text-[12.5px]")}>{v ?? <span className="text-muted">Not stated</span>}</dd>
    </div>
  );
}
