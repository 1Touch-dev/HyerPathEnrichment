import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { OutreachModerationPanel } from "./OutreachModerationPanel";
import * as useOutreachModerationHooks from "../hooks/useOutreachModeration";
import type { AdminOutreachMessage, AdminOutreachMessageListResponse } from "@/src/lib/types";
import type { UseQueryResult } from "@tanstack/react-query";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const baseMessage: AdminOutreachMessage = {
  id: "m1",
  userId: "u1",
  jobMatchId: "jm1",
  recipientRoleTitle: "Hiring Manager",
  companyName: "Acme Corp",
  subject: "Interested in the Backend Engineer role",
  body: "Hello, I would love to discuss the role.",
  status: "sent",
  adminBlocked: false,
  sentAt: "2026-01-01T00:00:00Z",
  createdAt: "2026-01-01T00:00:00Z",
};

const sampleList: AdminOutreachMessageListResponse = {
  items: [baseMessage],
  nextCursor: null,
  hasMore: false,
};

function mockUseAdminOutreachMessages(
  overrides: Partial<UseQueryResult<AdminOutreachMessageListResponse>> = {},
) {
  vi.spyOn(useOutreachModerationHooks, "useAdminOutreachMessages").mockReturnValue({
    data: sampleList,
    isLoading: false,
    ...overrides,
  } as UseQueryResult<AdminOutreachMessageListResponse>);
}

const moderateMutate = vi.fn();

function mockModerate(
  overrides: Partial<ReturnType<typeof useOutreachModerationHooks.useModerateOutreachMessage>> = {},
) {
  vi.spyOn(useOutreachModerationHooks, "useModerateOutreachMessage").mockReturnValue({
    mutate: moderateMutate,
    isPending: false,
    ...overrides,
  } as unknown as ReturnType<typeof useOutreachModerationHooks.useModerateOutreachMessage>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  moderateMutate.mockReset();
  mockUseAdminOutreachMessages();
  mockModerate();
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

describe("OutreachModerationPanel", () => {
  it("renders a row per message with company, subject, status, and moderation badges", () => {
    render(<OutreachModerationPanel />, { wrapper });
    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("Interested in the Backend Engineer role")).toBeInTheDocument();
    expect(screen.getByText("sent")).toBeInTheDocument();
    expect(screen.getByText("Allowed")).toBeInTheDocument();
  });

  it("renders an empty state when there are no outreach messages", () => {
    mockUseAdminOutreachMessages({ data: { items: [], nextCursor: null, hasMore: false } });
    render(<OutreachModerationPanel />, { wrapper });
    expect(screen.getByText("No outreach messages found")).toBeInTheDocument();
  });

  it("calls useModerateOutreachMessage when Block is clicked, after confirmation", () => {
    render(<OutreachModerationPanel />, { wrapper });
    fireEvent.click(screen.getByText("Block"));
    expect(moderateMutate).toHaveBeenCalledWith({ id: "m1", adminBlocked: true });
  });

  it("does not call useModerateOutreachMessage when the confirmation is declined", () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<OutreachModerationPanel />, { wrapper });
    fireEvent.click(screen.getByText("Block"));
    expect(moderateMutate).not.toHaveBeenCalled();
  });

  it("shows Unblock and calls the mutation with adminBlocked: false for already-blocked messages", () => {
    mockUseAdminOutreachMessages({
      data: { items: [{ ...baseMessage, adminBlocked: true }], nextCursor: null, hasMore: false },
    });
    render(<OutreachModerationPanel />, { wrapper });
    expect(screen.getByText("Blocked")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Unblock"));
    expect(moderateMutate).toHaveBeenCalledWith({ id: "m1", adminBlocked: false });
  });

  it("disables the Next page button when hasMore is false", () => {
    render(<OutreachModerationPanel />, { wrapper });
    expect(screen.getByText("Next page")).toBeDisabled();
  });

  it("enables the Next page button when hasMore is true", () => {
    mockUseAdminOutreachMessages({
      data: { items: [baseMessage], nextCursor: "cursor2", hasMore: true },
    });
    render(<OutreachModerationPanel />, { wrapper });
    expect(screen.getByText("Next page")).not.toBeDisabled();
  });
});
