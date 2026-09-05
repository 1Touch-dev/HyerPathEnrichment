import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { JdPracticeSessionView } from "./JdPracticeSessionView";
import * as jdPracticeClient from "../api/client";
import * as practiceApiClient from "@/src/lib/api-client";
import { ApiError } from "@/src/lib/api-envelope";
import type { JdPracticeResponse } from "@/src/lib/types";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const sampleResponse: JdPracticeResponse = {
  questions: [
    {
      id: "q1",
      questionText: "Tell me about a time you optimized a slow API.",
      category: "technical",
      difficulty: "medium",
      sampleAnswer: "A strong answer covers profiling, the bottleneck, and the fix.",
    },
  ],
  jobMatchId: "match-1",
  practiceSessionId: "session-1",
};

describe("JdPracticeSessionView", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("shows a loading spinner while questions are being generated", async () => {
    let resolveRequest!: (value: JdPracticeResponse) => void;
    const pending = new Promise<JdPracticeResponse>((resolve) => {
      resolveRequest = resolve;
    });
    const requestSpy = vi
      .spyOn(jdPracticeClient, "requestJdPracticeQuestions")
      .mockReturnValue(pending);

    render(<JdPracticeSessionView jobMatchId="match-1" />, { wrapper });

    await waitFor(() => expect(requestSpy).toHaveBeenCalledTimes(1));
    expect(screen.getByText("Generating your practice questions...")).toBeInTheDocument();

    resolveRequest(sampleResponse);
    await waitFor(
      () =>
        expect(screen.queryByText("Generating your practice questions...")).not.toBeInTheDocument(),
      { timeout: 5000 },
    );
  });

  it("hides the sample answer until after the candidate submits an attempt", async () => {
    vi.spyOn(jdPracticeClient, "requestJdPracticeQuestions").mockResolvedValue(sampleResponse);
    vi.spyOn(practiceApiClient, "addPracticeAttempt").mockResolvedValue({
      success: true,
      data: {
        id: "attempt-1",
        sessionId: "session-1",
        userId: "user-1",
        questionId: null,
        questionText: null,
        responseType: "text",
        textResponse: "My answer",
        audioRecordingId: null,
        aiScore: null,
        scoreBreakdown: null,
        aiFeedback: null,
        timeTakenSeconds: null,
        attemptedAt: "2026-01-01T00:00:00Z",
      },
    });

    render(<JdPracticeSessionView jobMatchId="match-1" />, { wrapper });

    await waitFor(() =>
      expect(
        screen.getByText("Tell me about a time you optimized a slow API."),
      ).toBeInTheDocument(),
    );

    expect(
      screen.queryByText("A strong answer covers profiling, the bottleneck, and the fix."),
    ).not.toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("Type your answer..."), {
      target: { value: "I profiled the endpoint and found an N+1 query." },
    });
    fireEvent.click(screen.getByText("Submit answer"));

    await waitFor(() =>
      expect(
        screen.getByText("A strong answer covers profiling, the bottleneck, and the fix."),
      ).toBeInTheDocument(),
    );
  });

  it("shows rate-limit-specific copy when generation hits the daily limit", async () => {
    vi.spyOn(jdPracticeClient, "requestJdPracticeQuestions").mockRejectedValue(
      new ApiError("Daily JD-tailored practice question limit reached", {
        code: "RATE_LIMIT_EXCEEDED",
        statusCode: 429,
      }),
    );

    render(<JdPracticeSessionView jobMatchId="match-1" />, { wrapper });

    await waitFor(() =>
      expect(
        screen.getByText("You've hit today's practice question limit, try again tomorrow"),
      ).toBeInTheDocument(),
    );
    expect(
      screen.queryByText("Couldn't generate questions, please try again"),
    ).not.toBeInTheDocument();
  });

  it("shows generic error copy for a non-rate-limit failure", async () => {
    vi.spyOn(jdPracticeClient, "requestJdPracticeQuestions").mockRejectedValue(
      new ApiError("boom", { code: "INTERNAL_ERROR", statusCode: 500 }),
    );

    render(<JdPracticeSessionView jobMatchId="match-1" />, { wrapper });

    await waitFor(() =>
      expect(screen.getByText("Couldn't generate questions, please try again")).toBeInTheDocument(),
    );
    expect(
      screen.queryByText("You've hit today's practice question limit, try again tomorrow"),
    ).not.toBeInTheDocument();
  });
});
