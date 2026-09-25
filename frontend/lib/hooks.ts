"use client";

import { useQueryClient } from "@tanstack/react-query";
import * as React from "react";

/** After any write, refresh every view that aggregates reports so the dashboard updates. */
export function useInvalidateAll() {
  const qc = useQueryClient();
  return React.useCallback(() => {
    for (const k of ["reports", "dashboard", "review", "review-stats", "ranking", "patterns", "pattern", "audit", "model", "report"]) qc.invalidateQueries({ queryKey: [k] });
  }, [qc]);
}
