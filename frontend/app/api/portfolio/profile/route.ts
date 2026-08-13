import { NextRequest } from "next/server";
import { adaptPortfolioProfile } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import {
  backendFailureResponse,
  bffServiceUnavailable,
  bffValidationError,
  handleBackendJson,
} from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

export async function GET() {
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/portfolio/profile");
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, adaptPortfolioProfile);
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
  return handleBackendJson(backendResponse, adaptPortfolioProfile);
}
