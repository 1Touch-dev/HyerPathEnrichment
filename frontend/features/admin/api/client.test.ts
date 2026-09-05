import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  decideReviewQueueItem,
  moderateDocument,
  moderateJobPosting,
  moderateOutreachMessage,
  moderatePortfolioProfile,
  updateUserStatus,
} from "./client";

function okJson(data: unknown): Response {
  return new Response(JSON.stringify({ success: true, data }), { status: 200 });
}

describe("admin client idempotency headers", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("adds Idempotency-Key to status and moderation mutations", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(okJson({}))
      .mockResolvedValueOnce(okJson({ id: "job-1" }))
      .mockResolvedValueOnce(okJson({}))
      .mockResolvedValueOnce(okJson({ profile_id: "profile-1" }))
      .mockResolvedValueOnce(okJson({ id: "queue-1" }))
      .mockResolvedValueOnce(okJson({ id: "doc-1" }));
    vi.stubGlobal("fetch", fetchMock);

    await updateUserStatus("user-1", false, "suspended");
    await moderateJobPosting("job-1", "hidden", "spam");
    await moderateOutreachMessage("message-1", true, "policy");
    await moderatePortfolioProfile("profile-1", true, "policy");
    await decideReviewQueueItem("queue-1", "approved", "looks fine");
    await moderateDocument("doc-1", "soft_delete", "policy");

    const calls = fetchMock.mock.calls.map(([, init]) => init as RequestInit);
    for (const call of calls) {
      const headers = call.headers as Record<string, string>;
      expect(headers["Idempotency-Key"]).toBeTruthy();
    }
  });
});
