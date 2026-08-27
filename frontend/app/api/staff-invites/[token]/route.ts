import { NextRequest } from "next/server";
import { backendFetchPublic } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

type BackendPublicStaffInviteResponse = {
  invited_by_name: string | null;
  role_name: string;
  email: string;
  expires_at: string;
};

/** Thin proxy for the backend's public, unauthenticated
 * `GET /api/staff-invites/{token}` (staff_invites/router.py's get_invite). */
export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ token: string }> },
) {
  const { token } = await params;
  let backendResponse: Response;
  try {
    backendResponse = await backendFetchPublic(`/api/staff-invites/${token}`);
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, (payload: BackendPublicStaffInviteResponse) => payload);
}
