import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdminStaffInvitesPage from "./page";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

describe("AdminStaffInvitesPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.stubGlobal("fetch", vi.fn());
  });

  it("collects confirmation email, MFA, and locked recruiter role before posting", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        success: true,
        data: {
          id: "invite-1",
          email: "teammate@example.com",
          role_name: "recruiter",
          expires_at: "2026-10-20T00:00:00.000Z",
          accepted_at: null,
          invite_token: "plain-token",
        },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<AdminStaffInvitesPage />, { wrapper });
    fireEvent.click(screen.getByRole("button", { name: "Invite staff member" }));

    expect(screen.getByLabelText("Role name")).toHaveValue("recruiter");
    expect(screen.getByLabelText("Role name")).toBeDisabled();

    const send = screen.getByRole("button", { name: "Send invite" });
    expect(send).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "teammate@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Confirm email"), {
      target: { value: "teammate@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Your 2FA code"), {
      target: { value: "123456" },
    });

    expect(send).toBeEnabled();
    fireEvent.click(send);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/admin/staff-invites");
    expect(init.method).toBe("POST");
    const headers = init.headers as Record<string, string>;
    expect(headers["Idempotency-Key"]).toMatch(/^staff-invite:/);
    expect(JSON.parse(String(init.body))).toEqual({
      email: "teammate@example.com",
      confirmation_email: "teammate@example.com",
      mfa_code: "123456",
      role_name: "recruiter",
    });

    await waitFor(() => {
      expect(screen.getByText("teammate@example.com")).toBeInTheDocument();
    });
    expect(screen.getByText("Invite path: /invite/plain-token")).toBeInTheDocument();
  });

  it("keeps send disabled when confirmation email does not match", () => {
    render(<AdminStaffInvitesPage />, { wrapper });
    fireEvent.click(screen.getByRole("button", { name: "Invite staff member" }));
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "teammate@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Confirm email"), {
      target: { value: "other@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Your 2FA code"), {
      target: { value: "123456" },
    });
    expect(screen.getByRole("button", { name: "Send invite" })).toBeDisabled();
    expect(vi.mocked(fetch)).not.toHaveBeenCalled();
  });
});
