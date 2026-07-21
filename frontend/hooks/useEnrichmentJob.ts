"use client";

import { useCallback, useEffect, useState } from "react";
import { createEnrichmentJob, getEnrichmentJob } from "@/src/lib/api-client";
import { isTerminalStatus, pollEnrichmentJob } from "@/src/lib/enrich-poll";
import { ApiError } from "@/src/lib/api-envelope";
import { formatApiErrorMessage } from "@/src/lib/format-api-error";
import { EnrichmentInput, EnrichmentJob, EnrichMode } from "@/src/lib/types";

type UseEnrichmentJobOptions = {
  initialJob?: EnrichmentJob | null;
  autoPoll?: boolean;
};

export function useEnrichmentJob(options: UseEnrichmentJobOptions = {}) {
  const [job, setJob] = useState<EnrichmentJob | null>(options.initialJob ?? null);
  const [loading, setLoading] = useState(false);
  const [polling, setPolling] = useState(false);
  const [pollTimedOut, setPollTimedOut] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadJob = useCallback(async (id: string) => {
    setError(null);
    setLoading(true);
    try {
      const loaded = await getEnrichmentJob(id);
      setJob(loaded.data);
      return loaded.data;
    } catch (loadError) {
      const message = formatApiErrorMessage(loadError);
      setError(message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const startPolling = useCallback(async (jobId: string) => {
    setPolling(true);
    setPollTimedOut(false);
    setError(null);

    const result = await pollEnrichmentJob(jobId, {
      onUpdate: (updated) => setJob(updated),
    });

    setPolling(false);

    if (result.status === "completed") {
      setJob(result.job);
    } else if (result.status === "timeout") {
      setJob(result.job);
      setPollTimedOut(true);
    } else {
      setError(
        result.error instanceof ApiError
          ? result.error.message
          : formatApiErrorMessage(result.error),
      );
    }
  }, []);

  const submit = useCallback(
    async (input: EnrichmentInput, mode: EnrichMode) => {
      setLoading(true);
      setError(null);
      setPollTimedOut(false);

      try {
        const created = await createEnrichmentJob(input, mode);
        setJob(created.data);

        if (mode === "async" && !isTerminalStatus(created.data.status)) {
          await startPolling(created.data.id);
        }

        return created.data;
      } catch (submitError) {
        setError(formatApiErrorMessage(submitError));
        return null;
      } finally {
        setLoading(false);
      }
    },
    [startPolling],
  );

  useEffect(() => {
    if (!options.autoPoll || !options.initialJob) {
      return;
    }

    if (!isTerminalStatus(options.initialJob.status)) {
      void startPolling(options.initialJob.id);
    }
  }, [options.autoPoll, options.initialJob, startPolling]);

  return {
    job,
    setJob,
    loading,
    polling,
    pollTimedOut,
    error,
    submit,
    loadJob,
    startPolling,
  };
}
