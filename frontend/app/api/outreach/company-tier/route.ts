import { NextRequest } from "next/server";
import { backendFetch } from "@/src/lib/backend-client";
import {
  bffServiceUnavailable,
  bffValidationError,
  handleBackendJson,
} from "@/src/lib/bff-response";
import { OutreachCompanyTier } from "@/src/lib/types";

export const dynamic = "force-dynamic";

/**
 * Real backend contract (backend/app/modules/outreach/router.py::get_company_tier /
 * set_company_tier, backed by schemas.py::CompanyTierResponse/SetCompanyTierRequest):
 * `company_name` + `tier` are required, `notes` is optional. `GET` returns `null`
 * (200, not a 404) when the employer has no tier set yet — the backend router itself
 * returns `None` in that case, so there's no error branch to special-case here.
 */
interface RawCompanyTierResponse {
  company_name: string;
  tier: OutreachCompanyTier["tier"];
  notes: string | null;
  updated_at: string;
}

function adaptCompanyTier(raw: RawCompanyTierResponse | null): OutreachCompanyTier | null {
  if (raw === null) return null;
  return {
    companyName: raw.company_name,
    tier: raw.tier,
    notes: raw.notes,
    updatedAt: raw.updated_at,
  };
}

export async function GET(request: NextRequest) {
  const companyName = request.nextUrl.searchParams.get("companyName");
  if (!companyName || !companyName.trim()) {
    return bffValidationError("companyName is required.");
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(
      `/api/outreach/company-tier?company_name=${encodeURIComponent(companyName)}`,
    );
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, adaptCompanyTier);
}

export async function PUT(request: NextRequest) {
  const body = await request.json();

  if (typeof body?.companyName !== "string" || !body.companyName.trim()) {
    return bffValidationError("companyName is required.");
  }
  if (typeof body?.tier !== "string" || !body.tier.trim()) {
    return bffValidationError("tier is required.");
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/outreach/company-tier", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        company_name: body.companyName,
        tier: body.tier,
        notes: body.notes ?? null,
      }),
    });
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, adaptCompanyTier);
}
