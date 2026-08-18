import { NextRequest } from "next/server";
import {
  BackendFeatureFlagResponse,
  mapBackendFeatureFlag,
  toBackendFeatureFlagRequest,
} from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";
import { FeatureFlag } from "@/src/lib/types";

export async function PUT(request: NextRequest, { params }: { params: Promise<{ key: string }> }) {
  const { key } = await params;
  const body = (await request.json()) as Partial<FeatureFlag>;

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/admin/feature-flags/${key}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(toBackendFeatureFlagRequest(body)),
    });
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, (payload: BackendFeatureFlagResponse) =>
    mapBackendFeatureFlag(payload),
  );
}
