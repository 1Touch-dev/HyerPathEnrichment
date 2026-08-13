import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { CompletenessBanner } from "./CompletenessBanner";
import * as apiClient from "@/src/lib/api-client";
import type { CvCompleteness } from "@/src/lib/types";
import type { SuccessEnvelope } from "@/src/lib/api-envelope";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

function envelope<T>(data: T): SuccessEnvelope<T> {
  return { success: true, data, message: null, meta: null };
}

const incompleteData: CvCompleteness = {
  documentId: "doc1",
  completenessScore: 0.6,
  missingFields: ["phone", "location"],
  hasActiveChatSession: false,
};

describe("CompletenessBanner", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders nothing when missingFields is empty", async () => {
    vi.spyOn(apiClient, "fetchCvCompleteness").mockResolvedValue(
      envelope({ ...incompleteData, missingFields: [] }),
    );
    const onStartChat = vi.fn();
    const { container } = render(
      <CompletenessBanner documentId="doc1" onStartChat={onStartChat} />,
      { wrapper },
    );
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(container.firstChild).toBeNull();
  });

  it("renders percent, missing field count, and Complete it button", async () => {
    vi.spyOn(apiClient, "fetchCvCompleteness").mockResolvedValue(envelope(incompleteData));
    const onStartChat = vi.fn();
    render(<CompletenessBanner documentId="doc1" onStartChat={onStartChat} />, { wrapper });

    expect(await screen.findByText(/60% complete/)).toBeInTheDocument();
    expect(screen.getByText(/2 fields missing/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Complete it" })).toBeInTheDocument();
  });

  it("fires onStartChat on click", async () => {
    vi.spyOn(apiClient, "fetchCvCompleteness").mockResolvedValue(envelope(incompleteData));
    const onStartChat = vi.fn();
    render(<CompletenessBanner documentId="doc1" onStartChat={onStartChat} />, { wrapper });

    fireEvent.click(await screen.findByRole("button", { name: "Complete it" }));
    expect(onStartChat).toHaveBeenCalledTimes(1);
  });
});
