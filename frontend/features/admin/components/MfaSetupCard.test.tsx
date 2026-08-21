import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { MfaSetupCard } from "./MfaSetupCard";
import * as useMfaSetupHooks from "../hooks/useMfaSetup";
import type { MfaEnrollResult, MfaStatus } from "@/src/lib/types";
import type { UseQueryResult } from "@tanstack/react-query";

type EnrollMfaResult = ReturnType<typeof useMfaSetupHooks.useEnrollMfa>;
type ConfirmMfaResult = ReturnType<typeof useMfaSetupHooks.useConfirmMfaEnrollment>;
type DisableMfaResult = ReturnType<typeof useMfaSetupHooks.useDisableMfa>;

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const disabledStatus: MfaStatus = { mfaEnabled: false, mfaEnrolledAt: null };
const enabledStatus: MfaStatus = { mfaEnabled: true, mfaEnrolledAt: "2026-01-01T00:00:00Z" };
const enrollResult: MfaEnrollResult = {
  secret: "SECRET123",
  provisioningUri: "otpauth://totp/Hyrepath:user@example.com?secret=SECRET123",
};

const enrollMutateAsync = vi.fn();
const confirmMutateAsync = vi.fn();
const disableMutateAsync = vi.fn();

function mockUseMfaStatus(overrides: Partial<UseQueryResult<MfaStatus>> = {}) {
  vi.spyOn(useMfaSetupHooks, "useMfaStatus").mockReturnValue({
    data: disabledStatus,
    isLoading: false,
    ...overrides,
  } as UseQueryResult<MfaStatus>);
}

function mockUseEnrollMfa(overrides: Partial<EnrollMfaResult> = {}) {
  vi.spyOn(useMfaSetupHooks, "useEnrollMfa").mockReturnValue({
    mutateAsync: enrollMutateAsync,
    data: undefined,
    isPending: false,
    ...overrides,
  } as unknown as EnrollMfaResult);
}

function mockUseConfirmMfaEnrollment(overrides: Partial<ConfirmMfaResult> = {}) {
  vi.spyOn(useMfaSetupHooks, "useConfirmMfaEnrollment").mockReturnValue({
    mutateAsync: confirmMutateAsync,
    isPending: false,
    ...overrides,
  } as unknown as ConfirmMfaResult);
}

function mockUseDisableMfa(overrides: Partial<DisableMfaResult> = {}) {
  vi.spyOn(useMfaSetupHooks, "useDisableMfa").mockReturnValue({
    mutateAsync: disableMutateAsync,
    isPending: false,
    ...overrides,
  } as unknown as DisableMfaResult);
}

beforeEach(() => {
  vi.restoreAllMocks();
  enrollMutateAsync.mockReset().mockResolvedValue(enrollResult);
  confirmMutateAsync.mockReset().mockResolvedValue(undefined);
  disableMutateAsync.mockReset().mockResolvedValue(undefined);
  mockUseMfaStatus();
  mockUseEnrollMfa();
  mockUseConfirmMfaEnrollment();
  mockUseDisableMfa();
});

describe("MfaSetupCard", () => {
  it("shows an Enable 2FA button when MFA is not enabled and enrollment hasn't started", () => {
    render(<MfaSetupCard />, { wrapper });
    expect(screen.getByText("Enable 2FA")).toBeInTheDocument();
  });

  it("shows the Disable 2FA button and enrollment date when MFA is already enabled", () => {
    mockUseMfaStatus({ data: enabledStatus });
    render(<MfaSetupCard />, { wrapper });
    expect(screen.getByText("2FA is enabled")).toBeInTheDocument();
    expect(screen.getByText("Disable 2FA")).toBeInTheDocument();
  });

  it("starts enrollment when Enable 2FA is clicked", async () => {
    render(<MfaSetupCard />, { wrapper });
    fireEvent.click(screen.getByText("Enable 2FA"));
    await waitFor(() => expect(enrollMutateAsync).toHaveBeenCalledTimes(1));
  });

  it("shows the copyable secret and provisioning URI once enrollment has started", () => {
    mockUseEnrollMfa({ data: enrollResult } as Partial<EnrollMfaResult>);
    render(<MfaSetupCard />, { wrapper });
    expect(screen.getByDisplayValue("SECRET123")).toBeInTheDocument();
    expect(screen.getByText(enrollResult.provisioningUri)).toBeInTheDocument();
  });

  it("submits the 6-digit code to confirm enrollment", async () => {
    mockUseEnrollMfa({ data: enrollResult } as Partial<EnrollMfaResult>);
    render(<MfaSetupCard />, { wrapper });

    fireEvent.change(screen.getByLabelText("6-digit code"), { target: { value: "123456" } });
    const form = screen.getByLabelText("6-digit code").closest("form");
    expect(form).not.toBeNull();
    form!.requestSubmit();

    await waitFor(() => expect(confirmMutateAsync).toHaveBeenCalledWith("123456"));
  });

  it("calls disable MFA after the user confirms the window.confirm prompt", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    mockUseMfaStatus({ data: enabledStatus });
    render(<MfaSetupCard />, { wrapper });

    fireEvent.click(screen.getByText("Disable 2FA"));
    await waitFor(() => expect(disableMutateAsync).toHaveBeenCalledTimes(1));
  });

  it("does not disable MFA when the user declines the confirmation", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    mockUseMfaStatus({ data: enabledStatus });
    render(<MfaSetupCard />, { wrapper });

    fireEvent.click(screen.getByText("Disable 2FA"));
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(disableMutateAsync).not.toHaveBeenCalled();
  });
});
