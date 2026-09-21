import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import OsintJobDetailPage from "./jobs/[id]/page";
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
  trackJobCompletion: vi.fn(),
  addJob: vi.fn(),
  updateJobStatus: vi.fn(),
  searchParams: new URLSearchParams("tiers=tier1%2Ctier3"),
  intakeState: {
    draft: { requestedTiers: [] as string[] },
    enrichMode: "sync" as "sync" | "async",
  },
  jobQueryResult: { data: null as { id: string; status: "completed" } | null, isFetching: false },
  params: { id: "job-123" },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
  useSearchParams: () => mocks.searchParams,
  useParams: () => mocks.params,
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
  JobQueuePanel: ({
    jobsBasePath = "/osint/jobs",
    queryString = "",
  }: {
    jobsBasePath?: string;
    queryString?: string;
  }) => (
    <div data-testid="queue-panel" data-base-path={jobsBasePath} data-query={queryString}>
      Embedded queue
    </div>
  ),
}));

vi.mock("@/components/console/JobHistoryPanel", () => ({
  JobHistoryPanel: ({
    jobsBasePath = "/osint/jobs",
    queryString = "",
  }: {
    jobsBasePath?: string;
    queryString?: string;
  }) => (
    <div data-testid="history-panel" data-base-path={jobsBasePath} data-query={queryString}>
      Embedded history
    </div>
  ),
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
  useJobCompletionToasts: () => mocks.trackJobCompletion,
  useJobQuery: (jobId?: string) =>
    jobId ? mocks.jobQueryResult : { data: null, isFetching: false },
  JobDetailView: ({ jobId, jobsHref }: { jobId: string; jobsHref: string }) => (
    <div data-testid="job-detail" data-job-id={jobId} data-jobs-href={jobsHref} />
  ),
}));

vi.mock("@/hooks/useLocalStorageJobs", () => ({
  useLocalStorageJobs: () => ({
    jobs: [],
    activeJobs: [],
    addJob: mocks.addJob,
    updateJobStatus: mocks.updateJobStatus,
  }),
}));

vi.mock("@/store/hooks", () => ({
  useAppDispatch: () => mocks.dispatch,
  useAppSelector: (
    selector: (state: {
      intake: {
        draft: { requestedTiers: string[] };
        enrichMode: "sync" | "async";
      };
    }) => unknown,
  ) =>
    selector({
      intake: mocks.intakeState,
    }),
}));

vi.mock("@/features/settings", () => ({
  SettingsView: ({
    securityHref,
    showShellHeader = true,
  }: {
    securityHref: string;
    showShellHeader?: boolean;
  }) => (
    <div data-testid="settings-view" data-shell-header={String(showShellHeader)}>
      <a href={securityHref}>OSINT security</a>
    </div>
  ),
}));

vi.mock("@/features/admin", () => ({
  MfaSetupCard: () => <div>MFA settings</div>,
}));

beforeEach(() => {
  mocks.dispatch.mockReset();
  mocks.mutateAsync.mockReset();
  mocks.push.mockReset();
  mocks.trackJobCompletion.mockReset();
  mocks.addJob.mockReset();
  mocks.updateJobStatus.mockReset();
  mocks.searchParams = new URLSearchParams("tiers=tier1%2Ctier3");
  mocks.intakeState = {
    draft: { requestedTiers: [] },
    enrichMode: "sync",
  };
  mocks.jobQueryResult = { data: null, isFetching: false };
  mocks.params = { id: "job-123" };
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
    expect(screen.getByRole("link", { name: "Open jobs" })).toHaveAttribute(
      "href",
      "/osint/jobs?tiers=tier1%2Ctier3",
    );

    fireEvent.click(screen.getByRole("button", { name: "Submit lookup" }));
    await waitFor(() =>
      expect(mocks.push).toHaveBeenCalledWith("/osint/jobs/job-123?tiers=tier1%2Ctier3"),
    );
  });

  it("keeps async lookups in-place until the dossier is ready", async () => {
    mocks.intakeState = {
      draft: { requestedTiers: [] },
      enrichMode: "async",
    };
    mocks.jobQueryResult = {
      data: { id: "job-123", status: "completed" },
      isFetching: false,
    };

    render(<OsintLookupPage />);

    fireEvent.click(screen.getByRole("button", { name: "Submit lookup" }));

    await waitFor(() => expect(mocks.addJob).toHaveBeenCalledWith("job-123", "completed"));
    expect(mocks.trackJobCompletion).toHaveBeenCalledWith("job-123");
    expect(mocks.push).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Open dossier" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Open dossier" }));
    await waitFor(() =>
      expect(mocks.push).toHaveBeenCalledWith("/osint/jobs/job-123?tiers=tier1%2Ctier3"),
    );
  });

  it("keeps queue and history behind in-page Jobs access", () => {
    render(<OsintJobsPage />);

    expect(screen.getByText("Embedded queue")).toBeInTheDocument();
    expect(screen.getByText("Embedded history")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to workbench" })).toHaveAttribute(
      "href",
      "/osint?tiers=tier1%2Ctier3",
    );
    expect(screen.getByTestId("queue-panel")).toHaveAttribute("data-query", "tiers=tier1%2Ctier3");
    expect(screen.getByTestId("history-panel")).toHaveAttribute(
      "data-query",
      "tiers=tier1%2Ctier3",
    );
  });

  it("preserves query state when opening a dossier detail", () => {
    render(<OsintJobDetailPage />);

    expect(screen.getByTestId("job-detail")).toHaveAttribute("data-job-id", "job-123");
    expect(screen.getByTestId("job-detail")).toHaveAttribute(
      "data-jobs-href",
      "/osint/jobs?tiers=tier1%2Ctier3",
    );
  });

  it("reuses settings without leaving the OSINT shell", () => {
    const { unmount } = render(<OsintSettingsPage />);
    expect(screen.getByTestId("settings-view")).toHaveAttribute("data-shell-header", "false");
    expect(screen.getByRole("link", { name: "OSINT security" })).toHaveAttribute(
      "href",
      "/osint/settings/security",
    );

    unmount();
    render(<OsintSecuritySettingsPage />);
    expect(screen.getByRole("link", { name: "Back to settings" })).toHaveAttribute(
      "href",
      "/osint/settings",
    );
    expect(screen.getByText("MFA settings")).toBeInTheDocument();
  });
});
