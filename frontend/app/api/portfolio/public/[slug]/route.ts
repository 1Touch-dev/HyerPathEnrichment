import { NextRequest } from "next/server";
import { adaptPublicPortfolioProfile } from "@/src/lib/api-adapter";
import { backendFetchPublic } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";
import { BackendPublicPortfolioProfile, toRawPublicPortfolioProfile } from "@/features/portfolio/lib/backend-shapes";

export const dynamic = "force-dynamic";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ slug: string }> },
) {
  const { slug } = await params;
  let backendResponse: Response;
  try {
    backendResponse = await backendFetchPublic(`/api/portfolio/public/${slug}`);
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, (raw: BackendPublicPortfolioProfile) =>
    adaptPublicPortfolioProfile(toRawPublicPortfolioProfile(raw)),
  );
}
