import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import type { UseQueryResult } from "@tanstack/react-query";
import { InterviewScheduleCard } from "./InterviewScheduleCard";
import * as useInterviewScheduleHooks from "../hooks/useInterviewSchedule";
import * as useCancelInterviewHooks from "../hooks/useCancelInterview";
import type { InterviewSchedule } from "@/src/lib/types";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const sampleSchedule: InterviewSchedule = {
  id: "sched1",
  jobMatchId: "m1",
  scheduledAt: "2026-09-01T14:00:00Z",
  durationMinutes: 60,
  notes: "Bring resume",
  icsDownloadUrl: "/api/interviews/matches/m1/schedule.ics",
  googleCalendarLink: "https://calendar.google.com/calendar/render?action=TEMPLATE",
  createdAt: "2026-08-20T00:00:00Z",
};

const cancelMutateMock = vi.fn();

function mockUseInterviewSchedule(
  overrides: Partial<UseQueryResult<InterviewSchedule | null>> = {},
) {
  vi.spyOn(useInterviewScheduleHooks, "useInterviewSchedule").mockReturnValue({
    data: undefined,
    isLoading: false,
    isError: false,
    ...overrides,
  } as UseQueryResult<InterviewSchedule | null>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  cancelMutateMock.mockReset();
  vi.spyOn(useCancelInterviewHooks, "useCancelInterview").mockReturnValue({
    mutate: cancelMutateMock,
    isPending: false,
  } as unknown as ReturnType<typeof useCancelInterviewHooks.useCancelInterview>);
});

describe("InterviewScheduleCard", () => {
  it("renders a skeleton while loading", () => {
    mockUseInterviewSchedule({ isLoading: true });
    const { container } = render(<InterviewScheduleCard matchId="m1" />, { wrapper });
    expect(container.querySelector(".animate-pulse")).toBeTruthy();
  });

  it("renders an inline error with no retry button on failure", () => {
    mockUseInterviewSchedule({ isError: true });
    render(<InterviewScheduleCard matchId="m1" />, { wrapper });
    expect(screen.getByRole("alert")).toHaveTextContent(/Couldn't load the interview schedule/);
    expect(screen.queryByRole("button", { name: /retry/i })).not.toBeInTheDocument();
  });

  it('renders a "Schedule interview" CTA instead of the card when the schedule is null', () => {
    mockUseInterviewSchedule({ data: null });
    render(<InterviewScheduleCard matchId="m1" />, { wrapper });
    expect(screen.getByRole("button", { name: "Schedule interview" })).toBeInTheDocument();
    expect(screen.queryByText("Interview scheduled")).not.toBeInTheDocument();
  });

  it("renders both calendar-add affordances (.ics download and Google Calendar link)", () => {
    mockUseInterviewSchedule({ data: sampleSchedule });
    render(<InterviewScheduleCard matchId="m1" />, { wrapper });

    const icsLink = screen.getByRole("link", { name: /Add to Calendar \(\.ics\)/ });
    expect(icsLink).toHaveAttribute("href", sampleSchedule.icsDownloadUrl);

    const googleLink = screen.getByRole("link", { name: /Google Calendar/ });
    expect(googleLink).toHaveAttribute("href", sampleSchedule.googleCalendarLink);
  });

  it('renders a "Practice for this interview" link with the correct ?jobMatchId= query param', () => {
    mockUseInterviewSchedule({ data: sampleSchedule });
    render(<InterviewScheduleCard matchId="m1" />, { wrapper });

    const practiceLink = screen.getByRole("link", { name: "Practice for this interview" });
    expect(practiceLink).toHaveAttribute("href", "/app/practice?jobMatchId=m1");
  });

  it("wires the Cancel button to useCancelInterview", () => {
    mockUseInterviewSchedule({ data: sampleSchedule });
    render(<InterviewScheduleCard matchId="m1" />, { wrapper });

    screen.getByRole("button", { name: "Cancel" }).click();
    expect(cancelMutateMock).toHaveBeenCalledTimes(1);
  });

  it("renders the formatted local date/time and notes", () => {
    mockUseInterviewSchedule({ data: sampleSchedule });
    render(<InterviewScheduleCard matchId="m1" />, { wrapper });

    const expected = new Date(sampleSchedule.scheduledAt).toLocaleString(undefined, {
      dateStyle: "full",
      timeStyle: "short",
    });
    expect(screen.getByText(expected)).toBeInTheDocument();
    expect(screen.getByText("Bring resume")).toBeInTheDocument();
  });
});
