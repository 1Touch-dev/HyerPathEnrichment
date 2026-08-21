import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { ScheduleInterviewDialog } from "./ScheduleInterviewDialog";
import * as client from "../api/client";
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
  notes: null,
  icsDownloadUrl: "/api/interviews/matches/m1/schedule.ics",
  googleCalendarLink: "https://calendar.google.com/calendar/render?action=TEMPLATE",
  createdAt: "2026-08-20T00:00:00Z",
};

describe("ScheduleInterviewDialog", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(client, "scheduleInterview").mockResolvedValue(sampleSchedule);
  });

  it("renders the dialog form fields when open", () => {
    render(<ScheduleInterviewDialog matchId="m1" open={true} onOpenChange={() => {}} />, {
      wrapper,
    });

    expect(screen.getByLabelText("Date & time")).toBeInTheDocument();
    expect(screen.getByLabelText("Duration (minutes)")).toBeInTheDocument();
    expect(screen.getByLabelText("Notes")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Schedule interview" })).toBeInTheDocument();
  });

  it("does not render dialog content when closed", () => {
    render(<ScheduleInterviewDialog matchId="m1" open={false} onOpenChange={() => {}} />, {
      wrapper,
    });

    expect(screen.queryByLabelText("Date & time")).not.toBeInTheDocument();
  });

  it("shows a validation error when submitted with no date/time chosen", () => {
    render(<ScheduleInterviewDialog matchId="m1" open={true} onOpenChange={() => {}} />, {
      wrapper,
    });

    fireEvent.click(screen.getByRole("button", { name: "Schedule interview" }));

    expect(screen.getByText("Date and time are required.")).toBeInTheDocument();
    expect(client.scheduleInterview).not.toHaveBeenCalled();
  });

  it("converts the picked local datetime to a UTC ISO string before submitting", async () => {
    render(<ScheduleInterviewDialog matchId="m1" open={true} onOpenChange={() => {}} />, {
      wrapper,
    });

    fireEvent.change(screen.getByLabelText("Date & time"), {
      target: { value: "2026-09-01T10:00" },
    });
    fireEvent.change(screen.getByLabelText("Duration (minutes)"), {
      target: { value: "45" },
    });
    fireEvent.change(screen.getByLabelText("Notes"), {
      target: { value: "Bring resume" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Schedule interview" }));

    await waitFor(() => expect(client.scheduleInterview).toHaveBeenCalledTimes(1));

    const [matchId, input] = (client.scheduleInterview as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(matchId).toBe("m1");
    expect(input.scheduledAt).toBe(new Date("2026-09-01T10:00").toISOString());
    expect(input.durationMinutes).toBe(45);
    expect(input.notes).toBe("Bring resume");
  });

  it("calls onOpenChange(false) after a successful submission", async () => {
    const onOpenChange = vi.fn();
    render(<ScheduleInterviewDialog matchId="m1" open={true} onOpenChange={onOpenChange} />, {
      wrapper,
    });

    fireEvent.change(screen.getByLabelText("Date & time"), {
      target: { value: "2026-09-01T10:00" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Schedule interview" }));

    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });
});
