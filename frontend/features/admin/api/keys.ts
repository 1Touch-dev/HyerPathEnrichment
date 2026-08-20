import type { JobPostingFilters } from "./client";

export const adminKeys = {
  all: ["admin"] as const,
  users: (cursor: string | null, isActive: boolean | null) =>
    [...adminKeys.all, "users", cursor, isActive] as const,
  roles: () => [...adminKeys.all, "roles"] as const,
  auditLogs: (cursor: string | null, action: string | null) =>
    [...adminKeys.all, "audit-logs", cursor, action] as const,
  featureFlags: () => [...adminKeys.all, "feature-flags"] as const,
  queues: () => [...adminKeys.all, "queues"] as const,
  failedJobs: (queueName: string) => [...adminKeys.all, "queues", queueName, "failed"] as const,
  systemHealth: () => [...adminKeys.all, "system-health"] as const,
  analytics: () => [...adminKeys.all, "analytics", "job-matches"] as const,
  mfaStatus: () => [...adminKeys.all, "mfa-status"] as const,
  impersonationStatus: () => [...adminKeys.all, "impersonation-status"] as const,
  reviewQueueAll: () => [...adminKeys.all, "review-queue"] as const,
  reviewQueue: (cursor: string | null, resourceType: string | null, status: string | null) =>
    [...adminKeys.reviewQueueAll(), cursor, resourceType, status] as const,
  reviewQueueItem: (id: string) => [...adminKeys.reviewQueueAll(), id] as const,
  jobPostings: (cursor: string | null, filters: JobPostingFilters) =>
    [...adminKeys.all, "job-postings", cursor, filters] as const,
  jobPosting: (id: string) => [...adminKeys.all, "job-postings", id] as const,
};
