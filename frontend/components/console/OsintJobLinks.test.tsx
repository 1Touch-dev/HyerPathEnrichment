import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { JobHistoryTable } from "./JobHistoryTable";
import { JobProgress } from "./JobProgress";
import { JobQueuePanel } from "./JobQueuePanel";
import type { EnrichmentJob } from "@/src/lib/types";

const localJobs = vi.hoisted(() => ({
  jobs: [
    {
      id: "job-123",
      status: "completed" as const,
      createdAt: Date.now(),
      completedAt: Date.now() - 5000,
    },
  ],
  activeJobs: [],
  removeJob: vi.fn(),
  clearCompleted: vi.fn(),
}));

vi.mock("@/hooks/useLocalStorageJobs", () => ({
  useLocalStorageJobs: () => localJobs,
}));

beforeEach(() => {
  localJobs.removeJob.mockReset();
  localJobs.clearCompleted.mockReset();
});

describe("OSINT job links", () => {
  it("opens queued jobs at the canonical dossier route", () => {
    render(<JobQueuePanel />);

    const jobLink = screen.getByRole("link");
    expect(jobLink).toHaveAttribute("href", "/osint/jobs/job-123");
  });

  it("uses canonical dossier links throughout expanded history", () => {
    render(
      <JobHistoryTable
        jobs={[
          {
            id: "job-123",
            status: "completed",
            createdAt: "2026-09-02T10:00:00Z",
            updatedAt: "2026-09-02T10:01:00Z",
            identifierSummary: "supplied identifier",
            requestedTiers: ["tier1", "tier3"],
          },
        ]}
        total={1}
        limit={50}
        offset={0}
      />,
    );

    expect(screen.getByRole("link", { name: "supplied identifier" })).toHaveAttribute(
      "href",
      "/osint/jobs/job-123",
    );

    fireEvent.click(screen.getByRole("button", { name: "Show more columns" }));
    for (const link of screen.getAllByRole("link")) {
      expect(link).toHaveAttribute("href", "/osint/jobs/job-123");
    }
  });

  it("points timed-out progress to the canonical dossier", () => {
    const job = {
      id: "job-123",
      status: "completed",
      createdAt: "2026-09-02T10:00:00Z",
      updatedAt: "2026-09-02T10:01:00Z",
      input: { requestedTiers: ["tier1"] },
      dossier: {
        handles: [],
        emails: [],
        verifiedEmails: [],
        coworkers: [],
        jobs: [],
        confidence: [],
        sources: [],
        metadata: {
          generatedAt: "2026-09-02T10:01:00Z",
          pipelineId: "pipeline-123",
          requestedTiers: ["tier1"],
          identifierSummary: "supplied identifier",
        },
      },
    } satisfies EnrichmentJob;

    render(<JobProgress job={job} pollTimedOut />);

    expect(screen.getByRole("link", { name: "job detail" })).toHaveAttribute(
      "href",
      "/osint/jobs/job-123",
    );
  });
});
