"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "active_jobs";
const MAX_COMPLETED_AGE_MS = 5 * 60 * 1000; // 5 minutes

export type TrackedJob = {
  id: string;
  status: "queued" | "running" | "completed" | "failed" | "suppressed";
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
    if (job.status === "queued" || job.status === "running") {
      return true; // Keep active jobs
    }
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

  const addJob = (id: string, status: TrackedJob["status"] = "queued") => {
    setJobs((prev) => {
      const exists = prev.find((j) => j.id === id);
      if (exists) return prev;
      
      const cleaned = cleanupOldJobs(prev);
      return [...cleaned, { id, status, createdAt: Date.now() }];
    });
  };

  const updateJobStatus = (id: string, status: TrackedJob["status"]) => {
    setJobs((prev) =>
      prev.map((job) =>
        job.id === id
          ? {
              ...job,
              status,
              completedAt:
                status === "completed" || status === "failed" || status === "suppressed"
                  ? Date.now()
                  : job.completedAt,
            }
          : job
      )
    );
  };

  const removeJob = (id: string) => {
    setJobs((prev) => prev.filter((job) => job.id !== id));
  };

  const clearCompleted = () => {
    setJobs((prev) => prev.filter((job) => job.status === "queued" || job.status === "running"));
  };

  const activeJobs = jobs.filter((job) => job.status === "queued" || job.status === "running");

  return {
    jobs: cleanupOldJobs(jobs),
    activeJobs,
    addJob,
    updateJobStatus,
    removeJob,
    clearCompleted,
  };
}
