"use client";

import { Lock } from "lucide-react";

import { EmptyState } from "@/components/ui/primitives";
import { useAuth } from "@/lib/auth";

export function RequirePermission({ perm, children }: { perm: string; children: React.ReactNode }) {
  const { can, user } = useAuth();
  if (!can(perm)) {
    return <EmptyState icon={Lock} title="Restricted to HSE Admin" description={`Your role (${user?.role_label ?? "unknown"}) does not include access to this area.`} />;
  }
  return <>{children}</>;
}
