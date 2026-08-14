import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { QuestionCard } from "./QuestionCard";
import type { InterviewQuestion } from "@/src/lib/types";

function makeQuestion(overrides: Partial<InterviewQuestion> = {}): InterviewQuestion {
  return {
    id: "q1",
    questionText: "Describe a time you disagreed with a teammate.",
    category: "behavioral",
    difficulty: "medium",
    jobRoles: ["software_engineer"],
    technologies: [],
    isPersonalized: false,
    ...overrides,
  };
}

describe("QuestionCard", () => {
  it("renders the question text, category, and difficulty", () => {
    render(<QuestionCard question={makeQuestion()} />);
    expect(screen.getByText("Describe a time you disagreed with a teammate.")).toBeInTheDocument();
    expect(screen.getByText("behavioral")).toBeInTheDocument();
    expect(screen.getByText("medium")).toBeInTheDocument();
  });

  it("does not show a Personalized badge for a non-personalized question", () => {
    render(<QuestionCard question={makeQuestion({ isPersonalized: false })} />);
    expect(screen.queryByText("Personalized")).not.toBeInTheDocument();
  });

  it("shows a Personalized badge for a personalized question", () => {
    render(<QuestionCard question={makeQuestion({ isPersonalized: true })} />);
    expect(screen.getByText("Personalized")).toBeInTheDocument();
  });
});
