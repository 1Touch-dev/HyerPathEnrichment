"use client";

import { useEffect, useState, useCallback, useMemo } from "react";

const STORAGE_KEY = "active_jobs";
const MAX_COMPLETED_AGE_MS = 5 * 60 * 1000; // 5 minutes
const MAX_OVERALL_AGE_MS = 60 * 60 * 1000; // 1 hour for ANY job

export type TrackedJob = {
  id: string;
  status: "queued" | "running" | "completed" | "completed_no_data" | "failed" | "suppressed";
  createdAt: number;
  completedAt?: number;
};

function getStoredJobs(): TrackedJob[] {
  if (typeof window === "undefined") return [];

  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return [];
    return JSON.parse(stored) as TrackedJob[];
  } catch {
    return [];
  }
}

function setStoredJobs(jobs: TrackedJob[]): void {
  if (typeof window === "undefined") return;

  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(jobs));
  } catch {
    // Ignore localStorage errors
  }
}

function cleanupOldJobs(jobs: TrackedJob[]): TrackedJob[] {
  const now = Date.now();
  return jobs.filter((job) => {
    // Remove jobs older than 1 hour regardless of status
    if (now - job.createdAt > MAX_OVERALL_AGE_MS) {
      return false;
    }

    // Keep active jobs
    if (job.status === "queued" || job.status === "running") {
      return true;
    }

    // Keep completed jobs for 5 minutes
    if (job.completedAt) {
      return now - job.completedAt < MAX_COMPLETED_AGE_MS;
    }

    return false;
  });
}

export function useLocalStorageJobs() {
  const [jobs, setJobs] = useState<TrackedJob[]>(getStoredJobs);

  useEffect(() => {
    setStoredJobs(jobs);
  }, [jobs]);

  const cleanedJobs = useMemo(() => cleanupOldJobs(jobs), [jobs]);

  const addJob = useCallback((id: string, status: TrackedJob["status"] = "queued") => {
    setJobs((prev) => {
      const exists = prev.find((j) => j.id === id);
      if (exists) return prev;

      const cleaned = cleanupOldJobs(prev);
      return [...cleaned, { id, status, createdAt: Date.now() }];
    });
  }, []);

  const updateJobStatus = useCallback((id: string, status: TrackedJob["status"]) => {
    setJobs((prev) =>
      prev.map((job) =>
        job.id === id
          ? {
              ...job,
              status,
              completedAt:
                status === "completed" ||
                status === "completed_no_data" ||
                status === "failed" ||
                status === "suppressed"
                  ? Date.now()
                  : job.completedAt,
            }
          : job,
      ),
    );
  }, []);

  const removeJob = useCallback((id: string) => {
    setJobs((prev) => prev.filter((job) => job.id !== id));
  }, []);

  const clearCompleted = useCallback(() => {
    setJobs((prev) => prev.filter((job) => job.status === "queued" || job.status === "running"));
  }, []);

  const activeJobs = useMemo(
    () => cleanedJobs.filter((job) => job.status === "queued" || job.status === "running"),
    [cleanedJobs],
  );

  return {
    jobs: cleanedJobs,
    activeJobs,
    addJob,
    updateJobStatus,
    removeJob,
    clearCompleted,
  };
}
