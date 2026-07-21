"use client";

import { useEffect, useMemo, useState } from "react";
import { Dossier } from "@/src/lib/types";
import { DossierSummary } from "@/components/console/DossierSummary";
import { RawJsonPanel } from "@/components/console/RawJsonPanel";
import { EmptyState } from "@/components/console/EmptyState";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { DossierScanList } from "./DossierScanList";
import { EntityDetailPanel } from "./EntityDetailPanel";
import type { DossierEntity } from "./dossier-entity";
import { formatPercent, initialsFrom } from "@/src/lib/utils";
import { EnrichmentJob } from "@/src/lib/types";

type DossierViewProps = {
  job: EnrichmentJob;
};

function SectionSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-20 w-full" />
    </div>
  );
}

function EmptyMessage({ message }: { message: string }) {
  return <p className="text-sm text-muted-foreground">{message}</p>;
}

export function DossierView({ job }: DossierViewProps) {
  const { dossier, status } = job;
  const loading = status === "running" || status === "queued";
  const suppressed = status === "suppressed";

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
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const mql = window.matchMedia("(max-width: 767px)");

    const apply = () => setIsMobile(mql.matches);
    apply();

    const onChange = () => apply();

    if (typeof mql.addEventListener === "function") {
      mql.addEventListener("change", onChange);
      return () => mql.removeEventListener("change", onChange);
    }

    // Safari fallback for older MediaQueryList implementations.
    const legacy = mql as unknown as {
      addListener: (cb: () => void) => void;
      removeListener: (cb: () => void) => void;
    };

    legacy.addListener(onChange);
    return () => legacy.removeListener(onChange);
  }, []);

  useEffect(() => {
    setSelectedEntity(null);
    setSheetOpen(false);
  }, [job.id]);

  const hasFindings = useMemo(
    () =>
      dossier.handles.length ||
      dossier.emails.length ||
      dossier.verifiedEmails.length ||
      dossier.jobs.length ||
      dossier.confidence.length ||
      dossier.sources.length,
    [dossier],
  );

  const selectedId = selectedEntity?.id ?? null;

  const handleSelect = (entity: DossierEntity) => {
    setSelectedEntity(entity);
    if (isMobile) {
      setSheetOpen(true);
    }
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
      <Card>
        <CardHeader>
          <p className="text-xs uppercase tracking-widest text-muted-foreground">Merged dossier</p>
          <DossierSummary dossier={dossier} loading={loading} />
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_420px]">
            <div className="min-w-0">
              {loading && !hasFindings ? <SectionSkeleton /> : null}
              {hasFindings ? (
                <DossierScanList
                  dossier={dossier}
                  selectedId={selectedId}
                  onSelect={handleSelect}
                />
              ) : (
                <EmptyMessage message={loading ? "Building findings…" : "No findings returned."} />
              )}
            </div>

            <div className="hidden lg:block">
              {selectedEntity ? (
                <EntityDetailPanel dossier={dossier} entity={selectedEntity} />
              ) : (
                <EmptyMessage message="Select a finding to view details." />
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
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Business</CardTitle>
        </CardHeader>
        <CardContent className="text-sm">
          {dossier.business ? (
            <ul className="flex flex-col gap-1">
              <li>{dossier.business.name}</li>
              <li>{dossier.business.address}</li>
              <li>
                <a
                  href={dossier.business.website}
                  target="_blank"
                  rel="noreferrer"
                  className="text-primary"
                >
                  {dossier.business.website}
                </a>
              </li>
              <li>{dossier.business.phone}</li>
              <li>Rating: {dossier.business.rating}</li>
            </ul>
          ) : (
            <EmptyMessage message="No business profile returned." />
          )}
        </CardContent>
      </Card>
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
