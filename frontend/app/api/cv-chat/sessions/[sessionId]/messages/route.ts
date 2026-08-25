import { NextRequest } from "next/server";
import { adaptCvChatSession } from "@/src/lib/api-adapter";
import { backendFetch } from "@/src/lib/backend-client";
import {
  bffServiceUnavailable,
  bffValidationError,
  handleBackendJson,
} from "@/src/lib/bff-response";

export const dynamic = "force-dynamic";

type RawCvChatTurnResponse = {
  session: Parameters<typeof adaptCvChatSession>[0];
};

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const { sessionId } = await params;
  const body = await request.json().catch(() => null);
  if (typeof body?.content !== "string" || !body.content.trim()) {
    return bffValidationError("Message content is required.");
  }

  let backendResponse: Response;
  try {
    backendResponse = await backendFetch(`/api/documents/cv-chat/sessions/${sessionId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: body.content }),
    });
  } catch {
    return bffServiceUnavailable();
  }
  // Backend response envelopes { session, assistant_message } — adapt just the session
  // half here; the chat UI (§12.3) re-derives the latest assistant message from
  // session.messages, so no separate adapter is needed for the turn wrapper shape.
  return handleBackendJson(backendResponse, (raw: RawCvChatTurnResponse) =>
    adaptCvChatSession(raw.session),
  );
}
