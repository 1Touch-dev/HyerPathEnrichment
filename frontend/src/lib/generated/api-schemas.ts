/**
 * Wire-format types derived from the committed OpenAPI schema.
 * Regenerate via `npm run openapi:gen` after backend contract changes.
 */
import type { components } from '@/src/lib/generated/openapi';

type Schemas = components['schemas'];

export type BackendDossier = Schemas['Dossier'];
export type BackendJobResponse = Schemas['EnrichmentJobResponse'] & { error?: string };
export type BackendJobListItem = Schemas['EnrichmentJobListItem'];
export type BackendJobListResponse = Schemas['EnrichmentJobListResponse'];
export type BackendHealthResponse = Schemas['HealthResponse'];
export type BackendDsarResponse = Schemas['DsarResponse'];
export type BackendSignalListItem = Schemas['SignalListItem'];
export type BackendSignalListResponse = Schemas['SignalListResponse'];
export type BackendEnrichmentRequest = Schemas['EnrichmentRequest'];
export type BackendSuppressionRequest = Schemas['SuppressionRequest'];
export type BackendJobPreferencesRequest = Schemas['JobPreferencesRequest'];
export type BackendJobPreferencesResponse = Schemas['JobPreferencesResponse'];
export type BackendJobMatchResponse = Schemas['JobMatchResponse'];
export type BackendJobMatchListResponse = Schemas['JobMatchListResponse'];
export type BackendScanTriggerResponse = Schemas['ScanTriggerResponse'];
export type BackendDocumentMetadata = Schemas['DocumentMetadata'];
export type BackendDocumentDetailResponse = Schemas['DocumentDetailResponse'];
export type BackendDocumentUploadResponse = Schemas['DocumentUploadResponse'];
export type BackendJobStatusResponse = Schemas['JobStatusResponse'];
export type BackendCVDataResponse = Schemas['CVDataResponse'];
export type BackendSearchResult = Schemas['SearchResult'];
export type BackendSearchResponse = Schemas['SearchResponse'];

// Admin module (backend/app/modules/admin/schemas.py)
export type BackendAdminUserResponse = Schemas['AdminUserResponse'];
export type BackendAdminUserListResponse = Schemas['AdminUserListResponse'];
export type BackendUpdateUserStatusRequest = Schemas['UpdateUserStatusRequest'];
export type BackendAssignRoleRequest = Schemas['AssignRoleRequest'];
export type BackendAdminAuditLogEntryResponse = Schemas['AdminAuditLogEntryResponse'];
export type BackendAdminAuditLogListResponse = Schemas['AdminAuditLogListResponse'];
export type BackendRoleWithPermissionsResponse = Schemas['RoleWithPermissionsResponse'];
export type BackendFeatureFlagResponse = Schemas['FeatureFlagResponse'];
export type BackendUpsertFeatureFlagRequest = Schemas['UpsertFeatureFlagRequest'];
export type BackendQueueSnapshotResponse = Schemas['QueueSnapshotResponse'];
export type BackendQueuesOverviewResponse = Schemas['QueuesOverviewResponse'];
export type BackendFailedJobResponse = Schemas['FailedJobResponse'];
export type BackendSystemHealthResponse = Schemas['SystemHealthResponse'];
export type BackendJobMatchAnalyticsResponse = Schemas['JobMatchAnalyticsResponse'];
export type BackendMfaEnrollResponse = Schemas['MfaEnrollResponse'];
export type BackendMfaStatusResponse = Schemas['MfaStatusResponse'];
export type BackendMfaVerifyRequest = Schemas['MfaVerifyRequest'];
export type BackendImpersonationStartRequest = Schemas['ImpersonationStartRequest'];
export type BackendImpersonationStartResponse = Schemas['ImpersonationStartResponse'];
export type BackendImpersonationStatusResponse = Schemas['ImpersonationStatusResponse'];
