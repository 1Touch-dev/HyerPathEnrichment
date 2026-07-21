"use client";

import { useCallback, useEffect, useState } from "react";
import { getHealth } from "@/src/lib/api-client";
import { HealthStatus } from "@/src/lib/types";

const POLL_INTERVAL_MS = 60_000;

export function useHealth() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [online, setOnline] = useState(true);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const status = await getHealth();
      setHealth(status.data);
      setOnline(status.data.status === "ok" || status.data.status === "ready");
    } catch {
      setHealth({ status: "error", service: "hyrepath-enrichment" });
      setOnline(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const interval = setInterval(() => {
      void refresh();
    }, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refresh]);

  return { health, online, loading, refresh };
}
