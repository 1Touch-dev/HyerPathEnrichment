import { describe, it, expect, vi, beforeEach, afterAll } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { ImpersonationBanner } from "./ImpersonationBanner";
import * as useImpersonationHooks from "../hooks/useImpersonation";
import type { ImpersonationStatus } from "@/src/lib/types";
import type { UseQueryResult } from "@tanstack/react-query";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const notImpersonating: ImpersonationStatus = {
  isImpersonating: false,
  adminUserId: null,
  adminEmail: null,
  targetUserId: null,
  expiresAt: null,
};

const impersonating: ImpersonationStatus = {
  isImpersonating: true,
  adminUserId: "admin1",
  adminEmail: "admin@example.com",
  targetUserId: "target1",
  expiresAt: "2026-01-01T01:00:00Z",
};

const endMutateAsync = vi.fn();
const assignMock = vi.fn();
const originalLocation = window.location;

// jsdom's window.location.assign is non-configurable, so it can't be spied on
// or reassigned directly; replace the whole `location` object instead.
Object.defineProperty(window, "location", {
  configurable: true,
  value: { ...originalLocation, assign: assignMock },
});

afterAll(() => {
  Object.defineProperty(window, "location", { configurable: true, value: originalLocation });
});

function mockUseImpersonationStatus(overrides: Partial<UseQueryResult<ImpersonationStatus>> = {}) {
  vi.spyOn(useImpersonationHooks, "useImpersonationStatus").mockReturnValue({
    data: notImpersonating,
    isLoading: false,
    ...overrides,
  } as UseQueryResult<ImpersonationStatus>);
}

function mockUseEndImpersonation(
  overrides: Partial<ReturnType<typeof useImpersonationHooks.useEndImpersonation>> = {},
) {
  vi.spyOn(useImpersonationHooks, "useEndImpersonation").mockReturnValue({
    mutateAsync: endMutateAsync,
    isPending: false,
    ...overrides,
  } as unknown as ReturnType<typeof useImpersonationHooks.useEndImpersonation>);
}

beforeEach(() => {
  vi.restoreAllMocks();
  endMutateAsync.mockReset().mockResolvedValue(undefined);
  assignMock.mockReset();
  mockUseImpersonationStatus();
  mockUseEndImpersonation();
});

describe("ImpersonationBanner", () => {
  it("renders nothing when not impersonating", () => {
    const { container } = render(<ImpersonationBanner />, { wrapper });
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the acting-identity banner with target and admin identities when impersonating", () => {
    mockUseImpersonationStatus({ data: impersonating });
    render(<ImpersonationBanner />, { wrapper });
    expect(screen.getByText("target1")).toBeInTheDocument();
    expect(screen.getByText(/admin@example.com/)).toBeInTheDocument();
    expect(screen.getByText("Exit impersonation")).toBeInTheDocument();
  });

  it("ends impersonation and navigates to /desk/users on success", async () => {
    mockUseImpersonationStatus({ data: impersonating });
    render(<ImpersonationBanner />, { wrapper });

    fireEvent.click(screen.getByText("Exit impersonation"));

    await waitFor(() => expect(endMutateAsync).toHaveBeenCalledTimes(1));
    expect(assignMock).toHaveBeenCalledWith("/desk/users");
  });

  it("shows an inline error and does not navigate when ending impersonation fails", async () => {
    endMutateAsync.mockRejectedValueOnce(new Error("Failed to exit impersonation."));
    mockUseImpersonationStatus({ data: impersonating });
    render(<ImpersonationBanner />, { wrapper });

    fireEvent.click(screen.getByText("Exit impersonation"));

    await waitFor(() =>
      expect(screen.getByText("(Failed to exit impersonation.)")).toBeInTheDocument(),
    );
    expect(assignMock).not.toHaveBeenCalled();
  });
});
