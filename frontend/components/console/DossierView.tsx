"use client";

import { useEffect, useState } from "react";
import { Dossier } from "@/src/lib/types";
import { DossierSummary } from "@/components/console/DossierSummary";
import { RawJsonPanel } from "@/components/console/RawJsonPanel";
import { EmptyState } from "@/components/console/EmptyState";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import {
  SectionHeader,
  SectionHeaderActions,
  SectionHeaderContent,
  SectionHeaderDescription,
  SectionHeaderTitle,
} from "@/components/ui/section-header";
import { DossierTabView } from "./DossierTabView";
import { EntityDetailPanel } from "./EntityDetailPanel";
import type { DossierEntity } from "./dossier-entity";
import { formatPercent, initialsFrom } from "@/src/lib/utils";
import { EnrichmentJob } from "@/src/lib/types";
import { useJobEvents } from "@/hooks/useJobEvents";
import { Clock, Loader2, CheckCircle } from "lucide-react";
import { BusinessProfileCard } from "@/components/dossier/BusinessProfileCard";

type DossierViewProps = {
  job: EnrichmentJob;
};

function EmptyMessage({ message }: { message: string }) {
  return <p className="text-sm text-muted-foreground">{message}</p>;
}

export function DossierView({ job }: DossierViewProps) {
  const { dossier, status } = job;
  const loading = status === "running" || status === "queued";
  const suppressed = status === "suppressed";
  const evidenceCount =
    dossier.handles.length +
    dossier.emails.length +
    dossier.verifiedEmails.length +
    dossier.jobs.length +
    dossier.confidence.length;

  // Legacy helpers below are kept temporarily during the refactor.
  // Referencing them prevents TS noUnusedLocals errors while the codebase migrates.
  void IdentitySection;
  void HandlesSection;
  void EmailsSection;
  void GithubSection;
  void JobsBusinessSection;
  void ConfidenceSection;
  void SourcesSection;

  const [selectedEntity, setSelectedEntity] = useState<DossierEntity | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);

  // SSE for real-time updates
  useJobEvents({
    jobId: job.id,
    enabled: loading,
    onStatusChange: (newStatus) => {
      console.log("Job status changed:", newStatus);
    },
  });

  useEffect(() => {
    setSelectedEntity(null);
    setSheetOpen(false);
  }, [job.id]);

  const selectedId = selectedEntity?.id ?? null;

  const handleSelect = (entity: DossierEntity) => {
    setSelectedEntity(entity);
    setSheetOpen(true);
  };

  if (suppressed) {
    return (
      <div className="flex flex-col gap-4">
        <EmptyState
          title="Identifier suppressed"
          description="This identifier opted out of enrichment. The dossier is intentionally empty."
        />
        <RawJsonPanel job={job} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Status Alert */}
      {status === "queued" && (
        <Alert>
          <Clock className="h-4 w-4" />
          <AlertTitle>Job Queued</AlertTitle>
          <AlertDescription>Your enrichment is queued and will start shortly...</AlertDescription>
        </Alert>
      )}

      {status === "running" && (
        <Alert>
          <Loader2 className="h-4 w-4 animate-spin" />
          <AlertTitle>Enriching...</AlertTitle>
          <AlertDescription>
            Scanning {dossier.sources.length || "multiple"} sources. This may take 1-2 minutes.
          </AlertDescription>
        </Alert>
      )}

      {status === "completed" && (
        <Alert variant="success">
          <CheckCircle className="h-4 w-4" />
          <AlertTitle>Complete</AlertTitle>
          <AlertDescription>
            Enrichment completed at {new Date(job.updatedAt).toLocaleTimeString()}
          </AlertDescription>
        </Alert>
      )}

      <Card className="overflow-hidden border-border/70 bg-card shadow-sm">
        <CardHeader className="gap-5 border-b border-border/60 bg-primary-soft/40">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">{job.input.requestedTiers.length} requested tiers</Badge>
            <Badge variant="info">{evidenceCount} evidence points</Badge>
            <Badge variant="secondary">{dossier.sources.length} sources</Badge>
          </div>
          <DossierSummary dossier={dossier} loading={loading} />
        </CardHeader>
        <CardContent className="space-y-5 pt-6">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <SummaryMetric label="Handles" value={dossier.handles.length} />
            <SummaryMetric
              label="Emails"
              value={dossier.emails.length + dossier.verifiedEmails.length}
            />
            <SummaryMetric label="Professional leads" value={dossier.jobs.length} />
            <SummaryMetric label="Confidence rules" value={dossier.confidence.length} />
          </div>

          <SectionHeader>
            <SectionHeaderContent>
              <SectionHeaderTitle>Evidence review</SectionHeaderTitle>
              <SectionHeaderDescription>
                Work through the tabs on the left, then inspect the selected item in the detail
                panel.
              </SectionHeaderDescription>
            </SectionHeaderContent>
            <SectionHeaderActions>
              {selectedEntity ? (
                <Badge variant="success">Detail selected</Badge>
              ) : (
                <Badge variant="outline">Pick a finding</Badge>
              )}
            </SectionHeaderActions>
          </SectionHeader>

          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_420px]">
            <div className="min-w-0">
              <DossierTabView
                dossier={dossier}
                selectedId={selectedId}
                onSelect={handleSelect}
                loading={loading}
              />
            </div>

            <div className="hidden lg:block">
              {selectedEntity ? (
                <EntityDetailPanel dossier={dossier} entity={selectedEntity} />
              ) : (
                <div className="rounded-xl border border-dashed border-border/70 bg-card p-6 text-sm text-muted-foreground">
                  Select a finding to view its details, supporting evidence, and raw payload.
                </div>
              )}
            </div>
          </div>

          <div className="mt-4 lg:hidden">
            <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
              <SheetContent side="right">
                {selectedEntity ? (
                  <EntityDetailPanel dossier={dossier} entity={selectedEntity} />
                ) : (
                  <EmptyState
                    title="Select a finding"
                    description="Pick a row from the scan list to view details."
                  />
                )}
              </SheetContent>
            </Sheet>
          </div>
        </CardContent>
      </Card>
      <RawJsonPanel job={job} />
    </div>
  );
}

function SummaryMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-border/70 bg-card p-4 shadow-sm">
      <p className="text-[0.7rem] font-semibold uppercase tracking-[0.16em] text-primary">
        {label}
      </p>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-foreground">{value}</p>
    </div>
  );
}

function IdentitySection({ dossier }: { dossier: Dossier }) {
  const title = dossier.metadata.identifierSummary || "Subject";
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Photo</CardTitle>
        </CardHeader>
        <CardContent>
          {dossier.photo ? (
            <div className="flex flex-col gap-2 text-sm">
              <div className="flex size-16 items-center justify-center rounded-full bg-muted text-lg font-semibold">
                {initialsFrom(title)}
              </div>
              <a
                href={dossier.photo.assetUrl}
                target="_blank"
                rel="noreferrer"
                className="text-primary break-all"
              >
                {dossier.photo.assetUrl}
              </a>
              <p className="text-muted-foreground">
                {dossier.photo.source} · {formatPercent(dossier.photo.confidence)}
              </p>
            </div>
          ) : (
            <EmptyMessage message="No LinkedIn photo returned." />
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Emails</CardTitle>
        </CardHeader>
        <CardContent>
          {dossier.emails.length ? (
            <ul className="flex flex-col gap-2 text-sm">
              {dossier.emails.map((email) => (
                <li key={email}>{email}</li>
              ))}
            </ul>
          ) : (
            <EmptyMessage message="No email addresses returned." />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function HandlesSection({ dossier }: { dossier: Dossier }) {
  if (!dossier.handles.length) {
    return <EmptyMessage message="No social handles returned." />;
  }
  return (
    <ul className="flex flex-col gap-2">
      {dossier.handles.map((handle) => (
        <li key={`${handle.platform}-${handle.username}`} className="rounded-lg border p-3 text-sm">
          <div className="font-medium">
            {handle.platform} · {handle.username}
          </div>
          <a
            href={handle.profileUrl}
            target="_blank"
            rel="noreferrer"
            className="text-primary break-all"
          >
            {handle.profileUrl}
          </a>
          <div className="text-muted-foreground">{formatPercent(handle.confidence)}</div>
        </li>
      ))}
    </ul>
  );
}

function EmailsSection({ dossier }: { dossier: Dossier }) {
  if (!dossier.verifiedEmails.length) {
    return <EmptyMessage message="No verified email intelligence returned." />;
  }
  return (
    <ul className="flex flex-col gap-2">
      {dossier.verifiedEmails.map((email) => (
        <li key={email.value} className="rounded-lg border p-3 text-sm">
          <div className="font-medium">{email.value}</div>
          <div className="text-muted-foreground">
            {email.status} · {email.source} · {formatPercent(email.confidence)}
          </div>
        </li>
      ))}
    </ul>
  );
}

function GithubSection({ dossier }: { dossier: Dossier }) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">GitHub</CardTitle>
        </CardHeader>
        <CardContent className="text-sm">
          {dossier.github?.profile ? (
            <a
              href={dossier.github.profile}
              target="_blank"
              rel="noreferrer"
              className="text-primary"
            >
              {dossier.github.profile}
            </a>
          ) : (
            <EmptyMessage message="No GitHub profile." />
          )}
          <p className="mt-2 text-muted-foreground">
            Public commits: {dossier.github?.publicCommits ?? 0}
          </p>
          {dossier.github?.organizations.length ? (
            <ul className="mt-2 flex flex-col gap-1">
              {dossier.github.organizations.map((org) => (
                <li key={org}>{org}</li>
              ))}
            </ul>
          ) : null}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Coworkers</CardTitle>
        </CardHeader>
        <CardContent>
          {dossier.coworkers.length ? (
            <ul className="flex flex-col gap-1 text-sm">
              {dossier.coworkers.map((coworker) => (
                <li key={coworker}>{coworker}</li>
              ))}
            </ul>
          ) : (
            <EmptyMessage message="No coworkers returned." />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function JobsBusinessSection({ dossier }: { dossier: Dossier }) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Jobs</CardTitle>
        </CardHeader>
        <CardContent>
          {dossier.jobs.length ? (
            <ul className="flex flex-col gap-2 text-sm">
              {dossier.jobs.map((job) => (
                <li key={`${job.title}-${job.company}`} className="rounded border p-2">
                  <div className="font-medium">{job.title}</div>
                  <div className="text-muted-foreground">
                    {job.company} · {job.location} · {job.remote ? "Remote" : "On-site"} ·{" "}
                    {job.source}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyMessage message="No job listings returned." />
          )}
        </CardContent>
      </Card>
      {dossier.business ? (
        <BusinessProfileCard business={dossier.business} />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Business</CardTitle>
          </CardHeader>
          <CardContent>
            <EmptyMessage message="No business profile returned." />
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function ConfidenceSection({ dossier }: { dossier: Dossier }) {
  if (!dossier.confidence.length) {
    return <EmptyMessage message="No confidence scoring returned." />;
  }
  return (
    <div className="flex flex-col gap-2">
      {dossier.confidence.map((item) => (
        <div
          key={item.label}
          className="flex items-start justify-between rounded-lg border p-3 text-sm"
        >
          <div>
            <div className="font-medium">{item.label}</div>
            <p className="text-muted-foreground">{item.evidence.join(" · ")}</p>
          </div>
          <span>{formatPercent(item.score)}</span>
        </div>
      ))}
    </div>
  );
}

function SourcesSection({ dossier }: { dossier: Dossier }) {
  if (!dossier.sources.length) {
    return <EmptyMessage message="No enrichment sources recorded." />;
  }
  return (
    <ul className="flex flex-col gap-1 text-sm">
      {dossier.sources.map((source) => (
        <li key={source} className="rounded border px-3 py-2">
          {source}
        </li>
      ))}
    </ul>
  );
}
