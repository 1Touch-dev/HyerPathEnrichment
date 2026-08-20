"use client";

import { RefreshCw } from "lucide-react";
import { EmptyState } from "@/components/console/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Job match analytics</h2>
          <p className="text-sm text-muted-foreground">
            Aggregate stats, not a full analytics suite.
          </p>
        </div>
        <div className="flex items-center gap-2">
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
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total postings
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">{data.totalPostings.toLocaleString()}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total matches
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">{data.totalMatches.toLocaleString()}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Avg salary range
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-lg font-semibold">
              {formatCurrency(data.avgSalaryMin)} – {formatCurrency(data.avgSalaryMax)}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Avg match score
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">
              {data.avgOverallScore !== null ? Math.round(data.avgOverallScore) : "—"}
            </p>
          </CardContent>
        </Card>
      </div>

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
