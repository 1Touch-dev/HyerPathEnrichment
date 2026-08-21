import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

interface RawDocumentMetadata {
  document_id: string;
  document_type: string;
  original_filename: string;
  file_size_bytes: number;
  processing_status: string;
  created_at: string;
}

/**
 * Thin proxy for the backend's existing `GET /api/documents` (list_documents,
 * backend/app/modules/documents/router.py) — no Module 2 track built this yet (flagged
 * as a known gap in phase2_module2.md §13.2's own scope note), but `useDraftOutreachForMatch`
 * (features/outreach/hooks/useOutreach.ts) needs it to resolve "the candidate's most
 * recently completed CV" when drafting outreach from a job-swipe card, which has no
 * documentId of its own.
 */
export async function GET() {
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/documents");
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, (raw: RawDocumentMetadata[]) =>
    raw.map((doc) => ({
      documentId: doc.document_id,
      documentType: doc.document_type,
      originalFilename: doc.original_filename,
      fileSizeBytes: doc.file_size_bytes,
      processingStatus: doc.processing_status,
      createdAt: doc.created_at,
    })),
  );
}
