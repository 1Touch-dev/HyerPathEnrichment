"use client";

import { RefreshCw } from "lucide-react";
import { EmptyState } from "@/components/console/EmptyState";
import { DeskMetricCard, DeskMetricGrid } from "@/components/desk/desk-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  SectionHeader,
  SectionHeaderActions,
  SectionHeaderContent,
  SectionHeaderDescription,
  SectionHeaderTitle,
} from "@/components/ui/section-header";
import { useJobMatchAnalytics } from "../hooks/useAnalytics";

function formatCurrency(value: number | null): string {
  if (value === null) return "—";
  return `$${value.toLocaleString()}`;
}

/**
 * Aggregate stats, not a full analytics suite — labeled explicitly in the UI
 * to keep the scope boundary from docs/admin-module-research.md §6 visible
 * to whoever uses the screen, not just documented in the plan (§12.4).
 */
export function AnalyticsPanel() {
  const { data, isLoading, isRefetching, refresh } = useJobMatchAnalytics();

  async function handleRefresh() {
    await refresh();
  }

  if (isLoading && !data) {
    return <p className="text-sm text-muted-foreground">Loading analytics…</p>;
  }
  if (!data) {
    return <EmptyState title="No analytics available" description="Could not load analytics." />;
  }

  const topCompanies = data.topCompanies.slice(0, 10);
  const postingsBySource = Object.entries(data.postingsBySource);
  const maxSourceCount = Math.max(1, ...postingsBySource.map(([, count]) => count));

  return (
    <div className="flex flex-col gap-6">
      <SectionHeader>
        <SectionHeaderContent>
          <SectionHeaderTitle>Job match analytics</SectionHeaderTitle>
          <SectionHeaderDescription>
            Aggregate stats, not a full analytics suite.
          </SectionHeaderDescription>
        </SectionHeaderContent>
        <SectionHeaderActions>
          <Badge variant={data.cacheHit ? "secondary" : "outline"}>
            {data.cacheHit ? "Cache hit" : "Freshly computed"}
          </Badge>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void handleRefresh()}
            disabled={isRefetching}
          >
            <RefreshCw className="mr-1 size-3" />
            Refresh
          </Button>
        </SectionHeaderActions>
      </SectionHeader>

      <DeskMetricGrid>
        <DeskMetricCard
          label="Tracked job postings"
          value={data.totalPostings.toLocaleString()}
          hint="Current analytics sample"
        />
        <DeskMetricCard
          label="Generated matches"
          value={data.totalMatches.toLocaleString()}
          hint="Across the sampled postings"
          tone="info"
        />
        <DeskMetricCard
          label="Average salary range"
          value={
            <span className="text-lg">
              {formatCurrency(data.avgSalaryMin)} – {formatCurrency(data.avgSalaryMax)}
            </span>
          }
          hint="Null values remain honest"
        />
        <DeskMetricCard
          label="Average match score"
          value={data.avgOverallScore !== null ? Math.round(data.avgOverallScore) : "—"}
          hint="Rounded for quick scanning"
          tone="success"
        />
      </DeskMetricGrid>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Postings by source</CardTitle>
          </CardHeader>
          <CardContent>
            {postingsBySource.length ? (
              <div className="flex flex-col gap-2">
                {postingsBySource.map(([source, count]) => (
                  <div key={source} className="flex items-center gap-2">
                    <span className="w-24 truncate text-sm">{source}</span>
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-primary"
                        style={{ width: `${(count / maxSourceCount) * 100}%` }}
                      />
                    </div>
                    <span className="w-12 text-right text-sm text-muted-foreground">{count}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No postings yet.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Top 10 companies</CardTitle>
          </CardHeader>
          <CardContent>
            {topCompanies.length ? (
              <ol className="flex flex-col gap-1">
                {topCompanies.map((entry, index) => (
                  <li key={entry.company} className="flex items-center justify-between text-sm">
                    <span>
                      {index + 1}. {entry.company}
                    </span>
                    <span className="text-muted-foreground">{entry.count}</span>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="text-sm text-muted-foreground">No company data yet.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
