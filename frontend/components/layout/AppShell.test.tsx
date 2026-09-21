import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { AppShell } from "./AppShell";
import { useAppShellAccess } from "./app-shell-access";

const unreadMatchesMock = vi.fn(() => ({ unreadCount: 4 }));
const mutationMock = vi.fn();
const gestureMutationMock = vi.fn();
type ImpersonationQueryState = {
  data?: { isImpersonating: boolean };
  isError: boolean;
  isSuccess: boolean;
};
const impersonationStatusMock = vi.fn<() => ImpersonationQueryState>();

vi.mock("next/navigation", () => ({
  usePathname: () => "/app/matches",
}));
vi.mock("@/providers/auth-provider", () => ({
  useAuth: () => ({ user: null }),
}));
vi.mock("@/features/job-matching", () => ({
  useUnreadMatchEvents: () => unreadMatchesMock(),
}));
vi.mock("@/components/auth/verification-banner", () => ({
  VerificationBanner: () => null,
}));
vi.mock("@/features/admin", () => ({
  ImpersonationBanner: () => null,
  useImpersonationStatus: () => impersonationStatusMock(),
}));
vi.mock("./AppSidebar", () => ({
  AppSidebar: () => null,
}));
vi.mock("./AppNavRail", () => ({
  AppNavRail: () => null,
}));
vi.mock("./AppTopbar", () => ({
  AppTopbar: ({ product }: { product: string }) => <div>{product} topbar</div>,
}));
vi.mock("./AppBottomNav", () => ({
  AppBottomNav: () => null,
}));

beforeEach(() => {
  unreadMatchesMock.mockClear();
  mutationMock.mockReset();
  gestureMutationMock.mockReset();
  impersonationStatusMock.mockReset();
  impersonationStatusMock.mockReturnValue({
    data: { isImpersonating: false },
    isError: false,
    isSuccess: true,
  });
});

function AccessProbe() {
  const { candidateMutationsAllowed } = useAppShellAccess();
  return (
    <div>
      <span>{candidateMutationsAllowed ? "Standard access" : "Candidate changes blocked"}</span>
      {["Scan now", "Upload document", "Cancel job", "Retry job"].map((label) => (
        <button key={label} type="button" onClick={mutationMock}>
          {label}
        </button>
      ))}
      <div role="button" tabIndex={0} onPointerDown={gestureMutationMock}>
        Swipe match
      </div>
      <a href="/app/history">Candidate history</a>
    </div>
  );
}

describe("AppShell product subscriptions", () => {
  it("mounts the match subscription for Candidate", () => {
    render(<AppShell product="candidate">Candidate content</AppShell>);
    expect(unreadMatchesMock).toHaveBeenCalledOnce();
    expect(screen.getByText("Candidate content")).toBeInTheDocument();
  });

  it.each(["desk", "osint"] as const)(
    "does not mount Candidate subscriptions for %s",
    (product) => {
      render(<AppShell product={product}>Staff content</AppShell>);
      expect(unreadMatchesMock).not.toHaveBeenCalled();
      expect(screen.getByText(`${product} topbar`)).toBeInTheDocument();
    },
  );

  it("fails closed while Candidate impersonation status is loading", () => {
    impersonationStatusMock.mockReturnValue({
      isError: false,
      isSuccess: false,
    });

    render(
      <AppShell product="candidate">
        <AccessProbe />
      </AppShell>,
    );

    const scanButton = screen.getByRole("button", { name: "Scan now" });
    for (const label of ["Scan now", "Upload document", "Cancel job", "Retry job"]) {
      expect(screen.getByRole("button", { name: label })).toBeDisabled();
    }
    fireEvent.click(scanButton);
    fireEvent.pointerDown(screen.getByRole("button", { name: "Swipe match" }));
    expect(mutationMock).not.toHaveBeenCalled();
    expect(gestureMutationMock).not.toHaveBeenCalled();
    expect(screen.getByRole("link", { name: "Candidate history" })).toHaveAttribute(
      "href",
      "/app/history",
    );
    expect(screen.getByRole("status")).toHaveTextContent(/being verified/i);
  });

  it("fails closed when Candidate impersonation status is unavailable", () => {
    impersonationStatusMock.mockReturnValue({
      isError: true,
      isSuccess: false,
    });

    render(
      <AppShell product="candidate">
        <AccessProbe />
      </AppShell>,
    );

    expect(screen.getByRole("button", { name: "Scan now" })).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent(/could not be verified/i);
  });

  it("fails closed when Candidate impersonation status has no usable result", () => {
    impersonationStatusMock.mockReturnValue({
      data: undefined,
      isError: false,
      isSuccess: true,
    });

    render(
      <AppShell product="candidate">
        <AccessProbe />
      </AppShell>,
    );

    expect(screen.getByRole("button", { name: "Upload document" })).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent(/could not be verified/i);
  });

  it("keeps confirmed Candidate impersonation read-only", () => {
    impersonationStatusMock.mockReturnValue({
      data: { isImpersonating: true },
      isError: false,
      isSuccess: true,
    });

    render(
      <AppShell product="candidate">
        <AccessProbe />
      </AppShell>,
    );

    expect(screen.getByText("Candidate changes blocked")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Scan now" })).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent(/read-only impersonation is active/i);
  });

  it("enables Candidate mutations only after confirmed non-impersonation", () => {
    render(
      <AppShell product="candidate">
        <AccessProbe />
      </AppShell>,
    );

    expect(screen.getByText("Standard access")).toBeInTheDocument();
    const scanButton = screen.getByRole("button", { name: "Scan now" });
    for (const label of ["Scan now", "Upload document", "Cancel job", "Retry job"]) {
      expect(screen.getByRole("button", { name: label })).toBeEnabled();
    }
    fireEvent.click(scanButton);
    fireEvent.pointerDown(screen.getByRole("button", { name: "Swipe match" }));
    expect(mutationMock).toHaveBeenCalledOnce();
    expect(gestureMutationMock).toHaveBeenCalledOnce();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("does not apply Candidate read-only policy to an impersonated Desk shell", () => {
    impersonationStatusMock.mockReturnValue({
      data: { isImpersonating: true },
      isError: false,
      isSuccess: true,
    });

    render(
      <AppShell product="desk">
        <AccessProbe />
      </AppShell>,
    );

    expect(screen.getByText("Standard access")).toBeInTheDocument();
  });
});
