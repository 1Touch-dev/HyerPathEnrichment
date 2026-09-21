"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { AlertCircle, ArrowRight, Clock3, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { EmptyState } from "@/components/console/EmptyState";
import { EnrichModeToggle } from "@/components/console/EnrichModeToggle";
import { IntakeForm } from "@/components/console/IntakeForm";
import { JobHistoryPanel } from "@/components/console/JobHistoryPanel";
import { JobProgress } from "@/components/console/JobProgress";
import { JobQueuePanel } from "@/components/console/JobQueuePanel";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  PageHeader,
  PageHeaderActions,
  PageHeaderContent,
  PageHeaderDescription,
  PageHeaderEyebrow,
  PageHeaderTitle,
} from "@/components/ui/page-header";
import { useCreateEnrichment, useJobCompletionToasts, useJobQuery } from "@/features/enrich";
import { useLocalStorageJobs } from "@/hooks/useLocalStorageJobs";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { patchDraft, setEnrichMode } from "@/store/slices/intakeSlice";
import { isTerminalStatus } from "@/src/lib/enrich-poll";
import { formatApiErrorMessage } from "@/src/lib/format-api-error";
import { getTierLabel, parseTiersFromQuery } from "@/src/lib/tier-utils";
import type { EnrichmentInput } from "@/src/lib/types";

function OsintLookupPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const dispatch = useAppDispatch();
  const draft = useAppSelector((state) => state.intake.draft);
  const mode = useAppSelector((state) => state.intake.enrichMode);
  const initialTiers = useMemo(
    () => parseTiersFromQuery(searchParams.get("tiers")),
    [searchParams],
  );
  const queryString = useMemo(() => searchParams.toString(), [searchParams]);
  const createMutation = useCreateEnrichment();
  const trackJobCompletion = useJobCompletionToasts();
  const { jobs, activeJobs, addJob, updateJobStatus } = useLocalStorageJobs();

  const [activeAsyncJob, setActiveAsyncJob] = useState<string | null>(null);
  const { data: activeJob, isFetching: isPolling } = useJobQuery(activeAsyncJob ?? undefined);

  useEffect(() => {
    if (initialTiers.length) {
      dispatch(patchDraft({ requestedTiers: initialTiers }));
    }
  }, [dispatch, initialTiers]);

  useEffect(() => {
    if (activeJob && activeAsyncJob) {
      updateJobStatus(activeAsyncJob, activeJob.status);

      if (isTerminalStatus(activeJob.status)) {
        const timer = setTimeout(() => {
          setActiveAsyncJob(null);
        }, 3000);
        return () => clearTimeout(timer);
      }
    }
  }, [activeJob, activeAsyncJob, updateJobStatus]);

  useEffect(() => {
    if (createMutation.error) {
      toast.error("Request failed", {
        description: formatApiErrorMessage(createMutation.error),
        duration: 5000,
      });
    }
  }, [createMutation.error]);

  const handleSubmit = async (input: EnrichmentInput) => {
    dispatch(patchDraft(input));
    const created = await createMutation.mutateAsync({ input, mode });

    if (mode === "async") {
      toast.success("Job created", { description: created.id });
      trackJobCompletion(created.id);
      addJob(created.id, created.status);
      setActiveAsyncJob(created.id);
      return;
    }

    router.push(`/osint/jobs/${created.id}${queryString ? `?${queryString}` : ""}`);
  };

  const handleViewResults = () => {
    if (activeAsyncJob) {
      router.push(`/osint/jobs/${activeAsyncJob}${queryString ? `?${queryString}` : ""}`);
    }
  };

  const showProgress = mode === "async" && Boolean(activeJob) && Boolean(activeAsyncJob);
  const showViewResults = showProgress && activeJob ? isTerminalStatus(activeJob.status) : false;
  const jobsHref = queryString ? `/osint/jobs?${queryString}` : "/osint/jobs";
  const selectedTiers = draft.requestedTiers.length > 0 ? draft.requestedTiers : initialTiers;
  const reviewableJobs = useMemo(
    () => jobs.filter((job) => isTerminalStatus(job.status)).length,
    [jobs],
  );

  return (
    <div className="flex flex-col gap-8">
      <PageHeader>
        <PageHeaderContent>
          <PageHeaderEyebrow>OSINT workbench</PageHeaderEyebrow>
          <PageHeaderTitle>Investigate a public footprint</PageHeaderTitle>
          <PageHeaderDescription>
            Staff-only workspace for person and business research. Queue a deeper multi-tier run or
            stay in sync mode for quick verification when the browser pipeline is not needed.
          </PageHeaderDescription>
        </PageHeaderContent>
        <PageHeaderActions className="items-start sm:items-center">
          <Badge variant="info">Staff access</Badge>
          <Badge variant={mode === "async" ? "warning" : "secondary"}>
            {mode === "async" ? "Full async run" : "Quick sync run"}
          </Badge>
          <Button asChild variant="outline" className="w-fit shrink-0">
            <Link href={jobsHref}>Open jobs</Link>
          </Button>
          <Button asChild variant="ghost" className="w-fit shrink-0">
            <Link href="/osint/settings/security">Security</Link>
          </Button>
        </PageHeaderActions>
      </PageHeader>

      <div className="grid gap-4 md:grid-cols-3">
        <WorkbenchMetric
          label="Selected tiers"
          value={selectedTiers.length.toString()}
          description={
            selectedTiers.length > 0
              ? selectedTiers.map((tier) => getTierLabel(tier)).join(", ")
              : "No tier seed in the URL."
          }
        />
        <WorkbenchMetric
          label="Tracked jobs"
          value={jobs.length.toString()}
          description="Recent local queue entries follow this browser session."
        />
        <WorkbenchMetric
          label="Ready to review"
          value={reviewableJobs.toString()}
          description={`${activeJobs.length} active ${activeJobs.length === 1 ? "request" : "requests"} still polling.`}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.82fr)]">
        <div className="flex min-w-0 flex-col gap-6">
          <Card className="overflow-hidden">
            <CardHeader className="gap-4 border-b border-border/60 bg-surface-muted/40">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="space-y-2">
                  <p className="text-[0.7rem] font-semibold uppercase tracking-[0.16em] text-subtle-foreground">
                    Run strategy
                  </p>
                  <CardTitle className="text-xl">Choose speed or depth</CardTitle>
                  <CardDescription>
                    Async mode keeps the full tier ladder available. Sync mode returns faster but
                    skips Tier 1&apos;s browser-only pass.
                  </CardDescription>
                </div>
                <Badge variant="outline">
                  {mode === "async" ? "Best for full dossier runs" : "Best for quick validation"}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4 pt-6">
              <EnrichModeToggle mode={mode} onChange={(next) => dispatch(setEnrichMode(next))} />
              <Alert variant={mode === "async" ? "info" : "default"}>
                <Clock3 className="h-4 w-4" />
                <AlertDescription>
                  {mode === "async"
                    ? "Queue the lookup when you want browser-backed evidence, progress tracking, and a stable review trail."
                    : "Use sync mode when the identifiers already look strong and you want the dossier inline as soon as the supported tiers finish."}
                </AlertDescription>
              </Alert>
            </CardContent>
          </Card>

          {createMutation.error ? (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{formatApiErrorMessage(createMutation.error)}</AlertDescription>
            </Alert>
          ) : null}

          {showProgress && activeJob ? (
            <Card className="overflow-hidden">
              <CardHeader className="gap-3 border-b border-border/60 bg-surface-muted/40">
                <CardTitle className="text-xl">Active lookup</CardTitle>
                <CardDescription>
                  Live progress remains visible here until the request reaches a terminal state.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 pt-6">
                <JobProgress job={activeJob} polling={isPolling} />
                {showViewResults ? (
                  <Button onClick={handleViewResults} className="w-full sm:w-fit" size="lg">
                    Open dossier
                    <ArrowRight className="ml-2 size-4" />
                  </Button>
                ) : null}
              </CardContent>
            </Card>
          ) : null}

          <IntakeForm
            mode={mode}
            initialTiers={draft.requestedTiers}
            onSubmit={handleSubmit}
            loading={createMutation.isPending}
          />

          {!showProgress ? (
            <EmptyState
              title="Ready to investigate"
              description="Build the request on the left, keep the queue on the right, and use recent dossiers below as your reusable research trail."
            />
          ) : null}
        </div>

        <div className="flex flex-col gap-6">
          <Card className="overflow-hidden">
            <CardHeader className="gap-4 border-b border-border/60 bg-surface-muted/40">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="space-y-2">
                  <p className="text-[0.7rem] font-semibold uppercase tracking-[0.16em] text-subtle-foreground">
                    Research briefing
                  </p>
                  <CardTitle className="text-xl">Keep the request targeted</CardTitle>
                  <CardDescription>
                    Strong identifiers shrink ambiguity. Add context only when it will improve the
                    public-web evidence you expect back.
                  </CardDescription>
                </div>
                <Badge variant="success">Local queue persists</Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-5 pt-6">
              <div className="space-y-3 rounded-xl border border-border/70 bg-surface p-4">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="size-4 text-info" />
                  <p className="text-sm font-medium text-foreground">Current tier seed</p>
                </div>
                {selectedTiers.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {selectedTiers.map((tier) => (
                      <Badge key={tier} variant="outline">
                        {getTierLabel(tier)}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    No `?tiers=` seed detected. The intake defaults remain editable before submit.
                  </p>
                )}
              </div>

              <div className="grid gap-3">
                <BriefingItem
                  title="Start with the strongest identifier"
                  description="LinkedIn URL, username, or email usually does more to anchor the dossier than extra free-form notes."
                />
                <BriefingItem
                  title="Use async for evidence gathering"
                  description="Queue the request whenever you want Tier 1 browser work, richer polling, or plan to revisit the dossier later."
                />
                <BriefingItem
                  title="Use sync for quick verification"
                  description="If you already have strong inputs and only need supported tiers, sync mode gets you to the dossier faster."
                />
              </div>
            </CardContent>
          </Card>

          <JobQueuePanel jobsBasePath="/osint/jobs" queryString={queryString} />
        </div>
      </div>

      <JobHistoryPanel jobsBasePath="/osint/jobs" queryString={queryString} />
    </div>
  );
}

function WorkbenchMetric({
  label,
  value,
  description,
}: {
  label: string;
  value: string;
  description: string;
}) {
  return (
    <Card>
      <CardContent className="space-y-2 p-5">
        <p className="text-[0.7rem] font-semibold uppercase tracking-[0.16em] text-subtle-foreground">
          {label}
        </p>
        <p className="text-3xl font-semibold tracking-tight text-foreground">{value}</p>
        <p className="text-sm text-muted-foreground">{description}</p>
      </CardContent>
    </Card>
  );
}

function BriefingItem({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-xl border border-border/70 bg-surface p-4">
      <p className="text-sm font-medium text-foreground">{title}</p>
      <p className="mt-1 text-sm text-muted-foreground">{description}</p>
    </div>
  );
}

export default function OsintLookupPage() {
  return (
    <Suspense fallback={null}>
      <OsintLookupPageContent />
    </Suspense>
  );
}
