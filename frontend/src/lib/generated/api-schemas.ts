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
export type BackendQuestionRequest = Schemas['QuestionRequest'];
export type BackendQuestionItem = Schemas['QuestionItem'];
export type BackendQuestionListResponse = Schemas['QuestionListResponse'];
export type BackendAudioUploadResponse = Schemas['AudioUploadResponse'];
export type BackendAudioStatusResponse = Schemas['AudioStatusResponse'];
export type BackendQuestionAttemptResponse = Schemas['QuestionAttemptResponse'];
export type BackendSessionResponse = Schemas['SessionResponse'];
export type BackendSessionListResponse = Schemas['SessionListResponse'];
