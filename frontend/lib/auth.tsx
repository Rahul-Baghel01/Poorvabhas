"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter } from "next/navigation";
import * as React from "react";

import { api, ApiError } from "@/lib/api";
import type { User } from "@/lib/types";

interface AuthCtx {
  user: User | null;
  loading: boolean;
  can: (perm: string) => boolean;
  logout: () => Promise<void>;
}

const Ctx = React.createContext<AuthCtx>({ user: null, loading: true, can: () => false, logout: async () => {} });

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const qc = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api<{ user: User }>("/auth/me"),
    retry: (n, e) => !(e instanceof ApiError && e.status === 401) && n < 2,
    staleTime: 60_000,
  });
  const user = me.data?.user ?? null;

  React.useEffect(() => {
    if (me.error instanceof ApiError && me.error.status === 401 && pathname !== "/login") {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [me.error, pathname, router]);

  const value = React.useMemo<AuthCtx>(
    () => ({
      user,
      loading: me.isLoading,
      can: (perm) => !!user?.permissions.includes(perm),
      logout: async () => {
        await api("/auth/logout", { method: "POST" }).catch(() => undefined);
        qc.clear();
        router.replace("/login");
      },
    }),
    [user, me.isLoading, qc, router],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  return React.useContext(Ctx);
}
