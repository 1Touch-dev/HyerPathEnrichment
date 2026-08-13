import { NextRequest } from "next/server";
import { adaptPortfolioProfile } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import {
  backendFailureResponse,
  bffServiceUnavailable,
  bffValidationError,
  handleBackendJson,
} from "@/src/lib/bff-response";
import { BackendPortfolioProfile, toRawPortfolioProfile } from "@/features/portfolio/lib/backend-shapes";

export const dynamic = "force-dynamic";

function mapProfile(raw: BackendPortfolioProfile) {
  return adaptPortfolioProfile(toRawPortfolioProfile(raw));
}

export async function GET() {
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/portfolio/profile");
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, mapProfile);
}

export async function PUT(request: NextRequest) {
  const body = await request.json();
  if (typeof body?.slug !== "string" || !body.slug.trim()) {
    return bffValidationError("A slug is required.");
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/portfolio/profile", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        slug: body.slug,
        headline: body.headline ?? null,
        // Backend field is `bio` (see PortfolioProfileRequest); frontend calls it `summary`.
        bio: body.summary ?? null,
        is_published: body.isPublished ?? false,
      }),
    });
  } catch {
    return bffServiceUnavailable();
  }
  if (!backendResponse.ok) return backendFailureResponse(backendResponse);
  return handleBackendJson(backendResponse, mapProfile);
}
