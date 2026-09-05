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
// `apply_clicked_at`/`applied_at` are added ahead of the backend's Module 4 §6 (apply
// tracking) landing and the openapi:gen regeneration that will follow it — same pattern
// as BackendJobResponse's `& { error?: string }` above. Drop this intersection once
// `openapi:gen` picks up the real fields from the backend's committed OpenAPI schema.
export type BackendJobMatchResponse = Schemas['JobMatchResponse'] & {
  apply_clicked_at?: string | null;
  applied_at?: string | null;
  is_blurred?: boolean;
};
export type BackendJobMatchListResponse = Schemas['JobMatchListResponse'];
export type BackendScanTriggerResponse = Schemas['ScanTriggerResponse'];
export type BackendQuestionRequest = Schemas['QuestionRequest'];
export type BackendQuestionItem = Schemas['QuestionItem'];
export type BackendQuestionListResponse = Schemas['QuestionListResponse'];
export type BackendAudioUploadResponse = Schemas['AudioUploadResponse'];
export type BackendAudioStatusResponse = Schemas['AudioStatusResponse'];
export type BackendQuestionAttemptResponse = Schemas['QuestionAttemptResponse'];
export type BackendSessionResponse = Schemas['SessionResponse'];
export type BackendSessionListResponse = Schemas['SessionListResponse'];
