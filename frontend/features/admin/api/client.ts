import type {
  AdminAuditLogListResponse,
  AdminJobPosting,
  AdminJobPostingListResponse,
  AdminDocument,
  AdminDocumentFilters,
  AdminDocumentListResponse,
  AdminDocumentModerateAction,
  AdminPortfolioProfile,
  AdminPortfolioProfileDetail,
  AdminPortfolioProfileListResponse,
  AdminOutreachMessage,
  AdminOutreachMessageListResponse,
  AdminUserListResponse,
  AdminRole,
  AdminRoleWithPermissions,
  AdminReviewQueueDetail,
  AdminReviewQueueItem,
  AdminReviewQueueListResponse,
  FailedJob,
  FeatureFlag,
  ImpersonationStatus,
  JobMatchAnalytics,
  LinkedInSendBatch,
  LinkedInSendTask,
  MfaEnrollResult,
  MfaStatus,
  ModerationStatus,
  QueueSnapshot,
  SystemHealthSnapshot,
} from "@/src/lib/types";

async function unwrap<T>(res: Response, errorLabel: string): Promise<T> {
  if (!res.ok) throw new Error(`${errorLabel}: ${res.status}`);
  const json = await res.json();
  return json.data as T;
}

export async function fetchAdminUsers(
  cursor: string | null,
  isActive: boolean | null,
): Promise<AdminUserListResponse> {
  const params = new URLSearchParams();
  if (cursor) params.set("cursor", cursor);
  if (isActive !== null) params.set("is_active", String(isActive));
  const res = await fetch(`/api/admin/users?${params.toString()}`);
  return unwrap(res, "Failed to fetch users");
}

export async function updateUserStatus(
  userId: string,
  isActive: boolean,
  reason?: string,
): Promise<void> {
  const res = await fetch(`/api/admin/users/${userId}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_active: isActive, reason }),
  });
  if (!res.ok) throw new Error(`Failed to update user status: ${res.status}`);
}

export async function assignUserRole(userId: string, roleId: string | null): Promise<void> {
  const res = await fetch(`/api/admin/users/${userId}/role`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role_id: roleId }),
  });
  if (!res.ok) throw new Error(`Failed to assign role: ${res.status}`);
}

export type JobPostingFilters = {
  moderationStatus?: ModerationStatus | null;
  source?: string | null;
  isActive?: boolean | null;
};

export async function fetchAdminJobPostings(
  cursor: string | null,
  filters: JobPostingFilters = {},
): Promise<AdminJobPostingListResponse> {
  const params = new URLSearchParams();
  if (cursor) params.set("cursor", cursor);
  if (filters.moderationStatus) params.set("moderation_status", filters.moderationStatus);
  if (filters.source) params.set("source", filters.source);
  if (filters.isActive !== null && filters.isActive !== undefined) {
    params.set("is_active", String(filters.isActive));
  }
  const res = await fetch(`/api/admin/job-postings?${params.toString()}`);
  return unwrap(res, "Failed to fetch job postings");
}

export async function fetchAdminJobPosting(id: string): Promise<AdminJobPosting> {
  const res = await fetch(`/api/admin/job-postings/${id}`);
  return unwrap(res, "Failed to fetch job posting");
}

export async function moderateJobPosting(
  id: string,
  moderationStatus: ModerationStatus,
  reason?: string,
): Promise<AdminJobPosting> {
  const res = await fetch(`/api/admin/job-postings/${id}/moderate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ moderation_status: moderationStatus, reason }),
  });
  return unwrap(res, "Failed to moderate job posting");
}

export type AdminOutreachFilters = {
  status?: string | null;
  adminBlocked?: boolean | null;
};

export async function fetchAdminOutreachMessages(
  cursor: string | null,
  filters: AdminOutreachFilters = {},
): Promise<AdminOutreachMessageListResponse> {
  const params = new URLSearchParams();
  if (cursor) params.set("cursor", cursor);
  if (filters.status) params.set("status", filters.status);
  if (filters.adminBlocked !== null && filters.adminBlocked !== undefined) {
    params.set("admin_blocked", String(filters.adminBlocked));
  }
  const res = await fetch(`/api/admin/outreach?${params.toString()}`);
  return unwrap(res, "Failed to fetch outreach messages");
}

export async function fetchAdminOutreachMessage(id: string): Promise<AdminOutreachMessage> {
  const res = await fetch(`/api/admin/outreach/${id}`);
  return unwrap(res, "Failed to fetch outreach message");
}

export async function moderateOutreachMessage(
  id: string,
  adminBlocked: boolean,
  reason?: string,
): Promise<void> {
  const res = await fetch(`/api/admin/outreach/${id}/moderate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ admin_blocked: adminBlocked, reason }),
  });
  if (!res.ok) throw new Error(`Failed to moderate outreach message: ${res.status}`);
}

export async function fetchRoles(): Promise<AdminRole[]> {
  const res = await fetch("/api/admin/roles");
  return unwrap(res, "Failed to fetch roles");
}

export async function createRole(body: {
  name: string;
  description?: string | null;
}): Promise<AdminRoleWithPermissions> {
  const res = await fetch("/api/admin/roles", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return unwrap(res, "Failed to create role");
}

export async function attachPermission(roleId: string, permissionId: string): Promise<void> {
  const res = await fetch(`/api/admin/roles/${roleId}/permissions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ permission_id: permissionId }),
  });
  if (!res.ok) throw new Error(`Failed to attach permission: ${res.status}`);
}

export async function detachPermission(roleId: string, permissionId: string): Promise<void> {
  const res = await fetch(`/api/admin/roles/${roleId}/permissions/${permissionId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Failed to detach permission: ${res.status}`);
}

export async function fetchAuditLogs(
  cursor: string | null,
  action: string | null,
): Promise<AdminAuditLogListResponse> {
  const params = new URLSearchParams();
  if (cursor) params.set("cursor", cursor);
  if (action) params.set("action", action);
  const res = await fetch(`/api/admin/audit-logs?${params.toString()}`);
  return unwrap(res, "Failed to fetch audit logs");
}

export type AdminPortfolioFilters = {
  isPublished?: boolean | null;
  adminHidden?: boolean | null;
};

export async function fetchAdminPortfolioProfiles(
  cursor: string | null,
  filters: AdminPortfolioFilters = {},
): Promise<AdminPortfolioProfileListResponse> {
  const params = new URLSearchParams();
  if (cursor) params.set("cursor", cursor);
  if (filters.isPublished !== null && filters.isPublished !== undefined) {
    params.set("is_published", String(filters.isPublished));
  }
  if (filters.adminHidden !== null && filters.adminHidden !== undefined) {
    params.set("admin_hidden", String(filters.adminHidden));
  }
  const res = await fetch(`/api/admin/portfolio?${params.toString()}`);
  return unwrap(res, "Failed to fetch portfolio profiles");
}

export async function fetchAdminPortfolioProfile(
  profileId: string,
): Promise<AdminPortfolioProfileDetail> {
  const res = await fetch(`/api/admin/portfolio/${profileId}`);
  return unwrap(res, "Failed to fetch portfolio profile");
}

export async function moderatePortfolioProfile(
  profileId: string,
  adminHidden: boolean,
  reason?: string,
): Promise<AdminPortfolioProfile> {
  const res = await fetch(`/api/admin/portfolio/${profileId}/moderate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ admin_hidden: adminHidden, reason }),
  });
  return unwrap(res, "Failed to moderate portfolio profile");
}

export async function fetchFeatureFlags(): Promise<FeatureFlag[]> {
  const res = await fetch("/api/admin/feature-flags");
  return unwrap(res, "Failed to fetch feature flags");
}

export async function upsertFeatureFlag(
  key: string,
  payload: Partial<FeatureFlag>,
): Promise<FeatureFlag> {
  const res = await fetch(`/api/admin/feature-flags/${key}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return unwrap(res, "Failed to update feature flag");
}

export async function fetchQueuesOverview(): Promise<QueueSnapshot[]> {
  const res = await fetch("/api/admin/queues");
  return unwrap(res, "Failed to fetch queues");
}

export async function fetchFailedJobs(queueName: string): Promise<FailedJob[]> {
  const res = await fetch(`/api/admin/queues/${queueName}/failed`);
  return unwrap(res, "Failed to fetch failed jobs");
}

export async function retryFailedJob(queueName: string, jobId: string): Promise<void> {
  const res = await fetch(`/api/admin/queues/${queueName}/failed/${jobId}/retry`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`Failed to retry job: ${res.status}`);
}

export async function fetchSystemHealth(): Promise<SystemHealthSnapshot> {
  const res = await fetch("/api/admin/system-health");
  return unwrap(res, "Failed to fetch system health");
}

export async function fetchJobMatchAnalytics(refresh = false): Promise<JobMatchAnalytics> {
  const res = await fetch(`/api/admin/analytics/job-matches${refresh ? "?refresh=1" : ""}`);
  return unwrap(res, "Failed to fetch analytics");
}

export async function fetchMfaStatus(): Promise<MfaStatus> {
  const res = await fetch("/api/admin/mfa/status");
  return unwrap(res, "Failed to fetch MFA status");
}

export async function enrollMfa(): Promise<MfaEnrollResult> {
  const res = await fetch("/api/admin/mfa/enroll", { method: "POST" });
  return unwrap(res, "Failed to enroll MFA");
}

export async function confirmMfaEnrollment(code: string): Promise<void> {
  const res = await fetch("/api/admin/mfa/confirm", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });
  if (!res.ok) throw new Error(`Failed to confirm MFA: ${res.status}`);
}

export async function disableMfa(): Promise<void> {
  const res = await fetch("/api/admin/mfa/disable", { method: "POST" });
  if (!res.ok) throw new Error(`Failed to disable MFA: ${res.status}`);
}

export async function startImpersonation(
  userId: string,
  reason: string,
  mfaCode?: string,
): Promise<void> {
  const res = await fetch(`/api/admin/impersonation/start/${userId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason, mfa_code: mfaCode }),
  });
  if (!res.ok) throw new Error(`Failed to start impersonation: ${res.status}`);
}

export async function endImpersonation(): Promise<void> {
  const res = await fetch("/api/admin/impersonation/end", { method: "POST" });
  if (!res.ok) throw new Error(`Failed to end impersonation: ${res.status}`);
}

export async function fetchImpersonationStatus(): Promise<ImpersonationStatus> {
  const res = await fetch("/api/admin/impersonation/status");
  return unwrap(res, "Failed to fetch impersonation status");
}

export async function fetchReviewQueue(
  cursor: string | null,
  resourceType: string | null,
  status: string | null,
): Promise<AdminReviewQueueListResponse> {
  const params = new URLSearchParams();
  if (cursor) params.set("cursor", cursor);
  if (resourceType) params.set("resource_type", resourceType);
  if (status) params.set("status", status);
  const res = await fetch(`/api/admin/review-queue?${params.toString()}`);
  return unwrap(res, "Failed to fetch review queue");
}

export async function fetchReviewQueueItem(id: string): Promise<AdminReviewQueueDetail> {
  const res = await fetch(`/api/admin/review-queue/${id}`);
  return unwrap(res, "Failed to fetch review queue item");
}

export async function decideReviewQueueItem(
  id: string,
  status: "approved" | "rejected",
  reviewNotes?: string,
): Promise<AdminReviewQueueItem> {
  const res = await fetch(`/api/admin/review-queue/${id}/decide`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, review_notes: reviewNotes }),
  });
  return unwrap(res, "Failed to decide review queue item");
}

export async function fetchAdminDocuments(
  cursor: string | null,
  filters: AdminDocumentFilters = { processingStatus: null, deleted: null },
): Promise<AdminDocumentListResponse> {
  const params = new URLSearchParams();
  if (cursor) params.set("cursor", cursor);
  if (filters.processingStatus) params.set("processing_status", filters.processingStatus);
  if (filters.deleted !== null) params.set("deleted", String(filters.deleted));
  const res = await fetch(`/api/admin/documents?${params.toString()}`);
  return unwrap(res, "Failed to fetch documents");
}

export async function fetchAdminDocument(id: string): Promise<AdminDocument> {
  const res = await fetch(`/api/admin/documents/${id}`);
  return unwrap(res, "Failed to fetch document");
}

export async function moderateDocument(
  id: string,
  action: AdminDocumentModerateAction,
  reason?: string,
): Promise<AdminDocument> {
  const res = await fetch(`/api/admin/documents/${id}/moderate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, reason }),
  });
  return unwrap(res, "Failed to moderate document");
}

export async function fetchLinkedInTasks(status: string | null): Promise<LinkedInSendTask[]> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  const res = await fetch(`/api/outreach/linkedin-tasks?${params.toString()}`);
  return unwrap(res, "Failed to fetch LinkedIn tasks");
}

export async function claimLinkedInTask(taskId: string): Promise<LinkedInSendTask> {
  const res = await fetch(`/api/outreach/linkedin-tasks/${taskId}/claim`, { method: "POST" });
  return unwrap(res, "Failed to claim LinkedIn task");
}

export async function completeLinkedInTask(
  taskId: string,
  outcomeNote?: string | null,
): Promise<LinkedInSendTask> {
  const res = await fetch(`/api/outreach/linkedin-tasks/${taskId}/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ outcomeNote: outcomeNote ?? null }),
  });
  return unwrap(res, "Failed to complete LinkedIn task");
}

export async function skipLinkedInTask(
  taskId: string,
  outcomeNote?: string | null,
): Promise<LinkedInSendTask> {
  const res = await fetch(`/api/outreach/linkedin-tasks/${taskId}/skip`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ outcomeNote: outcomeNote ?? null }),
  });
  return unwrap(res, "Failed to skip LinkedIn task");
}

export async function createLinkedInSendBatch(input: {
  multiloginProfileId: string;
  maxSendsPerDay: number;
  taskIds: string[];
}): Promise<LinkedInSendBatch> {
  const res = await fetch("/api/outreach/linkedin-send-batches", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return unwrap(res, "Failed to create LinkedIn send batch");
}

export async function startLinkedInSendBatch(batchId: string): Promise<LinkedInSendBatch> {
  const res = await fetch(`/api/outreach/linkedin-send-batches/${batchId}/start`, {
    method: "POST",
  });
  return unwrap(res, "Failed to start LinkedIn send batch");
}
