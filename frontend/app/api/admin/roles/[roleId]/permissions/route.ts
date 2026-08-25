import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/src/lib/backend-client";
import { backendFailureResponse, bffServiceUnavailable } from "@/src/lib/bff-response";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ roleId: string }> },
) {
  const { roleId } = await params;
  const body = (await request.json()) as { permission_id: string };

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/admin/roles/${roleId}/permissions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    return bffServiceUnavailable();
  }

  if (!backendResponse.ok) return backendFailureResponse(backendResponse);

  // Backend returns 204 No Content on success (roles_router.attach_permission), so
  // there is no JSON body to unwrap/envelope here — pass the status through as-is.
  return new NextResponse(null, { status: backendResponse.status });
}
