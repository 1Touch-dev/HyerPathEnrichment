import { NextRequest } from "next/server";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

type BackendStaffInviteResponse = {
  id: string;
  email: string;
  role_name: string;
  expires_at: string;
  accepted_at: string | null;
};

export async function POST(request: NextRequest) {
  const body = (await request.json()) as { email: string; role_name?: string };

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/staff-invites", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, (payload: BackendStaffInviteResponse) => payload, 201);
}
