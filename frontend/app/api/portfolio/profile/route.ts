import { NextRequest } from "next/server";
import {
  adaptPortfolioProfile,
  toBackendPortfolioContent,
  toBackendPortfolioTheme,
} from "@/src/lib/api-adapter";
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

  const payload: Record<string, unknown> = {
    slug: body.slug,
    display_name: body.displayName ?? body.content?.displayName ?? null,
    headline: body.headline ?? body.content?.headline ?? null,
    // Backend field is `bio` (see PortfolioProfileRequest); frontend calls it `summary`.
    bio: body.summary ?? body.content?.summary ?? null,
    is_published: body.isPublished ?? false,
    publish: body.publish ?? false,
  };

  if (body.templateId) payload.template_id = body.templateId;
  if (body.theme) payload.theme = toBackendPortfolioTheme(body.theme);
  if (body.content) payload.content = toBackendPortfolioContent(body.content);
  if (body.sectionVisibility) payload.section_visibility = body.sectionVisibility;
  if (body.sectionOrder) payload.section_order = body.sectionOrder;

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/portfolio/profile", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    return bffServiceUnavailable();
  }
  if (!backendResponse.ok) return backendFailureResponse(backendResponse);
  return handleBackendJson(backendResponse, adaptPortfolioProfile);
}
