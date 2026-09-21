import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MatchesView } from "@/app/app/matches/MatchesView";
import { DocumentUploadCard } from "@/components/console/DocumentUploadCard";
import {
  AppShellAccessProvider,
  CandidateMutationBoundary,
  CandidatePolicyLink,
  classifyCandidateLink,
  type CandidateMutationAccess,
} from "./app-shell-access";

const mocks = vi.hoisted(() => ({
  applyClick: vi.fn(),
  readLinkClick: vi.fn(),
  scanMutation: vi.fn(),
  uploadMutation: vi.fn(),
}));

beforeEach(() => {
  mocks.applyClick.mockReset();
  mocks.readLinkClick.mockReset();
  mocks.scanMutation.mockReset();
  mocks.uploadMutation.mockReset();
  mocks.uploadMutation.mockResolvedValue({ jobId: "job-1", message: "Queued" });
});

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ invalidateQueries: vi.fn() }),
}));

vi.mock("@/features/job-matching", () => ({
  MatchCard: () => null,
  useMatches: () => ({ data: { matches: [], total: 0 }, isLoading: false, isError: false }),
  useTriggerScan: () => ({ mutate: mocks.scanMutation, isPending: false }),
}));

vi.mock("@/features/documents", () => ({
  documentKeys: { list: () => ["documents"] },
  useDocumentJobQuery: () => ({ data: undefined, isFetching: false }),
  useUploadDocument: () => ({ mutateAsync: mocks.uploadMutation, isPending: false }),
}));

function CandidateSurfaces({ access }: { access: "allowed" | "impersonating" }) {
  return (
    <AppShellAccessProvider candidateMutationAccess={access}>
      <CandidateMutationBoundary>
        <MatchesView />
        <DocumentUploadCard />
      </CandidateMutationBoundary>
    </AppShellAccessProvider>
  );
}

function CandidateLinks({ access }: { access: CandidateMutationAccess }) {
  return (
    <AppShellAccessProvider candidateMutationAccess={access}>
      <CandidateMutationBoundary>
        <CandidatePolicyLink
          href="/api/matches/match-1/apply-redirect"
          onClick={(event) => {
            event.preventDefault();
            mocks.applyClick();
          }}
        >
          Apply
        </CandidatePolicyLink>
        <a
          href="/app/history"
          onClick={(event) => {
            event.preventDefault();
            mocks.readLinkClick();
          }}
        >
          Candidate history
        </a>
      </CandidateMutationBoundary>
    </AppShellAccessProvider>
  );
}

describe("Candidate mutation boundary surfaces", () => {
  it("blocks match scanning and document submission during impersonation", () => {
    render(<CandidateSurfaces access="impersonating" />);

    const scanButton = screen.getByRole("button", { name: "Scan now" });
    const fileInput = screen.getByLabelText("File");
    const uploadButton = screen.getByRole("button", { name: "Upload" });

    expect(scanButton).toBeDisabled();
    expect(fileInput).toBeDisabled();
    expect(uploadButton).toBeDisabled();
    fireEvent.click(scanButton);
    expect(mocks.scanMutation).not.toHaveBeenCalled();
    expect(mocks.uploadMutation).not.toHaveBeenCalled();
  });

  it("restores normal match scanning and document submission when access is confirmed", async () => {
    render(<CandidateSurfaces access="allowed" />);

    fireEvent.click(screen.getByRole("button", { name: "Scan now" }));
    expect(mocks.scanMutation).toHaveBeenCalledOnce();

    const file = new File(["candidate cv"], "candidate.pdf", { type: "application/pdf" });
    fireEvent.change(screen.getByLabelText("File"), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "Upload" }));

    await waitFor(() =>
      expect(mocks.uploadMutation).toHaveBeenCalledWith({
        file,
        documentType: "cv",
      }),
    );
  });

  it.each(["checking", "unavailable", "impersonating"] as CandidateMutationAccess[])(
    "blocks Apply GET side effects while access is %s but preserves read navigation",
    (access) => {
      render(<CandidateLinks access={access} />);

      const apply = screen.getByRole("link", { name: "Apply" });
      expect(apply).toHaveAttribute("aria-disabled", "true");
      expect(apply).not.toHaveAttribute("href");
      fireEvent.click(apply);
      expect(mocks.applyClick).not.toHaveBeenCalled();

      const history = screen.getByRole("link", { name: "Candidate history" });
      expect(history).toHaveAttribute("href", "/app/history");
      fireEvent.click(history);
      expect(mocks.readLinkClick).toHaveBeenCalledOnce();
    },
  );

  it("retains Apply behavior after confirmed non-impersonation", () => {
    render(<CandidateLinks access="allowed" />);

    const apply = screen.getByRole("link", { name: "Apply" });
    expect(apply).toHaveAttribute("href", "/api/matches/match-1/apply-redirect");
    fireEvent.click(apply);
    expect(mocks.applyClick).toHaveBeenCalledOnce();
  });

  it("classifies only known GET-side-effect routes as state-changing", () => {
    expect(classifyCandidateLink("/api/matches/match-1/apply-redirect")).toBe("state-changing");
    expect(classifyCandidateLink("/app/history?cursor=next")).toBe("read-only-navigation");
    expect(classifyCandidateLink("/api/interviews/matches/match-1/schedule.ics")).toBe(
      "read-only-navigation",
    );
    expect(classifyCandidateLink("https://jobs.example.test/posting/1")).toBe(
      "read-only-navigation",
    );
  });
});
