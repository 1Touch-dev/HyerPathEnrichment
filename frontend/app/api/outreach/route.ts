import { adaptOutreachMessage } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import { bffServiceUnavailable, handleBackendJson } from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

export async function GET() {
  let backendResponse: Response;
  try {
    backendResponse = await backendFetch("/api/outreach");
  } catch {
    return bffServiceUnavailable();
  }
  return handleBackendJson(backendResponse, (raw: { messages: Parameters<typeof adaptOutreachMessage>[0][] }) => ({
    messages: raw.messages.map(adaptOutreachMessage),
  }));
}
