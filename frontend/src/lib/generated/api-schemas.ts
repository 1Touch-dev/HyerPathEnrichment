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
