import { NextRequest } from "next/server";
import {
  BackendRoleWithPermissionsResponse,
  mapBackendRoleWithPermissions,
} from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export async function GET() {
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/admin/roles");
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, (payload: BackendRoleWithPermissionsResponse[]) =>
    payload.map(mapBackendRoleWithPermissions),
  );
}

export async function POST(request: NextRequest) {
  const body = (await request.json()) as { name: string; description?: string | null };

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/admin/roles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, (payload: BackendRoleWithPermissionsResponse) =>
    mapBackendRoleWithPermissions(payload),
  );
}
