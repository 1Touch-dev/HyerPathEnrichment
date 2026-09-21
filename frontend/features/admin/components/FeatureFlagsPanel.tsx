"use client";

import { Info } from "lucide-react";
import { EmptyState } from "@/components/console/EmptyState";
import { DeskMetricCard, DeskMetricGrid } from "@/components/desk/desk-shell";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  SectionHeader,
  SectionHeaderActions,
  SectionHeaderContent,
  SectionHeaderDescription,
  SectionHeaderTitle,
} from "@/components/ui/section-header";
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
  const enabledFlags = (flags ?? []).filter((flag) => flag.enabled).length;
  const disabledFlags = (flags ?? []).length - enabledFlags;

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

      <DeskMetricGrid className="xl:grid-cols-3">
        <DeskMetricCard
          label="Stored records"
          value={(flags ?? []).length}
          hint="Visible administration-only records"
        />
        <DeskMetricCard
          label="Enabled records"
          value={enabledFlags}
          hint="Set in storage, not yet consumed by an app service"
          tone={enabledFlags > 0 ? "info" : "default"}
        />
        <DeskMetricCard
          label="Disabled records"
          value={disabledFlags}
          hint="Mutation remains unavailable"
          tone={disabledFlags > 0 ? "warning" : "default"}
        />
      </DeskMetricGrid>

      <SectionHeader>
        <SectionHeaderContent>
          <SectionHeaderTitle>Stored flag records</SectionHeaderTitle>
          <SectionHeaderDescription>
            Read-only operational visibility into persisted feature flag values and ownership.
          </SectionHeaderDescription>
        </SectionHeaderContent>
        <SectionHeaderActions>
          <Button disabled aria-describedby="feature-flags-status-description">
            Create flag
          </Button>
        </SectionHeaderActions>
      </SectionHeader>

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
            <div
              key={flag.key}
              className="flex flex-col gap-3 rounded-lg border border-border/70 bg-surface p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0 space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-sm font-medium">{flag.key}</span>
                  <Badge variant={flag.enabled ? "success" : "outline"}>
                    {flag.enabled ? "Stored as enabled" : "Stored as disabled"}
                  </Badge>
                  {flag.updatedBy ? (
                    <Badge variant="outline" className="text-[10px]">
                      updated by {flag.updatedBy}
                    </Badge>
                  ) : null}
                </div>
                {flag.description ? (
                  <p className="text-sm text-muted-foreground">{flag.description}</p>
                ) : null}
                <p className="text-xs text-muted-foreground">
                  Last updated {flag.updatedAt.replace("T", " ").slice(0, 19)}
                </p>
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
