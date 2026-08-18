import { NextRequest } from "next/server";
import {
  BackendDocumentUploadResponse,
  mapBackendDocumentUploadResponse,
} from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import {
  bffServiceUnavailable,
  bffValidationError,
  handleBackendJson,
} from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const incomingFormData = await request.formData();
  const file = incomingFormData.get("file");

  if (!(file instanceof File)) {
    return bffValidationError("A file is required.");
  }

  const documentTypeRaw = incomingFormData.get("document_type");
  const documentType =
    typeof documentTypeRaw === "string" && documentTypeRaw ? documentTypeRaw : "cv";

  // Re-pack into a fresh FormData — do not set Content-Type manually, fetch
  // derives the multipart boundary itself from the body.
  const formData = new FormData();
  formData.append("file", file, file.name);

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(
      `/api/documents/upload?document_type=${encodeURIComponent(documentType)}`,
      {
        method: "POST",
        body: formData,
      },
    );
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, (payload: BackendDocumentUploadResponse) =>
    mapBackendDocumentUploadResponse(payload),
  );
}
