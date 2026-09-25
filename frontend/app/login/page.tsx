"use client";

import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import * as React from "react";

import { Button, Field, Input } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";

const DEMO = [
  { u: "admin", p: "Admin@2026", role: "HSE Admin" },
  { u: "officer", p: "Officer@2026", role: "HSE Officer" },
  { u: "reviewer", p: "Reviewer@2026", role: "HSE Officer (reviewer)" },
];

const FLOW = ["Free-text report", "NLP evidence", "Energy + control", "SCL class", "IOGP rule", "Patterns", "Fair ranking", "Human review"];

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const qc = useQueryClient();
  const [username, setUsername] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("/auth/login", { method: "POST", json: { username, password } });
      qc.clear();
      const next = params.get("next");
      router.replace(next && next.startsWith("/") && !next.startsWith("//") ? next : "/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sign-in failed");
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4" aria-label="Sign in">
      <Field label="Username" htmlFor="username" required>
        <Input id="username" name="username" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required autoFocus />
      </Field>
      <Field label="Password" htmlFor="password" required>
        <Input id="password" name="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
      </Field>
      {error ? (
        <p role="alert" className="rounded-sm border border-red/40 bg-red/10 px-3 py-2 text-[13px] text-red">
          {error}
        </p>
      ) : null}
      <Button type="submit" variant="primary" loading={busy} className="h-10">
        Sign in <ArrowRight className="size-4" aria-hidden />
      </Button>
      <div className="mt-2 rounded-sm border border-border bg-surface-2 p-3">
        <p className="label-tech">Demo credentials</p>
        <ul className="mt-2 flex flex-col gap-1">
          {DEMO.map((d) => (
            <li key={d.u}>
              <button
                type="button"
                onClick={() => {
                  setUsername(d.u);
                  setPassword(d.p);
                }}
                className="flex w-full items-center justify-between rounded-xs px-2 py-1.5 text-left font-mono text-[12px] text-fg-2 hover:bg-surface-3 hover:text-fg"
              >
                <span>
                  {d.u} / {d.p}
                </span>
                <span className="text-[10.5px] uppercase tracking-wider text-muted">{d.role}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </form>
  );
}

export default function LoginPage() {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1.15fr_1fr]">
      <section className="grid-bg relative hidden flex-col justify-between overflow-hidden border-r border-border bg-[#0a0e0f] p-12 lg:flex" aria-label="About Poorvabhas">
        <div className="flex items-center gap-3">
          <svg viewBox="0 0 32 32" className="size-8" aria-hidden>
            <path d="M16 4 28 26H4Z" fill="none" stroke="#FF4A43" strokeWidth="2.5" strokeLinejoin="round" />
            <circle cx="16" cy="19.5" r="2.4" fill="#F4F5F5" />
          </svg>
          <span className="text-[17px] font-semibold tracking-[0.2em]">POORVABHAS</span>
        </div>
        <div className="max-w-xl">
          <p className="label-tech !text-red">SIH 2026 · PS 26165 · Oil India Limited</p>
          <h1 className="mt-4 text-[44px] font-semibold leading-[1.05] tracking-[-0.02em]">
            Sensing the fatality
            <br />
            before it happens.
          </h1>
          <p className="mt-5 max-w-lg text-[15px] leading-relaxed text-fg-2">
            AI/NLP decision support that reads unsafe-act, unsafe-condition and near-miss reports, reasons about the hazard with the SCL model, and shows HSE teams where fatal potential is concentrated.
          </p>
          <ol className="mt-8 flex flex-wrap items-center gap-x-2 gap-y-2 font-mono text-[11px] uppercase tracking-[0.1em] text-fg-2" aria-label="Analysis flow">
            {FLOW.map((f, i) => (
              <li key={f} className="flex items-center gap-2">
                <span className="rounded-xs border border-border bg-surface px-2 py-1">{f}</span>
                {i < FLOW.length - 1 ? <span className="text-muted" aria-hidden>→</span> : null}
              </li>
            ))}
          </ol>
        </div>
        <div className="flex items-end justify-between gap-6">
          <p className="max-w-md text-[12.5px] leading-relaxed text-muted">
            <span className="font-semibold text-fg-2">Judge the hazard, not the outcome.</span> This system does not predict fatalities or individual outcomes; it prioritises attention. Final safety decisions belong to the HSE reviewer.
          </p>
          <span className="shrink-0 rounded-xs border border-amber/40 bg-amber/10 px-2 py-1 font-mono text-[10px] uppercase tracking-[0.1em] text-amber">Synthetic demo data</span>
        </div>
      </section>
      <section className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <p className="text-[17px] font-semibold tracking-[0.2em]">POORVABHAS</p>
            <p className="mt-1 text-[13px] text-fg-2">Sensing the fatality before it happens.</p>
          </div>
          <div className="mb-6 flex items-center gap-2">
            <ShieldCheck className="size-5 text-cyan" aria-hidden />
            <h2 className="text-[20px] font-semibold">Sign in to HSE intelligence</h2>
          </div>
          <React.Suspense>
            <LoginForm />
          </React.Suspense>
          <p className="mt-6 font-mono text-[10.5px] uppercase tracking-[0.1em] text-muted">Demo environment — synthetic safety data</p>
        </div>
      </section>
    </div>
  );
}
