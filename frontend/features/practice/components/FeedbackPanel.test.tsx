import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { FeedbackPanel } from "./FeedbackPanel";
import type { PracticeAttempt } from "@/src/lib/types";

function makeAttempt(overrides: Partial<PracticeAttempt> = {}): PracticeAttempt {
  return {
    id: "attempt-1",
    sessionId: "session-1",
    userId: "user-1",
    questionId: "q1",
    responseType: "text",
    textResponse: "My answer",
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
  it("shows a Pending state while aiScore is null", () => {
    render(<FeedbackPanel attempt={makeAttempt({ aiScore: null })} />);
    expect(screen.getByText("Pending...")).toBeInTheDocument();
  });

  it("shows the numeric score once available", () => {
    render(<FeedbackPanel attempt={makeAttempt({ aiScore: 8 })} />);
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.queryByText("Pending...")).not.toBeInTheDocument();
  });

  it("renders each scoreBreakdown entry generically, regardless of its keys", () => {
    render(
      <FeedbackPanel
        attempt={makeAttempt({
          aiScore: 7,
          scoreBreakdown: { clarity: "high", structure: 3, unexpected_field: true },
        })}
      />,
    );
    expect(screen.getByText("clarity")).toBeInTheDocument();
    expect(screen.getByText("high")).toBeInTheDocument();
    expect(screen.getByText("structure")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("unexpected_field")).toBeInTheDocument();
    expect(screen.getByText("true")).toBeInTheDocument();
  });

  it("renders aiFeedback text when present, and nothing when absent", () => {
    const { rerender } = render(
      <FeedbackPanel attempt={makeAttempt({ aiFeedback: "Great structure, be more concise." })} />,
    );
    expect(screen.getByText("Great structure, be more concise.")).toBeInTheDocument();

    rerender(<FeedbackPanel attempt={makeAttempt({ aiFeedback: null })} />);
    expect(screen.queryByText(/Great structure/)).not.toBeInTheDocument();
  });
});
