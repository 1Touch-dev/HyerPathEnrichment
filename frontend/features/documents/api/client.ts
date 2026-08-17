import type {
  CandidateDocument,
  CandidateDocumentDetail,
  CvData,
  DocumentJobStatus,
  DocumentSearchResponse,
  DocumentType,
  DocumentUploadResult,
} from "@/src/lib/types";

export async function fetchDocuments(limit = 50): Promise<CandidateDocument[]> {
  const res = await fetch(`/api/documents?limit=${limit}`);
  if (!res.ok) throw new Error(`Failed to fetch documents: ${res.status}`);
  const json = await res.json();
  return json.data;
}

export async function uploadDocument(
  file: File,
  documentType: DocumentType,
): Promise<DocumentUploadResult> {
  const formData = new FormData();
  formData.append("file", file, file.name);
  formData.append("document_type", documentType);

  const res = await fetch("/api/documents/upload", {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(`Failed to upload document: ${res.status}`);
  const json = await res.json();
  return json.data;
}

export async function fetchDocumentJob(jobId: string): Promise<DocumentJobStatus> {
  const res = await fetch(`/api/documents/jobs/${jobId}`);
  if (!res.ok) throw new Error(`Failed to fetch document job: ${res.status}`);
  const json = await res.json();
  return json.data;
}

export async function fetchDocument(documentId: string): Promise<CandidateDocumentDetail> {
  const res = await fetch(`/api/documents/${documentId}`);
  if (!res.ok) throw new Error(`Failed to fetch document: ${res.status}`);
  const json = await res.json();
  return json.data;
}

export async function fetchCvData(documentId: string): Promise<CvData> {
  const res = await fetch(`/api/documents/${documentId}/cv-data`);
  if (!res.ok) throw new Error(`Failed to fetch CV data: ${res.status}`);
  const json = await res.json();
  return json.data;
}

export async function deleteDocument(documentId: string): Promise<void> {
  const res = await fetch(`/api/documents/${documentId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Failed to delete document: ${res.status}`);
}

export async function reprocessDocument(documentId: string): Promise<DocumentUploadResult> {
  const res = await fetch(`/api/documents/${documentId}/reprocess`, { method: "POST" });
  if (!res.ok) throw new Error(`Failed to reprocess document: ${res.status}`);
  const json = await res.json();
  return json.data;
}

export async function searchDocuments(query: string, limit = 10): Promise<DocumentSearchResponse> {
  const res = await fetch("/api/documents/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, limit }),
  });
  if (!res.ok) throw new Error(`Failed to search documents: ${res.status}`);
  const json = await res.json();
  return json.data;
}
