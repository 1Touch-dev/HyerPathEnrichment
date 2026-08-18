"use client";

import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { jobMatchingKeys } from "../api/keys";

const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_DELAY_MS = 2000;

interface UnreadMatchCountPayload {
  unread_count?: number;
}

/**
 * Subscribes to the BFF's `/api/job-matching/events` SSE proxy for the caller's
 * live unread-match count, invalidating job-matching queries whenever the count
 * changes so `useMatches` (poll-based) picks up fresh data immediately.
 *
 * Reconnect strategy: modeled on `src/lib/enrich-events.ts`'s exponential-backoff
 * reconnect (not `hooks/useJobEvents.ts`, which closes on error without retrying)
 * — this stream is long-lived and has no terminal state, so silently giving up on
 * the first network hiccup would leave the badge stale for the rest of the session.
 */
export function useUnreadMatchEvents(enabled = true) {
  const [unreadCount, setUnreadCount] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const unreadCountRef = useRef<number | null>(null);

  useEffect(() => {
    if (!enabled) {
      return;
    }

    let source: EventSource | null = null;
    let reconnectAttempts = 0;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let isClosed = false;

    function connect() {
      if (isClosed) return;

      setError(null);
      source = new EventSource("/api/job-matching/events");

      source.onmessage = (event: MessageEvent<string>) => {
        reconnectAttempts = 0;
        try {
          const payload = JSON.parse(event.data) as UnreadMatchCountPayload;
          if (typeof payload.unread_count !== "number") {
            return;
          }
          const nextCount = payload.unread_count;
          if (unreadCountRef.current !== nextCount) {
            unreadCountRef.current = nextCount;
            setUnreadCount(nextCount);
            queryClient.invalidateQueries({ queryKey: jobMatchingKeys.all });
          }
        } catch {
          // Malformed payload — ignore; the next message (or reconnect) self-heals.
        }
      };

      source.onerror = () => {
        source?.close();
        if (isClosed) return;

        if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
          const delay = RECONNECT_DELAY_MS * Math.pow(2, reconnectAttempts);
          reconnectAttempts++;
          reconnectTimer = setTimeout(() => {
            if (!isClosed) connect();
          }, delay);
        } else {
          setError("Failed to connect to job-matching events stream.");
        }
      };
    }

    connect();

    return () => {
      isClosed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      source?.close();
      source = null;
    };
  }, [enabled, queryClient]);

  return { unreadCount, error };
}
