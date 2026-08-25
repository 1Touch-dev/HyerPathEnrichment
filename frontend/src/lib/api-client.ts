import {
  ApiError,
  isErrorEnvelope,
  isSuccessEnvelope,
  parseEnvelopeError,
  SuccessEnvelope,
} from "@/src/lib/api-envelope";
import {
  AudioRecordingStatus,
  AudioUploadResult,
  CvChatSession,
  CvCompleteness,
  CvFeedbackReport,
  DocumentJobStatus,
  DocumentSummary,
  DsarInput,
  DsarResponse,
  EnrichmentInput,
  EnrichmentJob,
  EnrichMode,
  HealthStatus,
  JobListResponse,
  OptOutInput,
  OutreachListResponse,
  OutreachDraftAccepted,
  OutreachMessage,
  OutreachMessageType,
  PortfolioItem,
  PortfolioProfile,
  PracticeAttempt,
  PracticeSession,
  PracticeSessionListResult,
  PublicPortfolioProfile,
  QuestionListResult,
  SignalListResponse,
  SwipeDeck,
  SwipeDirection,
} from "@/src/lib/types";

async function parseJsonBody(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

// Single-flight pattern: ensure only one refresh happens at a time
let refreshPromise: Promise<boolean> | null = null;

/**
 * Refresh access token using refresh token cookie.
 * Uses single-flight pattern to prevent concurrent refresh attempts.
 */
async function refreshAccessToken(): Promise<boolean> {
  // If refresh already in progress, wait for it
  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = (async () => {
    try {
      const response = await fetch("/api/auth/refresh", {
        method: "POST",
        credentials: "include",
      });
      return response.ok;
    } catch (error) {
      console.error("Token refresh failed:", error);
      return false;
    } finally {
      // Clear promise after completion
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

/**
 * Client-side fetch with automatic token refresh on 401.
 * Always includes credentials for cookie-based auth.
 */
async function request<T>(path: string, init?: RequestInit): Promise<SuccessEnvelope<T>> {
  // First attempt with current credentials
  let response = await fetch(path, {
    ...init,
    cache: "no-store",
    credentials: "include", // Always include cookies
  });

  // If 401, try to refresh token and retry
  if (response.status === 401) {
    // Try to refresh token
    const refreshed = await refreshAccessToken();

    if (refreshed) {
      // Retry the original request with new token
      response = await fetch(path, {
        ...init,
        cache: "no-store",
        credentials: "include",
      });
    } else {
      // Refresh failed, redirect to login
      if (typeof window !== "undefined") {
        window.location.href = "/login?session_expired=true";
      }
      throw new ApiError("Session expired", {
        code: "UNAUTHORIZED",
        statusCode: 401,
      });
    }
  }

  const body = await parseJsonBody(response);

  if (!response.ok || isErrorEnvelope(body)) {
    throw parseEnvelopeError(body, response.status);
  }

  if (!isSuccessEnvelope(body)) {
    throw new ApiError("Invalid API response shape", {
      code: "INTERNAL_ERROR",
      statusCode: response.status || 500,
    });
  }

  return body as SuccessEnvelope<T>;
}

export async function requestData<T>(path: string, init?: RequestInit): Promise<T> {
  const envelope = await request<T>(path, init);
  return envelope.data;
}

export async function createEnrichmentJob(
  input: EnrichmentInput,
  mode: EnrichMode,
): Promise<SuccessEnvelope<EnrichmentJob>> {
  const path = mode === "sync" ? "/api/enrich/sync" : "/api/enrich";
  return request<EnrichmentJob>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function getEnrichmentJob(id: string): Promise<SuccessEnvelope<EnrichmentJob>> {
  return request<EnrichmentJob>(`/api/enrich/${id}`);
}

export async function listEnrichmentJobs(
  params: { limit?: number; offset?: number } = {},
): Promise<SuccessEnvelope<JobListResponse>> {
  const search = new URLSearchParams();
  if (params.limit !== undefined) search.set("limit", String(params.limit));
  if (params.offset !== undefined) search.set("offset", String(params.offset));

  const query = search.toString();
  return request<JobListResponse>(`/api/enrich/jobs${query ? `?${query}` : ""}`);
}

export async function submitOptOut(
  payload: OptOutInput,
): Promise<SuccessEnvelope<{ status: "accepted" }>> {
  return request<{ status: "accepted" }>("/api/opt-out", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function submitDsar(payload: DsarInput): Promise<SuccessEnvelope<DsarResponse>> {
  return request<DsarResponse>("/api/dsar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function listSignals(
  params: { limit?: number; offset?: number } = {},
): Promise<SuccessEnvelope<SignalListResponse>> {
  const search = new URLSearchParams();
  if (params.limit !== undefined) search.set("limit", String(params.limit));
  if (params.offset !== undefined) search.set("offset", String(params.offset));

  const query = search.toString();
  return request<SignalListResponse>(`/api/signals${query ? `?${query}` : ""}`);
}

export async function getHealth(): Promise<SuccessEnvelope<HealthStatus>> {
  return request<HealthStatus>("/api/health");
}

// Module 2: Tinder-Style Job Board + CV Management (phase2_module2.md §12.2)
// Snake_case→camelCase adaptation already happens inside the BFF routes
// (§11.4-11.7), so these functions only need the frontend-shaped types.

// ── CV completeness + chat + feedback ──────────────────────────────

export async function fetchCvCompleteness(
  documentId: string,
): Promise<SuccessEnvelope<CvCompleteness>> {
  return request<CvCompleteness>(`/api/documents/${documentId}/completeness`);
}

export async function startCvChatSession(
  documentId: string,
): Promise<SuccessEnvelope<CvChatSession>> {
  return request<CvChatSession>(`/api/documents/${documentId}/cv-chat/sessions`, {
    method: "POST",
  });
}

export async function getCvChatSession(sessionId: string): Promise<SuccessEnvelope<CvChatSession>> {
  return request<CvChatSession>(`/api/cv-chat/sessions/${sessionId}`);
}

export async function postCvChatMessage(
  sessionId: string,
  content: string,
): Promise<SuccessEnvelope<CvChatSession>> {
  return request<CvChatSession>(`/api/cv-chat/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
}

export async function requestCvFeedback(
  documentId: string,
  targetRole?: string,
): Promise<SuccessEnvelope<{ jobId: string }>> {
  return request<{ jobId: string }>(`/api/documents/${documentId}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ targetRole: targetRole ?? null }),
  });
}

export async function fetchCvFeedback(
  documentId: string,
): Promise<SuccessEnvelope<CvFeedbackReport>> {
  return request<CvFeedbackReport>(`/api/documents/${documentId}/feedback`);
}

/**
 * Polls the real job-status endpoint (`GET /api/documents/jobs/{job_id}` — backend's
 * `JobStatusResponse`) for the async CV-feedback-generation job enqueued by
 * `requestCvFeedback`. There is no interim "pending" `CvFeedbackReport` row (see
 * backend/app/workers/tasks/cv_improvement.py), so this job record is the only real
 * signal that generation is still running vs. done vs. failed.
 */
export async function fetchDocumentJobStatus(
  jobId: string,
): Promise<SuccessEnvelope<DocumentJobStatus>> {
  return request<DocumentJobStatus>(`/api/documents/jobs/${jobId}`);
}

export async function fetchDocuments(): Promise<SuccessEnvelope<DocumentSummary[]>> {
  return request<DocumentSummary[]>("/api/documents");
}

export async function acceptCvBullet(
  documentId: string,
  reportId: string,
  bulletIndex: number,
): Promise<SuccessEnvelope<{ accepted: boolean }>> {
  return request<{ accepted: boolean }>(`/api/cv-feedback/${reportId}/accept-bullet`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ documentId, bulletIndex }),
  });
}

// ── Portfolio ───────────────────────────────────────────────────────

export async function fetchPortfolioProfile(): Promise<SuccessEnvelope<PortfolioProfile>> {
  return request<PortfolioProfile>("/api/portfolio/profile");
}

export async function savePortfolioProfile(
  payload: Partial<PortfolioProfile> & { slug: string },
): Promise<SuccessEnvelope<PortfolioProfile>> {
  return request<PortfolioProfile>("/api/portfolio/profile", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function addPortfolioItem(
  payload: Omit<PortfolioItem, "itemId" | "displayOrder">,
): Promise<SuccessEnvelope<PortfolioItem>> {
  return request<PortfolioItem>("/api/portfolio/items", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deletePortfolioItem(
  itemId: string,
): Promise<SuccessEnvelope<{ deleted: boolean }>> {
  return request<{ deleted: boolean }>(`/api/portfolio/items/${itemId}`, { method: "DELETE" });
}

/** Public — no auth cookie needed, but still routed through the BFF (§11.5) for consistency. */
export async function fetchPublicPortfolio(
  slug: string,
): Promise<SuccessEnvelope<PublicPortfolioProfile>> {
  return request<PublicPortfolioProfile>(`/api/portfolio/public/${slug}`);
}

// ── Job swipe ───────────────────────────────────────────────────────

export async function fetchSwipeDeck(): Promise<SuccessEnvelope<SwipeDeck>> {
  return request<SwipeDeck>("/api/matches/swipe-deck");
}

export async function submitSwipe(
  matchId: string,
  direction: SwipeDirection,
): Promise<SuccessEnvelope<{ direction: SwipeDirection }>> {
  return request<{ direction: SwipeDirection }>(`/api/matches/${matchId}/swipe`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ direction }),
  });
}

// ── Outreach ────────────────────────────────────────────────────────

export async function fetchOutreachMessages(): Promise<SuccessEnvelope<OutreachListResponse>> {
  return request<OutreachListResponse>("/api/outreach");
}

export async function draftOutreach(payload: {
  companyName: string;
  documentId: string;
  recipientRoleTitle?: string;
  jobMatchId?: string;
  jobDescription?: string;
  messageType?: OutreachMessageType;
  customInstruction?: string;
}): Promise<SuccessEnvelope<OutreachDraftAccepted>> {
  return request<OutreachDraftAccepted>("/api/outreach/drafts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      companyName: payload.companyName,
      documentId: payload.documentId,
      recipientRoleTitle: payload.recipientRoleTitle ?? null,
      jobMatchId: payload.jobMatchId ?? null,
      jobDescription: payload.jobDescription ?? null,
      // Module 4, Module G (§11.7): forwarded to the BFF route, which maps these
      // to the backend's snake_case `message_type`/`custom_instruction` fields.
      messageType: payload.messageType ?? "email",
      customInstruction: payload.customInstruction ?? null,
    }),
  });
}

export async function editOutreachDraft(
  messageId: string,
  subject: string,
  body: string,
): Promise<SuccessEnvelope<OutreachMessage>> {
  return request<OutreachMessage>(`/api/outreach/${messageId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ subject, body }),
  });
}

export async function sendOutreach(messageId: string): Promise<SuccessEnvelope<OutreachMessage>> {
  return request<OutreachMessage>(`/api/outreach/${messageId}/send`, { method: "POST" });
}

// Module 3: Interview Prep (phase2_module3.md §10.4)
// Snake_case→camelCase adaptation already happens inside the BFF routes (§10.3),
// so these functions only need the frontend-shaped types.

export async function createPracticeSession(
  sessionType: string,
  metadata?: Record<string, unknown>,
): Promise<SuccessEnvelope<PracticeSession>> {
  return request<PracticeSession>("/api/practice/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_type: sessionType, session_metadata: metadata ?? {} }),
  });
}

export async function listPracticeSessions(
  params: { limit?: number; offset?: number } = {},
): Promise<SuccessEnvelope<PracticeSessionListResult>> {
  const search = new URLSearchParams();
  if (params.limit !== undefined) search.set("limit", String(params.limit));
  if (params.offset !== undefined) search.set("offset", String(params.offset));

  const query = search.toString();
  return request<PracticeSessionListResult>(`/api/practice/sessions${query ? `?${query}` : ""}`);
}

export async function getPracticeSession(id: string): Promise<SuccessEnvelope<PracticeSession>> {
  return request<PracticeSession>(`/api/practice/sessions/${id}`);
}

/**
 * Sent as snake_case to match the backend's `QuestionAttemptRequest`
 * (backend/app/modules/sessions/schemas.py) — this request body is proxied through as-is
 * by the BFF route (§10.3's `[id]/attempts/route.ts`), not passed through a `toBackend*`
 * adapter helper, since none exists for this shape in `api-adapter.ts`.
 */
export async function addPracticeAttempt(
  sessionId: string,
  payload: {
    questionId?: string;
    responseType: "text" | "audio";
    textResponse?: string;
    audioRecordingId?: string;
    timeTakenSeconds?: number;
  },
): Promise<SuccessEnvelope<PracticeAttempt>> {
  return request<PracticeAttempt>(`/api/practice/sessions/${sessionId}/attempts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question_id: payload.questionId ?? null,
      response_type: payload.responseType,
      text_response: payload.textResponse ?? null,
      audio_recording_id: payload.audioRecordingId ?? null,
      time_taken_seconds: payload.timeTakenSeconds ?? null,
    }),
  });
}

export async function fetchQuestions(payload: {
  jobRole: string;
  count?: number;
  category?: string;
  difficulty?: string;
  personalize?: boolean;
  documentId?: string;
}): Promise<SuccessEnvelope<QuestionListResult>> {
  return request<QuestionListResult>("/api/practice/questions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      job_role: payload.jobRole,
      count: payload.count,
      category: payload.category ?? undefined,
      difficulty: payload.difficulty ?? undefined,
      personalize: payload.personalize ?? undefined,
      document_id: payload.documentId ?? undefined,
    }),
  });
}

/**
 * Multipart upload — deliberately does not go through the shared `request()` helper's
 * usual JSON body pattern, since `FormData` needs the browser to set its own
 * `Content-Type: multipart/form-data; boundary=...` header. `request()` never forces a
 * JSON content-type itself (callers set that header explicitly), so it is reused here
 * unchanged; this function just omits the header and passes `FormData` as the body.
 */
export async function uploadPracticeAudio(
  practiceSessionId: string,
  audioFormat: string,
  file: Blob,
  filename: string,
): Promise<SuccessEnvelope<AudioUploadResult>> {
  const formData = new FormData();
  formData.set("practice_session_id", practiceSessionId);
  formData.set("audio_format", audioFormat);
  formData.set("file", file, filename);

  return request<AudioUploadResult>("/api/practice/audio", {
    method: "POST",
    body: formData,
  });
}

export async function getPracticeAudioStatus(
  id: string,
): Promise<SuccessEnvelope<AudioRecordingStatus>> {
  return request<AudioRecordingStatus>(`/api/practice/audio/${id}`);
}
