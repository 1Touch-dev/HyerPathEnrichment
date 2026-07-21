"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo } from "react";
import { toast } from "sonner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { EnrichModeToggle } from "@/components/console/EnrichModeToggle";
import { IntakeForm } from "@/components/console/IntakeForm";
import { EmptyState } from "@/components/console/EmptyState";
import { useCreateEnrichment, useJobCompletionToasts } from "@/features/enrich";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { patchDraft, setEnrichMode } from "@/store/slices/intakeSlice";
import { parseTiersFromQuery } from "@/src/lib/tier-utils";
import { formatApiErrorMessage } from "@/src/lib/format-api-error";
import { EnrichmentInput } from "@/src/lib/types";

function EnrichPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const dispatch = useAppDispatch();
  const draft = useAppSelector((state) => state.intake.draft);
  const mode = useAppSelector((state) => state.intake.enrichMode);
  const initialTiers = useMemo(
    () => parseTiersFromQuery(searchParams.get("tiers")),
    [searchParams],
  );
  const createMutation = useCreateEnrichment();
  const trackJobCompletion = useJobCompletionToasts();

  useEffect(() => {
    if (initialTiers.length) {
      dispatch(patchDraft({ requestedTiers: initialTiers }));
    }
  }, [dispatch, initialTiers]);

  const handleSubmit = async (input: EnrichmentInput) => {
    dispatch(patchDraft(input));
    const created = await createMutation.mutateAsync({ input, mode });
    if (mode === "async") {
      toast.success("Job created", { description: created.id });
      trackJobCompletion(created.id);
      return;
    }
    router.push(`/app/jobs/${created.id}`);
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Look someone up</h1>
        <p className="text-sm text-muted-foreground">
          Select tiers and fill the fields they require. Async jobs stay here after submit — check
          History for results. Sync jobs open the dossier when finished.
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
          <AlertDescription>{formatApiErrorMessage(createMutation.error)}</AlertDescription>
        </Alert>
      ) : null}

      <EmptyState
        title="Ready to look up"
        description="Async: you will get a confirmation toast and can follow the job in History. Sync: results open on the job page."
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
