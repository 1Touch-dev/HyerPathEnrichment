"use client";

import { Activity, RefreshCw, ShieldCheck } from "lucide-react";
import { HealthIndicator } from "@/components/console/HealthIndicator";
import {
  ShellPageHeader,
  ShellPageHeaderActions,
  ShellPageHeaderContent,
  ShellPageHeaderDescription,
  ShellPageHeaderEyebrow,
  ShellPageHeaderTitle,
} from "@/components/layout/ShellPage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useHealthQuery } from "../hooks/useHealthQuery";
import { formatApiErrorMessage } from "@/src/lib/format-api-error";
import { cn } from "@/src/lib/utils";

export function HealthView() {
  const { data, isLoading, error, refetch, isFetching } = useHealthQuery();
  const online = data?.status === "ok" || data?.status === "ready";

  return (
    <div className="flex flex-col gap-6">
      <ShellPageHeader>
        <ShellPageHeaderContent>
          <ShellPageHeaderEyebrow>Candidate workspace</ShellPageHeaderEyebrow>
          <ShellPageHeaderTitle>System health</ShellPageHeaderTitle>
          <ShellPageHeaderDescription>
            Shared connectivity snapshot for the BFF and backend service used by Candidate and OSINT
            workflows.
          </ShellPageHeaderDescription>
        </ShellPageHeaderContent>
        <ShellPageHeaderActions className="items-start sm:items-center">
          <HealthIndicator />
          <Button variant="outline" size="sm" onClick={() => void refetch()} disabled={isFetching}>
            <RefreshCw className={cn("mr-2 h-4 w-4", isFetching && "animate-spin")} />
            Refresh
          </Button>
        </ShellPageHeaderActions>
      </ShellPageHeader>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <Card variant="accent">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Activity className="h-4 w-4 text-primary" />
              API status
            </CardTitle>
            <CardDescription>Health endpoint via Next.js BFF</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-8 w-32" />
            ) : error ? (
              <p className="text-sm text-destructive">{formatApiErrorMessage(error)}</p>
            ) : (
              <div className="flex items-center gap-3">
                <span
                  className={cn("h-3 w-3 rounded-full", online ? "bg-success" : "bg-destructive")}
                />
                <span className="font-mono text-sm text-primary">{data?.status ?? "unknown"}</span>
              </div>
            )}
          </CardContent>
        </Card>

        <Card variant="accent">
          <CardHeader>
            <CardTitle className="text-base">Service identifier</CardTitle>
            <CardDescription>Reported by the backend health check</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-6 w-48" />
            ) : (
              <p className="font-mono text-sm text-muted-foreground">{data?.service ?? "—"}</p>
            )}
          </CardContent>
        </Card>

        <Card variant="accent" className="sm:col-span-2 xl:col-span-1">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <ShieldCheck className="h-4 w-4 text-primary" />
              Monitoring cadence
            </CardTitle>
            <CardDescription>Polling behavior stays unchanged</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Badge variant={isFetching ? "warning" : "outline"}>
              {isFetching ? "Refreshing now" : "Refreshes every 30s"}
            </Badge>
            <p className="text-sm text-muted-foreground">
              Manual refresh is still available for an immediate connectivity check.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
