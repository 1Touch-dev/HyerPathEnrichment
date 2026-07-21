import { EnrichmentJob, JobStatus } from "@/src/lib/types";
import { getEnrichmentJob } from "@/src/lib/api-client";

const TERMINAL_STATUSES: JobStatus[] = ["completed", "failed", "suppressed"];

export type PollOptions = {
  initialIntervalMs?: number;
  maxIntervalMs?: number;
  maxDurationMs?: number;
  onUpdate?: (job: EnrichmentJob) => void;
};

export type PollResult =
  | { status: "completed"; job: EnrichmentJob }
  | { status: "timeout"; job: EnrichmentJob }
  | { status: "error"; error: Error };

export function isTerminalStatus(status: JobStatus): boolean {
  return TERMINAL_STATUSES.includes(status);
}

export async function pollEnrichmentJob(
  jobId: string,
  options: PollOptions = {},
): Promise<PollResult> {
  const initialIntervalMs = options.initialIntervalMs ?? 2000;
  const maxIntervalMs = options.maxIntervalMs ?? 5000;
  const maxDurationMs = options.maxDurationMs ?? 5 * 60 * 1000;

  const startedAt = Date.now();
  let intervalMs = initialIntervalMs;
  let latestJob: EnrichmentJob | null = null;

  while (Date.now() - startedAt < maxDurationMs) {
    await sleep(intervalMs);

    try {
      latestJob = (await getEnrichmentJob(jobId)).data;
      options.onUpdate?.(latestJob);

      if (isTerminalStatus(latestJob.status)) {
        return { status: "completed", job: latestJob };
      }
    } catch (error) {
      return { status: "error", error: error instanceof Error ? error : new Error("Poll failed") };
    }

    intervalMs = Math.min(Math.round(intervalMs * 1.25), maxIntervalMs);
  }

  if (latestJob) {
    return { status: "timeout", job: latestJob };
  }

  return {
    status: "error",
    error: new Error("Polling timed out before receiving a job response"),
  };
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
