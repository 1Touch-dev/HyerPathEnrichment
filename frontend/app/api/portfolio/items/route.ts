import { NextRequest } from "next/server";
import { backendFetch } from "@/src/lib/backend-client";
import {
  backendFailureResponse,
  bffServiceUnavailable,
  bffValidationError,
  handleBackendJson,
} from "@/src/lib/bff-response";
import { BackendPortfolioItem, adaptBackendPortfolioItem, itemTypeToBackend } from "@/features/portfolio/lib/backend-shapes";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const body = await request.json();
  if (typeof body?.url !== "string" || !body.url.trim()) {
    return bffValidationError("A URL is required.");
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/portfolio/items", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        // Backend's PortfolioItemRequest.item_type is "github"|"live_demo"|"case_study"|"other";
        // the frontend PortfolioItem.itemType uses "github_repo"/"other_link" instead.
        item_type: itemTypeToBackend(body.itemType),
        title: body.title,
        description: body.description ?? null,
        url: body.url,
      }),
    });
  } catch {
    return bffServiceUnavailable();
  }
  if (!backendResponse.ok) return backendFailureResponse(backendResponse);
  return handleBackendJson(
    backendResponse,
    (raw: BackendPortfolioItem) => adaptBackendPortfolioItem(raw),
    201,
  );
}
