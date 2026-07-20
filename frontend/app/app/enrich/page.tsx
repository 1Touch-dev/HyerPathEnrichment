'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useMemo } from 'react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { EnrichModeToggle } from '@/components/console/EnrichModeToggle';
import { IntakeForm } from '@/components/console/IntakeForm';
import { EmptyState } from '@/components/console/EmptyState';
import { useCreateEnrichment } from '@/features/enrich';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { patchDraft, setEnrichMode } from '@/store/slices/intakeSlice';
import { parseTiersFromQuery } from '@/src/lib/tier-utils';
import { EnrichmentInput } from '@/src/lib/types';

function EnrichPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const dispatch = useAppDispatch();
  const draft = useAppSelector((state) => state.intake.draft);
  const mode = useAppSelector((state) => state.intake.enrichMode);
  const initialTiers = useMemo(() => parseTiersFromQuery(searchParams.get('tiers')), [searchParams]);
  const jobIdParam = searchParams.get('jobId');
  const createMutation = useCreateEnrichment();

  useEffect(() => {
    if (jobIdParam) {
      router.replace(`/app/jobs/${jobIdParam}`);
    }
  }, [jobIdParam, router]);

  useEffect(() => {
    if (initialTiers.length) {
      dispatch(patchDraft({ requestedTiers: initialTiers }));
    }
  }, [dispatch, initialTiers]);

  const handleSubmit = async (input: EnrichmentInput) => {
    dispatch(patchDraft(input));
    const created = await createMutation.mutateAsync({ input, mode });
    router.push(`/app/jobs/${created.id}`);
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Look someone up</h1>
        <p className="text-sm text-muted-foreground">
          Paste one identifier (email, LinkedIn URL, or username). Results are opened in a shareable job page with live polling.
        </p>
      </div>

      <EnrichModeToggle mode={mode} onChange={(next) => dispatch(setEnrichMode(next))} />
      <IntakeForm
        mode={mode}
        initialTiers={draft.requestedTiers}
        onSubmit={handleSubmit}
        loading={createMutation.isPending}
      />

      {createMutation.error ? (
        <Alert variant="destructive">
          <AlertDescription>{createMutation.error.message}</AlertDescription>
        </Alert>
      ) : null}

      <EmptyState
        title="Ready to look up"
        description="After submit you will be redirected to the profile results page."
      />
    </div>
  );
}

export default function EnrichPage() {
  return (
    <Suspense fallback={null}>
      <EnrichPageContent />
    </Suspense>
  );
}
