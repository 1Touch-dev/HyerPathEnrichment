import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import OsintJobsPage from "./jobs/page";
import OsintLayout from "./layout";
import OsintLookupPage from "./page";
import OsintSettingsPage from "./settings/page";
import OsintSecuritySettingsPage from "./settings/security/page";
import type { EnrichmentInput } from "@/src/lib/types";

const mocks = vi.hoisted(() => ({
  dispatch: vi.fn(),
  mutateAsync: vi.fn(),
  push: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
  useSearchParams: () => new URLSearchParams("tiers=tier1%2Ctier3"),
}));

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

vi.mock("@/components/auth/staff-guard", () => ({
  StaffGuard: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="staff-guard">{children}</div>
  ),
}));

vi.mock("@/components/layout/AppShell", () => ({
  AppShell: ({ children, product }: { children: React.ReactNode; product: string }) => (
    <div data-product={product}>{children}</div>
  ),
}));

vi.mock("@/components/console/EnrichModeToggle", () => ({
  EnrichModeToggle: () => <div>Mode toggle</div>,
}));

vi.mock("@/components/console/IntakeForm", () => ({
  IntakeForm: ({
    initialTiers,
    onSubmit,
  }: {
    initialTiers: string[];
    onSubmit: (input: EnrichmentInput) => Promise<void>;
  }) => (
    <div>
      <span>Selected tiers: {initialTiers.join(",")}</span>
      <button
        type="button"
        onClick={() =>
          void onSubmit({
            email: "staff-supplied@example.com",
            linkedinUrl: "",
            username: "",
            company: "",
            business: "",
            jobSearch: "",
            requestedTiers: ["tier1", "tier3"],
          })
        }
      >
        Submit lookup
      </button>
    </div>
  ),
}));

vi.mock("@/components/console/JobQueuePanel", () => ({
  JobQueuePanel: () => <div>Embedded queue</div>,
}));

vi.mock("@/components/console/JobHistoryPanel", () => ({
  JobHistoryPanel: () => <div>Embedded history</div>,
}));

vi.mock("@/components/console/JobProgress", () => ({
  JobProgress: () => <div>Job progress</div>,
}));

vi.mock("@/features/enrich", () => ({
  useCreateEnrichment: () => ({
    mutateAsync: mocks.mutateAsync,
    error: null,
    isPending: false,
  }),
  useJobCompletionToasts: () => vi.fn(),
  useJobQuery: () => ({ data: null, isFetching: false }),
}));

vi.mock("@/hooks/useLocalStorageJobs", () => ({
  useLocalStorageJobs: () => ({
    addJob: vi.fn(),
    updateJobStatus: vi.fn(),
  }),
}));

vi.mock("@/store/hooks", () => ({
  useAppDispatch: () => mocks.dispatch,
  useAppSelector: (
    selector: (state: {
      intake: {
        draft: { requestedTiers: [] };
        enrichMode: "sync";
      };
    }) => unknown,
  ) =>
    selector({
      intake: {
        draft: { requestedTiers: [] },
        enrichMode: "sync",
      },
    }),
}));

vi.mock("@/features/settings", () => ({
  SettingsView: ({ securityHref }: { securityHref: string }) => (
    <a href={securityHref}>OSINT security</a>
  ),
}));

vi.mock("@/features/admin", () => ({
  MfaSetupCard: () => <div>MFA settings</div>,
}));

beforeEach(() => {
  mocks.dispatch.mockReset();
  mocks.mutateAsync.mockReset();
  mocks.push.mockReset();
  mocks.mutateAsync.mockResolvedValue({ id: "job-123", status: "completed" });
});

describe("OSINT route surface", () => {
  it("mounts the staff-only OSINT shell", () => {
    render(
      <OsintLayout>
        <div>OSINT content</div>
      </OsintLayout>,
    );

    expect(screen.getByTestId("staff-guard")).toHaveTextContent("OSINT content");
    expect(screen.getByText("OSINT content").parentElement).toHaveAttribute(
      "data-product",
      "osint",
    );
  });

  it("keeps tiers on Look up and sends sync results to the canonical dossier", async () => {
    render(<OsintLookupPage />);

    await waitFor(() =>
      expect(mocks.dispatch).toHaveBeenCalledWith({
        type: "intake/patchDraft",
        payload: { requestedTiers: ["tier1", "tier3"] },
      }),
    );
    expect(screen.getByText("Embedded queue")).toBeInTheDocument();
    expect(screen.getByText("Embedded history")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open jobs" })).toHaveAttribute("href", "/osint/jobs");

    fireEvent.click(screen.getByRole("button", { name: "Submit lookup" }));
    await waitFor(() => expect(mocks.push).toHaveBeenCalledWith("/osint/jobs/job-123"));
  });

  it("keeps queue and history behind in-page Jobs access", () => {
    render(<OsintJobsPage />);

    expect(screen.getByText("Embedded queue")).toBeInTheDocument();
    expect(screen.getByText("Embedded history")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to look up" })).toHaveAttribute("href", "/osint");
  });

  it("reuses settings without leaving the OSINT shell", () => {
    const { unmount } = render(<OsintSettingsPage />);
    expect(screen.getByRole("link", { name: "OSINT security" })).toHaveAttribute(
      "href",
      "/osint/settings/security",
    );

    unmount();
    render(<OsintSecuritySettingsPage />);
    expect(screen.getByRole("link", { name: "Back to Settings" })).toHaveAttribute(
      "href",
      "/osint/settings",
    );
    expect(screen.getByText("MFA settings")).toBeInTheDocument();
  });
});
