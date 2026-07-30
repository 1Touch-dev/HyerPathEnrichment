"use client";

import { useMemo } from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { DossierSummary } from "@/components/console/DossierSummary";
import { DossierScanList } from "@/components/console/DossierScanList";
import { EmptyState } from "@/components/console/EmptyState";
import { ConfidenceDashboard } from "@/components/dossier/ConfidenceDashboard";
import { SourceBadges } from "@/components/dossier/SourceBadges";
import { NetworkGraph } from "@/components/dossier/NetworkGraph";
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
        <TabsTrigger value="confidence" disabled={counts.confidence === 0}>
          Confidence {counts.confidence > 0 && `(${counts.confidence})`}
        </TabsTrigger>
        <TabsTrigger value="sources" disabled={counts.sources === 0}>
          Sources {counts.sources > 0 && `(${counts.sources})`}
        </TabsTrigger>
        <TabsTrigger value="network" disabled={!hasConnections}>
          Network
        </TabsTrigger>
      </TabsList>

      <TabsContent value="overview" className="mt-4">
        <div className="flex flex-col gap-4">
          <DossierSummary dossier={dossier} loading={loading} />
          {hasFindings ? (
            <div className="rounded-lg border bg-card p-4">
              <h3 className="mb-3 text-sm font-semibold">Quick Summary</h3>
              <div className="grid gap-2 text-sm">
                {counts.handles > 0 && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Social Handles:</span>
                    <span className="font-medium">{counts.handles}</span>
                  </div>
                )}
                {counts.emails > 0 && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Email Addresses:</span>
                    <span className="font-medium">{counts.emails}</span>
                  </div>
                )}
                {counts.jobs > 0 && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Job Listings:</span>
                    <span className="font-medium">{counts.jobs}</span>
                  </div>
                )}
                {counts.confidence > 0 && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Confidence Rules:</span>
                    <span className="font-medium">{counts.confidence}</span>
                  </div>
                )}
                {counts.sources > 0 && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Data Sources:</span>
                    <span className="font-medium">{counts.sources}</span>
                  </div>
                )}
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

      <TabsContent value="network" className="mt-4">
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
      </TabsContent>
    </Tabs>
  );
}
