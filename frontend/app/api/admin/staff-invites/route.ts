import { NextRequest } from "next/server";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";
import { ensureIdempotencyHeaders } from "@/src/lib/idempotency";

type BackendStaffInviteCreate = {
  email: string;
  confirmation_email: string;
  mfa_code: string;
  role_name?: "recruiter";
};

type BackendStaffInviteResponse = {
  id: string;
  email: string;
  role_name: string;
  expires_at: string;
  accepted_at: string | null;
  invite_token?: string | null;
};

export async function POST(request: NextRequest) {
  const body = (await request.json()) as BackendStaffInviteCreate;

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/staff-invites", {
      method: "POST",
      headers: ensureIdempotencyHeaders(request, "staff-invite", {
        "Content-Type": "application/json",
      }),
      body: JSON.stringify({
        email: body.email,
        confirmation_email: body.confirmation_email,
        mfa_code: body.mfa_code,
        role_name: body.role_name ?? "recruiter",
      }),
    });
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, (payload: BackendStaffInviteResponse) => payload, 201);
}
