"use client";

import { AppShell } from "@/components/shell/AppShell";
import { AuthProvider, useAuth } from "@/lib/auth";

function Gate({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center" role="status">
        <span className="label-tech">Verifying session…</span>
      </div>
    );
  }
  return <AppShell>{children}</AppShell>;
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <Gate>{children}</Gate>
    </AuthProvider>
  );
}
