import { NextRequest } from "next/server";
import {
  BackendModeratePortfolioRequest,
  mapBackendAdminPortfolioProfile,
} from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const body = (await request.json()) as BackendModeratePortfolioRequest;

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/admin/portfolio/${id}/moderate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, mapBackendAdminPortfolioProfile);
}
