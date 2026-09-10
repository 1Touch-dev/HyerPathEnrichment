"use client";

import { useMemo } from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { DossierScanList } from "@/components/console/DossierScanList";
import { EmptyState } from "@/components/console/EmptyState";
import { ConfidenceDashboard } from "@/components/dossier/ConfidenceDashboard";
import { SourceBadges } from "@/components/dossier/SourceBadges";
import { BusinessProfileCard } from "@/components/dossier/BusinessProfileCard";
import type { Dossier } from "@/src/lib/types";
import type { DossierEntity } from "./dossier-entity";

type DossierTabViewProps = {
  dossier: Dossier;
  selectedId?: string | null;
  onSelect: (entity: DossierEntity) => void;
  loading: boolean;
};

export function DossierTabView({ dossier, selectedId, onSelect, loading }: DossierTabViewProps) {
  const counts = useMemo(
    () => ({
      handles: dossier.handles.length,
      emails: dossier.emails.length + dossier.verifiedEmails.length,
      jobs: dossier.jobs.length,
      business: dossier.business ? 1 : 0,
      confidence: dossier.confidence.length,
      sources: dossier.sources.length,
    }),
    [dossier],
  );

  const hasFindings = useMemo(
    () =>
      counts.handles > 0 ||
      counts.emails > 0 ||
      counts.jobs > 0 ||
      counts.business > 0 ||
      counts.confidence > 0 ||
      counts.sources > 0,
    [counts],
  );

  const hasConnections = useMemo(
    () => counts.handles > 0 || counts.jobs > 0 || dossier.coworkers.length > 0,
    [counts, dossier.coworkers.length],
  );

  return (
    <Tabs defaultValue="overview" className="w-full">
      <TabsList className="w-full justify-start overflow-x-auto">
        <TabsTrigger value="overview">Overview</TabsTrigger>
        <TabsTrigger value="handles" disabled={counts.handles === 0}>
          Handles {counts.handles > 0 && `(${counts.handles})`}
        </TabsTrigger>
        <TabsTrigger value="emails" disabled={counts.emails === 0}>
          Emails {counts.emails > 0 && `(${counts.emails})`}
        </TabsTrigger>
        <TabsTrigger value="professional" disabled={counts.jobs === 0}>
          Professional {counts.jobs > 0 && `(${counts.jobs})`}
        </TabsTrigger>
        <TabsTrigger value="business" disabled={counts.business === 0}>
          Business
        </TabsTrigger>
        <TabsTrigger value="confidence" disabled={counts.confidence === 0}>
          Confidence {counts.confidence > 0 && `(${counts.confidence})`}
        </TabsTrigger>
        <TabsTrigger value="sources" disabled={counts.sources === 0}>
          Sources {counts.sources > 0 && `(${counts.sources})`}
        </TabsTrigger>
        {/* Network tab temporarily hidden */}
        {/* <TabsTrigger value="network" disabled={!hasConnections}>
          Network
        </TabsTrigger> */}
      </TabsList>

      <TabsContent value="overview" className="mt-4">
        <div className="flex flex-col gap-4">
          {hasFindings ? (
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(280px,1fr)]">
              <div className="rounded-xl border border-border/70 bg-surface p-4">
                <div className="mb-4 flex items-center justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-semibold text-foreground">Evidence snapshot</h3>
                    <p className="text-sm text-muted-foreground">
                      Start with the strongest signals, then drill into each tab for details.
                    </p>
                  </div>
                  {loading ? (
                    <Badge variant="warning">Updating</Badge>
                  ) : (
                    <Badge variant="success">Ready</Badge>
                  )}
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <OverviewMetric label="Handles" value={counts.handles} />
                  <OverviewMetric label="Emails" value={counts.emails} />
                  <OverviewMetric label="Professional" value={counts.jobs} />
                  <OverviewMetric label="Business" value={counts.business} />
                  <OverviewMetric label="Confidence rules" value={counts.confidence} />
                  <OverviewMetric label="Sources" value={counts.sources} />
                </div>
              </div>

              <div className="rounded-xl border border-border/70 bg-surface p-4">
                <h3 className="text-sm font-semibold text-foreground">Next best actions</h3>
                <div className="mt-3 flex flex-col gap-3 text-sm text-muted-foreground">
                  <p>Open tabbed sections to review findings grouped by category.</p>
                  <p>Select any row to inspect the supporting detail panel and raw payload.</p>
                  {hasConnections ? (
                    <p>
                      The dossier already has enough connected evidence to review relationships.
                    </p>
                  ) : (
                    <p>
                      Connection mapping is limited until handles, jobs, or coworkers are found.
                    </p>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <EmptyState
              title="No findings yet"
              description={loading ? "Building dossier..." : "No enrichment data available."}
            />
          )}
        </div>
      </TabsContent>

      <TabsContent value="handles" className="mt-4">
        {counts.handles > 0 ? (
          <DossierScanList
            dossier={dossier}
            categories={["handles"]}
            selectedId={selectedId}
            onSelect={onSelect}
          />
        ) : (
          <EmptyState
            title="No social handles"
            description="No social media profiles found in this enrichment."
          />
        )}
      </TabsContent>

      <TabsContent value="emails" className="mt-4">
        {counts.emails > 0 ? (
          <DossierScanList
            dossier={dossier}
            categories={["verifiedEmails", "emails"]}
            selectedId={selectedId}
            onSelect={onSelect}
          />
        ) : (
          <EmptyState
            title="No email addresses"
            description="No email addresses found in this enrichment."
          />
        )}
      </TabsContent>

      <TabsContent value="professional" className="mt-4">
        {counts.jobs > 0 ? (
          <DossierScanList
            dossier={dossier}
            categories={["jobs"]}
            selectedId={selectedId}
            onSelect={onSelect}
          />
        ) : (
          <EmptyState
            title="No professional information"
            description="No job listings or business information found."
          />
        )}
      </TabsContent>

      <TabsContent value="business" className="mt-4">
        {dossier.business ? (
          <BusinessProfileCard business={dossier.business} />
        ) : (
          <EmptyState
            title="No business information"
            description="No business profile found in this enrichment."
          />
        )}
      </TabsContent>

      <TabsContent value="confidence" className="mt-4">
        {counts.confidence > 0 ? (
          <ConfidenceDashboard confidence={dossier.confidence} />
        ) : (
          <EmptyState
            title="No confidence data"
            description="No confidence scoring available for this enrichment."
          />
        )}
      </TabsContent>

      <TabsContent value="sources" className="mt-4">
        {counts.sources > 0 ? (
          <SourceBadges sources={dossier.sources} className="p-4 rounded-lg border bg-card" />
        ) : (
          <EmptyState title="No sources" description="No enrichment sources recorded." />
        )}
      </TabsContent>

      {/* Network tab content temporarily hidden */}
      {/* <TabsContent value="network" className="mt-4">
        {hasConnections ? (
          <div className="rounded-lg border bg-card p-4">
            <h3 className="text-sm font-semibold mb-4">Connection Network</h3>
            <p className="text-xs text-muted-foreground mb-4">
              Interactive graph showing relationships between the subject, social handles,
              companies, and coworkers.
            </p>
            <NetworkGraph dossier={dossier} />
          </div>
        ) : (
          <EmptyState
            title="No connections"
            description="No handles, jobs, or coworkers to visualize."
          />
        )}
      </TabsContent> */}
    </Tabs>
  );
}

function OverviewMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-border/70 bg-background p-3">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-subtle-foreground">
        {label}
      </p>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-foreground">{value}</p>
    </div>
  );
}
