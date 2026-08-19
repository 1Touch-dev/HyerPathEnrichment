"use client";

import { EmptyState } from "@/components/console/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useSystemHealth } from "../hooks/useSystemHealth";

function StatusBadge({ ok }: { ok: boolean }) {
  return <Badge variant={ok ? "success" : "destructive"}>{ok ? "OK" : "Down"}</Badge>;
}

const SIGNAL_LABELS: Record<string, string> = {
  latency: "Latency",
  traffic: "Traffic",
  errors: "Errors",
  saturation: "Saturation",
};

/**
 * Two sections: always-populated self-checks, and golden signals shown only
 * when prometheusConfigured is true — the frontend half of the backend's
 * fail-soft design (§8.12): missing Prometheus config degrades the UI, it
 * doesn't error it.
 */
export function SystemHealthPanel() {
  const { data, isLoading } = useSystemHealth();

  if (isLoading && !data) {
    return <p className="text-sm text-muted-foreground">Loading system health…</p>;
  }
  if (!data) {
    return <EmptyState title="System health unavailable" description="Could not load health data." />;
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="mb-3 text-lg font-semibold">Self-checks</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Database</CardTitle>
              <StatusBadge ok={data.databaseOk} />
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-semibold">{data.databaseLatencyMs} ms</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Redis</CardTitle>
              <StatusBadge ok={data.redisOk} />
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-semibold">{data.redisLatencyMs} ms</p>
            </CardContent>
          </Card>
        </div>
      </div>

      <div>
        <h2 className="mb-3 text-lg font-semibold">Golden signals</h2>
        {data.prometheusConfigured ? (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {Object.entries(data.signals).map(([key, value]) => (
              <Card key={key}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium">
                    {SIGNAL_LABELS[key] ?? key}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-semibold">{value ?? "—"}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <EmptyState
            title="Golden signals not configured"
            description="Set PROMETHEUS_QUERY_URL to enable the golden-signals panel."
          />
        )}
      </div>
    </div>
  );
}
