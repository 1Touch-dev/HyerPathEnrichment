import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import CandidateHistoryPage from "./history/page";
import CandidateJobDetailPage from "./jobs/[id]/page";
import CandidateJobsPage from "./jobs/page";
import CandidateLayout from "./layout";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "candidate-job-123" }),
  usePathname: () => "/app/jobs",
  useSearchParams: () => new URLSearchParams("state=queued&cursor=next"),
}));

vi.mock("@/components/auth/auth-guard", () => ({
  AuthGuard: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="candidate-auth">{children}</div>
  ),
}));

vi.mock("@/components/layout/AppShell", () => ({
  AppShell: ({ children, product }: { children: React.ReactNode; product: string }) => (
    <div data-testid="app-shell" data-product={product}>
      {children}
    </div>
  ),
}));

vi.mock("@/components/console/JobQueuePanel", () => ({
  JobQueuePanel: ({ jobsBasePath, queryString }: { jobsBasePath: string; queryString: string }) => (
    <div>{`Queue ${jobsBasePath}?${queryString}`}</div>
  ),
}));

vi.mock("@/components/console/JobHistoryPanel", () => ({
  JobHistoryPanel: ({
    jobsBasePath,
    queryString,
  }: {
    jobsBasePath: string;
    queryString: string;
  }) => <div>{`History ${jobsBasePath}?${queryString}`}</div>,
}));

vi.mock("@/features/enrich", () => ({
  JobDetailView: ({ jobId, jobsHref }: { jobId: string; jobsHref: string }) => (
    <div>{`Dossier ${jobId} back to ${jobsHref}`}</div>
  ),
}));

afterEach(() => {
  vi.clearAllMocks();
});

function renderCandidateRoute(page: React.ReactNode) {
  return render(<CandidateLayout>{page}</CandidateLayout>);
}

describe("Candidate job routes", () => {
  it("renders /app/jobs in the Candidate shell and preserves its query", () => {
    renderCandidateRoute(<CandidateJobsPage />);

    expect(screen.getByTestId("candidate-auth")).toBeInTheDocument();
    expect(screen.getByTestId("app-shell")).toHaveAttribute("data-product", "candidate");
    expect(screen.getByRole("heading", { name: "Jobs" })).toBeInTheDocument();
    expect(screen.getByText("Queue /app/jobs?state=queued&cursor=next")).toBeInTheDocument();
    expect(screen.getByText("History /app/jobs?state=queued&cursor=next")).toBeInTheDocument();
  });

  it("renders /app/jobs/:id in the Candidate shell with a query-preserving return path", () => {
    renderCandidateRoute(<CandidateJobDetailPage />);

    expect(screen.getByTestId("app-shell")).toHaveAttribute("data-product", "candidate");
    expect(
      screen.getByText("Dossier candidate-job-123 back to /app/jobs?state=queued&cursor=next"),
    ).toBeInTheDocument();
  });

  it("renders /app/history in the Candidate shell and keeps Candidate dossier links", () => {
    renderCandidateRoute(<CandidateHistoryPage />);

    expect(screen.getByTestId("app-shell")).toHaveAttribute("data-product", "candidate");
    expect(screen.getByRole("heading", { name: "History" })).toBeInTheDocument();
    expect(screen.getByText("History /app/jobs?state=queued&cursor=next")).toBeInTheDocument();
  });
});
