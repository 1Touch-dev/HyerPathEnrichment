import type { JobPostingFilters, AdminPortfolioFilters } from "./client";
import type { AiActionFilters } from "./client";

export const adminKeys = {
  all: ["admin"] as const,
  users: (cursor: string | null, isActive: boolean | null) =>
    [...adminKeys.all, "users", cursor, isActive] as const,
  roles: () => [...adminKeys.all, "roles"] as const,
  auditLogs: (cursor: string | null, action: string | null) =>
    [...adminKeys.all, "audit-logs", cursor, action] as const,
  aiActionsAll: () => [...adminKeys.all, "ai-actions"] as const,
  aiActions: (cursor: string | null, filters: AiActionFilters = {}) =>
    [
      ...adminKeys.aiActionsAll(),
      cursor,
      filters.candidateId ?? null,
      filters.recruiterId ?? null,
      filters.actionType ?? null,
      filters.since ?? null,
      filters.until ?? null,
    ] as const,
  aiAction: (id: string) => [...adminKeys.aiActionsAll(), id] as const,
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
  documents: (cursor: string | null, processingStatus: string | null, deleted: boolean | null) =>
    [...adminKeys.all, "documents", cursor, processingStatus, deleted] as const,
  document: (id: string) => [...adminKeys.all, "documents", id] as const,
  portfolio: (cursor: string | null, filters: AdminPortfolioFilters = {}) =>
    [
      ...adminKeys.all,
      "portfolio",
      cursor,
      filters.isPublished ?? null,
      filters.adminHidden ?? null,
    ] as const,
  portfolioProfile: (profileId: string) => [...adminKeys.all, "portfolio", profileId] as const,
  outreach: (cursor: string | null, status: string | null, adminBlocked: boolean | null) =>
    [...adminKeys.all, "outreach", cursor, status, adminBlocked] as const,
  outreachMessage: (id: string) => [...adminKeys.all, "outreach", id] as const,
  linkedinTasks: (status: string | null) => [...adminKeys.all, "linkedin-tasks", status] as const,
};
