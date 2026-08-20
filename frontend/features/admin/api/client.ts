import type {
  AdminAuditLogListResponse,
  AdminDocument,
  AdminDocumentFilters,
  AdminDocumentListResponse,
  AdminDocumentModerateAction,
  AdminUserListResponse,
  AdminRole,
  FailedJob,
  FeatureFlag,
  ImpersonationStatus,
  JobMatchAnalytics,
  MfaEnrollResult,
  MfaStatus,
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

export async function fetchRoles(): Promise<AdminRole[]> {
  const res = await fetch("/api/admin/roles");
  return unwrap(res, "Failed to fetch roles");
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
