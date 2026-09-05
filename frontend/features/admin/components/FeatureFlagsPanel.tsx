"use client";

import { Info } from "lucide-react";
import { EmptyState } from "@/components/console/EmptyState";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { useFeatureFlags } from "../hooks/useFeatureFlags";

function AsyncState({
  role,
  title,
  description,
}: {
  role: "status" | "alert";
  title: string;
  description: string;
}) {
  return (
    <div role={role} aria-label={title} aria-description={description}>
      <EmptyState title={title} description={description} />
    </div>
  );
}

export function FeatureFlagsPanel() {
  const { data: flags, isLoading, isError } = useFeatureFlags();

  return (
    <div className="flex flex-col gap-4">
      <Alert role="status" aria-labelledby="feature-flags-status-title">
        <Info aria-hidden="true" className="h-4 w-4" />
        <AlertTitle id="feature-flags-status-title">Administration status only</AlertTitle>
        <AlertDescription id="feature-flags-status-description">
          Stored values are shown for administrative visibility only. No application service
          consumes these records, so mutation is disabled until a consumer exists.
        </AlertDescription>
      </Alert>

      <div className="flex items-center justify-between gap-4">
        <p className="text-sm text-muted-foreground">Read-only stored flag records</p>
        <Button disabled aria-describedby="feature-flags-status-description">
          Create flag
        </Button>
      </div>

      {isLoading && !flags ? (
        <p role="status" className="text-sm text-muted-foreground">
          Loading feature flag records…
        </p>
      ) : isError ? (
        <AsyncState
          role="alert"
          title="Feature flag records unavailable"
          description="The stored administration records could not be loaded."
        />
      ) : !flags?.length ? (
        <AsyncState
          role="status"
          title="No stored feature flag records"
          description="Creation remains unavailable while feature flags have no application consumer."
        />
      ) : (
        <div className="flex flex-col gap-2">
          {(flags ?? []).map((flag) => (
            <div key={flag.key} className="flex items-center justify-between rounded-lg border p-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm font-medium">{flag.key}</span>
                  {flag.updatedBy ? (
                    <Badge variant="outline" className="text-[10px]">
                      updated by {flag.updatedBy}
                    </Badge>
                  ) : null}
                </div>
                {flag.description ? (
                  <p className="text-sm text-muted-foreground">{flag.description}</p>
                ) : null}
              </div>
              <Switch
                checked={flag.enabled}
                disabled
                aria-label={`Toggle ${flag.key}`}
                aria-describedby="feature-flags-status-description"
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
