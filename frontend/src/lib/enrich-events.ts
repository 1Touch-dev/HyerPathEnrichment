import { JobStatus } from "@/src/lib/types";

const VALID_STATUSES: readonly JobStatus[] = [
  "queued",
  "running",
  "completed",
  "failed",
  "suppressed",
];

function parseJobStatus(raw: string): JobStatus | null {
  return (VALID_STATUSES as readonly string[]).includes(raw) ? (raw as JobStatus) : null;
}

export type JobEventHandlers = {
  onStatus?: (status: JobStatus) => void;
  onError?: (event: Event) => void;
};

/**
 * Opens an EventSource against the BFF's `/api/enrich/[id]/events` proxy and
 * reports parsed job status updates. Returns an unsubscribe function that
 * closes the connection; safe to call multiple times.
 */
export function subscribeJobEvents(jobId: string, handlers: JobEventHandlers): () => void {
  const source = new EventSource(`/api/enrich/${encodeURIComponent(jobId)}/events`);

  source.onmessage = (event: MessageEvent<string>) => {
    try {
      const payload = JSON.parse(event.data) as { job_id?: string; status?: string };
      const status = payload.status ? parseJobStatus(payload.status) : null;
      if (status) {
        handlers.onStatus?.(status);
      }
    } catch {
      // Malformed payload — ignore; History's poll-based view stays authoritative.
    }
  };

  source.onerror = (event) => {
    handlers.onError?.(event);
  };

  return () => source.close();
}
