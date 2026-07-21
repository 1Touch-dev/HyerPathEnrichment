'use client';

import Link from 'next/link';
import { JobHistoryTable } from '@/components/console/JobHistoryTable';
import { JobStatusBadge } from '@/components/console/JobStatusBadge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useJobMetricsQuery } from '@/features/history';
import { formatApiErrorMessage } from '@/src/lib/format-api-error';

export function DashboardView() {
  const { data, isLoading, error } = useJobMetricsQuery();

  const kpis = [
    { label: 'Total jobs', value: data?.total ?? 0 },
    { label: 'Success rate', value: data ? `${data.successRate}%` : '—' },
    { label: 'In progress', value: data?.running ?? 0 },
  ];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">Pipeline overview and recent enrichment activity.</p>
      </div>

      {error ? <p className="text-sm text-destructive">{formatApiErrorMessage(error)}</p> : null}

      <div className="grid gap-4 sm:grid-cols-3">
        {kpis.map((kpi) => (
          <Card key={kpi.label}>
            <CardHeader className="pb-2">
              <CardDescription>{kpi.label}</CardDescription>
              {isLoading ? (
                <Skeleton className="h-9 w-16" />
              ) : (
                <CardTitle className="text-3xl text-primary">{kpi.value}</CardTitle>
              )}
            </CardHeader>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <CardTitle>Recent jobs</CardTitle>
            <CardDescription>Latest enrichment runs from the pipeline.</CardDescription>
          </div>
          <Button asChild variant="outline" size="sm" className="shrink-0 self-start sm:self-auto">
            <Link href="/app/history">View all</Link>
          </Button>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : data?.recent.length ? (
            <ul className="flex flex-col gap-2">
              {data.recent.map((job) => (
                <li key={job.id} className="flex min-w-0 flex-col gap-1 rounded-md border px-3 py-2 text-sm">
                  <div className="flex min-w-0 items-center gap-2">
                    <Link
                      href={`/app/jobs/${job.id}`}
                      className="min-w-0 flex-1 truncate font-mono text-primary hover:underline"
                    >
                      {job.id}
                    </Link>
                    <span className="shrink-0">
                      <JobStatusBadge status={job.status} />
                    </span>
                  </div>
                  {job.identifierSummary ? (
                    <span className="truncate text-muted-foreground">{job.identifierSummary}</span>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">No jobs yet. Start a new enrichment.</p>
          )}
        </CardContent>
      </Card>

      <div className="flex flex-wrap gap-2">
        <Button asChild>
          <Link href="/app/enrich">New enrichment</Link>
        </Button>
        <Button asChild variant="outline">
          <Link href="/app/health">System health</Link>
        </Button>
      </div>
    </div>
  );
}
