'use client';

import { Activity, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useHealthQuery } from '../hooks/useHealthQuery';
import { cn } from '@/src/lib/utils';

export function HealthView() {
  const { data, isLoading, error, refetch, isFetching } = useHealthQuery();
  const online = data?.status === 'ok' || data?.status === 'ready';

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">System health</h1>
          <p className="text-sm text-muted-foreground">BFF and backend connectivity status.</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void refetch()} disabled={isFetching}>
          <RefreshCw className={cn('mr-2 h-4 w-4', isFetching && 'animate-spin')} />
          Refresh
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Activity className="h-4 w-4 text-brand-primary" />
              API status
            </CardTitle>
            <CardDescription>Health endpoint via Next.js BFF</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-8 w-32" />
            ) : error ? (
              <p className="text-sm text-destructive">{error.message}</p>
            ) : (
              <div className="flex items-center gap-3">
                <span className={cn('h-3 w-3 rounded-full', online ? 'bg-brand-secondary' : 'bg-destructive')} />
                <span className="font-mono text-sm">{data?.status ?? 'unknown'}</span>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Service</CardTitle>
            <CardDescription>Backend service identifier</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-6 w-48" />
            ) : (
              <p className="font-mono text-sm text-muted-foreground">{data?.service ?? '—'}</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
