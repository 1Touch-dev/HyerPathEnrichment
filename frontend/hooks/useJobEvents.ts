"use client";

import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

interface UseJobEventsOptions {
  jobId: string;
  enabled?: boolean;
  onStatusChange?: (status: string) => void;
}

export function useJobEvents({ jobId, enabled = true, onStatusChange }: UseJobEventsOptions) {
  const [eventSource, setEventSource] = useState<EventSource | null>(null);
  const queryClient = useQueryClient();
  const onStatusChangeRef = useRef(onStatusChange);

  useEffect(() => {
    onStatusChangeRef.current = onStatusChange;
  }, [onStatusChange]);

  useEffect(() => {
    if (!enabled || !jobId) {
      return;
    }

    // Create SSE connection
    const url = `/enrich/${jobId}/events`;
    const es = new EventSource(url);

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        // Handle status change
        if (data.status) {
          onStatusChangeRef.current?.(data.status);

          // If job completed, failed, or suppressed, invalidate queries and close connection
          if (["completed", "failed", "suppressed"].includes(data.status)) {
            queryClient.invalidateQueries({ queryKey: ["enrichment", jobId] });
            es.close();
          }
        }
      } catch (error) {
        console.error("Failed to parse SSE message:", error);
      }
    };

    es.onerror = (error) => {
      console.error("SSE error:", error);
      es.close();
    };

    setEventSource(es);

    // Cleanup on unmount
    return () => {
      es.close();
    };
  }, [jobId, enabled, queryClient]);

  return {
    close: () => eventSource?.close(),
  };
}
