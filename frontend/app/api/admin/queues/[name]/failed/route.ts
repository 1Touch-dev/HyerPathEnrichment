import { NextRequest } from "next/server";
import { BackendFailedJobResponse, mapBackendFailedJob } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export async function GET(request: NextRequest, { params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  const searchParams = request.nextUrl.searchParams;
  const query = new URLSearchParams();
  if (searchParams.get("limit")) query.set("limit", searchParams.get("limit")!);

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/admin/queues/${name}/failed?${query.toString()}`);
  } catch {
    return bffServiceUnavailable();
  }

  return handleBackendJson(backendResponse, (payload: BackendFailedJobResponse[]) =>
    payload.map(mapBackendFailedJob),
  );
}
