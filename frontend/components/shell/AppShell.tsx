"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  BookOpen,
  ClipboardCheck,
  Cpu,
  FileText,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  Network,
  Settings,
  Upload,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import * as React from "react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/format";

interface NavItem {
  href: string;
  label: string;
  icon: React.ElementType;
  perm: string;
  count?: "review";
}

const PRIMARY: NavItem[] = [
  { href: "/", label: "Command Center", icon: LayoutDashboard, perm: "dashboard" },
  { href: "/reports", label: "Safety Reports", icon: FileText, perm: "reports" },
  { href: "/patterns", label: "Pattern Explorer", icon: Network, perm: "patterns" },
  { href: "/import", label: "Import Data", icon: Upload, perm: "import" },
];
const ADMIN: NavItem[] = [
  { href: "/taxonomy", label: "Taxonomy", icon: BookOpen, perm: "taxonomy" },
  { href: "/review", label: "Review Queue", icon: ClipboardCheck, perm: "review", count: "review" },
  { href: "/model", label: "Model / Analysis", icon: Cpu, perm: "analysis" },
  { href: "/settings", label: "Settings", icon: Settings, perm: "settings" },
  { href: "/audit", label: "Audit Log", icon: History, perm: "audit" },
];

const TITLES: [RegExp, string][] = [
  [/^\/$/, "Command Center"],
  [/^\/reports\/new/, "New Report"],
  [/^\/reports\/.+/, "Report Detail"],
  [/^\/reports/, "Safety Reports"],
  [/^\/patterns\/.+/, "Pattern Detail"],
  [/^\/patterns/, "Pattern Explorer"],
  [/^\/import/, "Import Data"],
  [/^\/taxonomy/, "Taxonomy"],
  [/^\/review/, "Review Queue"],
  [/^\/model/, "Model / Analysis"],
  [/^\/settings/, "Settings"],
  [/^\/audit/, "Audit Log"],
];

function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <path d="M16 4 28 26H4Z" fill="none" stroke="#FF4A43" strokeWidth="2.5" strokeLinejoin="round" />
      <circle cx="16" cy="19.5" r="2.4" fill="#F4F5F5" />
    </svg>
  );
}

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(href + "/");
}

function NavList({ items, title, onNavigate, reviewCount }: { items: NavItem[]; title?: string; onNavigate?: () => void; reviewCount?: number }) {
  const pathname = usePathname();
  const { can } = useAuth();
  const visible = items.filter((i) => can(i.perm));
  if (!visible.length) return null;
  return (
    <div className="flex flex-col gap-0.5">
      {title ? <p className="label-tech mb-1.5 mt-5 px-3">{title}</p> : null}
      {visible.map((item) => {
        const active = isActive(pathname, item.href);
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "group relative flex h-9 items-center gap-3 rounded-sm px-3 text-[13.5px] transition-colors",
              active ? "bg-surface-3 text-fg" : "text-fg-2 hover:bg-surface-2 hover:text-fg",
            )}
          >
            {active ? <span className="absolute left-0 top-1.5 h-6 w-[2px] rounded-full bg-red" aria-hidden /> : null}
            <Icon className={cn("size-4", active ? "text-fg" : "text-muted group-hover:text-fg-2")} aria-hidden />
            <span className="flex-1">{item.label}</span>
            {item.count === "review" && reviewCount ? (
              <span className="num rounded-xs bg-amber/15 px-1.5 font-mono text-[11px] text-amber" aria-label={`${reviewCount} open reviews`}>
                {reviewCount}
              </span>
            ) : null}
          </Link>
        );
      })}
    </div>
  );
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { can } = useAuth();
  const stats = useQuery({ queryKey: ["review-stats"], queryFn: () => api<{ open: number }>("/review/stats"), enabled: can("review"), refetchInterval: 60_000 });
  return (
    <div className="flex h-full flex-col">
      <Link href="/" onClick={onNavigate} className="flex items-center gap-3 px-4 pb-5 pt-5">
        <BrandMark className="size-7" />
        <span className="flex flex-col">
          <span className="text-[15px] font-semibold tracking-[0.18em] text-fg">POORVABHAS</span>
          <span className="font-mono text-[9.5px] uppercase tracking-[0.14em] text-muted">SIF precursor intelligence</span>
        </span>
      </Link>
      <nav aria-label="Main" className="flex-1 overflow-y-auto px-2">
        <NavList items={PRIMARY} onNavigate={onNavigate} />
        <NavList items={ADMIN} title="Administration" onNavigate={onNavigate} reviewCount={stats.data?.open} />
      </nav>
      <div className="m-3 rounded-sm border border-border bg-surface-2 p-3">
        <p className="label-tech !text-amber">Decision support</p>
        <p className="mt-1.5 text-[12px] leading-snug text-fg-2">Judge the hazard, not the outcome. Final safety decisions belong to the HSE reviewer.</p>
      </div>
    </div>
  );
}

function SystemStatus() {
  const h = useQuery({ queryKey: ["health"], queryFn: () => api<{ status: string; database: string }>("/health"), refetchInterval: 30_000, retry: false });
  const ok = h.data?.status === "ok";
  const label = h.isLoading ? "Checking systems" : ok ? "Systems operational" : h.data ? "Database unavailable" : "Analysis service unreachable";
  return (
    <span className="hidden items-center gap-2 text-[12px] text-fg-2 md:inline-flex" role="status" aria-live="polite">
      <span className={cn("relative flex size-2")}>
        {ok ? <span className="absolute inline-flex size-full animate-ping rounded-full bg-green opacity-40" /> : null}
        <span className={cn("relative inline-flex size-2 rounded-full", ok ? "bg-green" : h.isLoading ? "bg-muted" : "bg-red")} />
      </span>
      {label}
    </span>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [open, setOpen] = React.useState(false);
  const title = TITLES.find(([re]) => re.test(pathname))?.[1] ?? "";

  return (
    <div className="flex min-h-screen">
      <a href="#main" className="sr-only z-50 rounded-sm bg-fg px-3 py-2 text-bg focus:not-sr-only focus:fixed focus:left-3 focus:top-3">
        Skip to content
      </a>
      <aside className="sticky top-0 hidden h-screen w-[248px] shrink-0 border-r border-border bg-[#0b0f10] lg:block">
        <SidebarContent />
      </aside>

      <Dialog.Root open={open} onOpenChange={setOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-40 bg-black/70 lg:hidden" />
          <Dialog.Content className="fixed inset-y-0 left-0 z-50 w-[272px] border-r border-border bg-[#0b0f10] lg:hidden" aria-describedby={undefined}>
            <Dialog.Title className="sr-only">Navigation</Dialog.Title>
            <Dialog.Close className="absolute right-3 top-5 rounded-sm p-1 text-muted hover:text-fg" aria-label="Close navigation">
              <X className="size-5" />
            </Dialog.Close>
            <SidebarContent onNavigate={() => setOpen(false)} />
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="hazard-stripe h-[3px] w-full" aria-hidden />
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-bg/95 px-4 backdrop-blur md:px-6">
          <button className="rounded-sm p-1.5 text-fg-2 hover:bg-surface-2 lg:hidden" onClick={() => setOpen(true)} aria-label="Open navigation">
            <Menu className="size-5" />
          </button>
          <nav aria-label="Breadcrumb" className="min-w-0 flex-1">
            <ol className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.14em]">
              <li className="text-muted">Poorvabhas</li>
              <li className="text-muted" aria-hidden>
                /
              </li>
              <li className="truncate text-fg" aria-current="page">
                {title}
              </li>
            </ol>
          </nav>
          <span className="inline-flex shrink-0 items-center gap-1.5 rounded-xs border border-amber/40 bg-amber/10 px-2 py-1 font-mono text-[10px] uppercase tracking-[0.1em] text-amber" title="All data in this environment is synthetic. No OIL production data.">
            <Activity className="size-3" aria-hidden />
            <span className="hidden xl:inline">Demo environment — synthetic safety data</span>
            <span className="xl:hidden">Synthetic<span className="hidden sm:inline"> / proxy data</span></span>
          </span>
          <SystemStatus />
          {user ? (
            <div className="flex items-center gap-3 border-l border-border pl-3">
              <div className="hidden text-right sm:block">
                <p className="text-[12.5px] font-medium leading-tight text-fg">{user.full_name}</p>
                <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-cyan">{user.role_label}</p>
              </div>
              <button onClick={logout} className="rounded-sm p-1.5 text-muted hover:bg-surface-2 hover:text-fg" aria-label="Sign out" title="Sign out">
                <LogOut className="size-4" />
              </button>
            </div>
          ) : null}
        </header>
        <main id="main" className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-6 md:px-6 lg:px-8 lg:py-8">
          {children}
        </main>
      </div>
    </div>
  );
}
