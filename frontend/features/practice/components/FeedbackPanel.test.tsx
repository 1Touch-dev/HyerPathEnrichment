import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { PracticeAttempt } from "@/src/lib/types";
import { FeedbackPanel } from "./FeedbackPanel";

function attempt(overrides: Partial<PracticeAttempt> = {}): PracticeAttempt {
  return {
    id: "attempt-1",
    sessionId: "session-1",
    userId: "user-1",
    questionId: "q1",
    questionText: "Tell me about a project.",
    responseType: "text",
    textResponse: "I led the API rewrite.",
    audioRecordingId: null,
    aiScore: null,
    scoreBreakdown: null,
    aiFeedback: null,
    timeTakenSeconds: null,
    attemptedAt: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("FeedbackPanel", () => {
  it("shows Pending while a score is still expected", () => {
    render(<FeedbackPanel attempt={attempt()} />);
    expect(screen.getByText("Pending...")).toBeInTheDocument();
  });

  it("shows the score when scoring finished", () => {
    render(<FeedbackPanel attempt={attempt({ aiScore: 8, aiFeedback: "Clear answer." })} />);
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.queryByText("Pending...")).not.toBeInTheDocument();
  });

  it("does not stay on Pending when scoring failed", () => {
    render(
      <FeedbackPanel
        attempt={attempt({ aiScore: null, aiFeedback: "Scoring failed for this answer." })}
      />,
    );
    expect(screen.getByText("Not scored")).toBeInTheDocument();
    expect(screen.getByText("Scoring failed for this answer.")).toBeInTheDocument();
    expect(screen.queryByText("Pending...")).not.toBeInTheDocument();
  });
});
