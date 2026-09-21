"use client";

import { EmptyState } from "@/components/console/EmptyState";
import { DeskMetricCard, DeskMetricGrid } from "@/components/desk/desk-shell";
import { Badge } from "@/components/ui/badge";
import {
  SectionHeader,
  SectionHeaderContent,
  SectionHeaderDescription,
  SectionHeaderTitle,
} from "@/components/ui/section-header";
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
    return (
      <EmptyState title="System health unavailable" description="Could not load health data." />
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <DeskMetricGrid className="lg:grid-cols-3">
        <DeskMetricCard
          label="Database latency"
          value={`${data.databaseLatencyMs} ms`}
          hint={<StatusBadge ok={data.databaseOk} />}
          tone={data.databaseOk ? "success" : "danger"}
        />
        <DeskMetricCard
          label="Redis latency"
          value={`${data.redisLatencyMs} ms`}
          hint={<StatusBadge ok={data.redisOk} />}
          tone={data.redisOk ? "success" : "danger"}
        />
        <DeskMetricCard
          label="Prometheus source"
          value={data.prometheusConfigured ? "Configured" : "Unavailable"}
          hint="Golden signals degrade gracefully when the query source is not configured."
          tone={data.prometheusConfigured ? "info" : "warning"}
        />
      </DeskMetricGrid>

      <section className="flex flex-col gap-4">
        <SectionHeader>
          <SectionHeaderContent>
            <SectionHeaderTitle>Self-checks</SectionHeaderTitle>
            <SectionHeaderDescription>
              Core service checks that should always report, even when the observability stack is
              only partially configured.
            </SectionHeaderDescription>
          </SectionHeaderContent>
        </SectionHeader>
        <DeskMetricGrid className="lg:grid-cols-2">
          <DeskMetricCard
            label="Database"
            value={`${data.databaseLatencyMs} ms`}
            hint={<StatusBadge ok={data.databaseOk} />}
            tone={data.databaseOk ? "success" : "danger"}
          />
          <DeskMetricCard
            label="Redis"
            value={`${data.redisLatencyMs} ms`}
            hint={<StatusBadge ok={data.redisOk} />}
            tone={data.redisOk ? "success" : "danger"}
          />
        </DeskMetricGrid>
      </section>

      <section className="flex flex-col gap-4">
        <SectionHeader>
          <SectionHeaderContent>
            <SectionHeaderTitle>Golden signals</SectionHeaderTitle>
            <SectionHeaderDescription>
              High-level demand and reliability indicators shown only when Prometheus wiring is
              available.
            </SectionHeaderDescription>
          </SectionHeaderContent>
        </SectionHeader>
        {data.prometheusConfigured ? (
          <DeskMetricGrid>
            {Object.entries(data.signals).map(([key, value]) => (
              <DeskMetricCard
                key={key}
                label={SIGNAL_LABELS[key] ?? key}
                value={value ?? "—"}
                hint="Prometheus-backed metric"
                tone="info"
              />
            ))}
          </DeskMetricGrid>
        ) : (
          <EmptyState
            title="Golden signals not configured"
            description="Set PROMETHEUS_QUERY_URL to enable the golden-signals panel."
          />
        )}
      </section>
    </div>
  );
}
