import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/src/lib/backend-client";
import { backendFailureResponse, bffServiceUnavailable } from "@/src/lib/bff-response";

export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ roleId: string; permissionId: string }> },
) {
  const { roleId, permissionId } = await params;

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/admin/roles/${roleId}/permissions/${permissionId}`, {
      method: "DELETE",
    });
  } catch {
    return bffServiceUnavailable();
  }

  if (!backendResponse.ok) return backendFailureResponse(backendResponse);

  // Backend returns 204 No Content on success (roles_router.detach_permission), so
  // there is no JSON body to unwrap/envelope here — pass the status through as-is.
  return new NextResponse(null, { status: backendResponse.status });
}
