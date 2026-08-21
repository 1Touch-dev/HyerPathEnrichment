import { NextRequest } from "next/server";
import { mapBackendAudioUploadResponse } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

/**
 * Thin proxy for the backend's `POST /api/practice/audio` (upload_audio,
 * backend/app/modules/practice_audio/router.py) — multipart passthrough, body forwarded
 * as `request.formData()` rather than re-serialized as JSON, since this is a file upload.
 */
export async function POST(request: NextRequest) {
  const formData = await request.formData();
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/practice/audio", {
      method: "POST",
      body: formData,
    });
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, mapBackendAudioUploadResponse);
}
