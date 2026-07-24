import { JobStatus } from "@/src/lib/types";

const VALID_STATUSES: readonly JobStatus[] = [
  "queued",
  "running",
  "completed",
  "failed",
  "suppressed",
];

const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_DELAY_MS = 2000;

function parseJobStatus(raw: string): JobStatus | null {
  return (VALID_STATUSES as readonly string[]).includes(raw) ? (raw as JobStatus) : null;
}

export type JobEventHandlers = {
  onStatus?: (status: JobStatus) => void;
  onError?: (event: Event) => void;
  onReconnect?: () => void;
};

/**
 * Opens an EventSource against the BFF's `/api/enrich/[id]/events` proxy and
 * reports parsed job status updates. Returns an unsubscribe function that
 * closes the connection; safe to call multiple times.
 *
 * Implements automatic reconnection with exponential backoff on connection errors.
 */
export function subscribeJobEvents(jobId: string, handlers: JobEventHandlers): () => void {
  let source: EventSource | null = null;
  let reconnectAttempts = 0;
  let reconnectTimer: NodeJS.Timeout | null = null;
  let isClosed = false;

  function connect() {
    if (isClosed) return;

    source = new EventSource(`/api/enrich/${encodeURIComponent(jobId)}/events`);

    source.onmessage = (event: MessageEvent<string>) => {
      reconnectAttempts = 0; // Reset on successful message
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

      // Close the failed connection
      source?.close();

      if (isClosed) return;

      // Attempt reconnection with exponential backoff
      if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
        const delay = RECONNECT_DELAY_MS * Math.pow(2, reconnectAttempts);
        reconnectAttempts++;

        reconnectTimer = setTimeout(() => {
          if (!isClosed) {
            handlers.onReconnect?.();
            connect();
          }
        }, delay);
      }
    };
  }

  connect();

  return () => {
    isClosed = true;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    source?.close();
    source = null;
  };
}
