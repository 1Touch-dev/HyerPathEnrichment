import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { SwipeDeckView } from "./SwipeDeckView";
import * as useSwipeDeckModule from "../hooks/useSwipeDeck";
import * as outreachModule from "@/features/outreach";
import type { SwipeDeck } from "@/src/lib/types";

let lastOnSwiped: ((direction: "left" | "right" | "up") => void) | undefined;

vi.mock("./SwipeCard", () => ({
  SwipeCard: ({
    card,
    isTop,
    onSwiped,
  }: {
    card: { matchId: string };
    isTop: boolean;
    onSwiped: (direction: "left" | "right" | "up") => void;
    onDraftOutreach: (matchId: string, companyName: string) => void;
  }) => {
    lastOnSwiped = onSwiped;
    return (
      <div data-testid="swipe-card" data-match-id={card.matchId} data-is-top={String(isTop)} />
    );
  },
}));

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const mutateMock = vi.fn();
const draftOutreachMutateMock = vi.fn();

function mockUseSwipeDeck(overrides: Partial<ReturnType<typeof useSwipeDeckModule.useSwipeDeck>>) {
  vi.spyOn(useSwipeDeckModule, "useSwipeDeck").mockReturnValue({
    data: undefined,
    isLoading: false,
    isError: false,
    ...overrides,
  } as ReturnType<typeof useSwipeDeckModule.useSwipeDeck>);
}

describe("SwipeDeckView", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mutateMock.mockReset();
    draftOutreachMutateMock.mockReset();
    lastOnSwiped = undefined;
    vi.spyOn(useSwipeDeckModule, "useSubmitSwipe").mockReturnValue({
      mutate: mutateMock,
    } as unknown as ReturnType<typeof useSwipeDeckModule.useSubmitSwipe>);
    vi.spyOn(outreachModule, "useDraftOutreachForMatch").mockReturnValue({
      mutate: draftOutreachMutateMock,
    } as unknown as ReturnType<typeof outreachModule.useDraftOutreachForMatch>);
  });

  it("renders a loading skeleton", () => {
    mockUseSwipeDeck({ isLoading: true });
    render(<SwipeDeckView />, { wrapper });
    expect(screen.queryByTestId("swipe-card")).not.toBeInTheDocument();
  });

  it("renders an error state", () => {
    mockUseSwipeDeck({ isError: true });
    render(<SwipeDeckView />, { wrapper });
    expect(screen.getByText("Couldn't load your deck")).toBeInTheDocument();
  });

  it("renders an empty state when there are no cards and hasMore is false", () => {
    mockUseSwipeDeck({ data: { cards: [], hasMore: false } as SwipeDeck });
    render(<SwipeDeckView />, { wrapper });
    expect(screen.getByText("No new matches to review")).toBeInTheDocument();
  });

  it('shows a "Load more" affordance when there are no cards but hasMore is true', () => {
    const refetchMock = vi.fn();
    mockUseSwipeDeck({ data: { cards: [], hasMore: true } as SwipeDeck, refetch: refetchMock });
    render(<SwipeDeckView />, { wrapper });
    expect(screen.getByText("You're caught up on this page")).toBeInTheDocument();
    const loadMoreButton = screen.getByRole("button", { name: "Load more" });
    fireEvent.click(loadMoreButton);
    expect(refetchMock).toHaveBeenCalled();
  });

  it("renders at most MAX_STACKED_CARDS cards, with exactly one isTop=true", () => {
    const cards = Array.from({ length: 5 }, (_, i) => ({
      matchId: `m${i}`,
      jobPostingId: `jp${i}`,
      title: `Job ${i}`,
      company: "Acme",
      location: null,
      remote: true,
      salaryMin: null,
      salaryMax: null,
      salaryCurrency: null,
      overallScore: 80,
      explanation: null,
    }));
    mockUseSwipeDeck({ data: { cards, hasMore: false } as SwipeDeck });
    render(<SwipeDeckView />, { wrapper });

    const rendered = screen.getAllByTestId("swipe-card");
    expect(rendered).toHaveLength(3);
    const topCards = rendered.filter((el) => el.getAttribute("data-is-top") === "true");
    expect(topCards).toHaveLength(1);
  });

  it("calls submitSwipe.mutate with the swiped card's matchId and direction", () => {
    const cards = [
      {
        matchId: "m0",
        jobPostingId: "jp0",
        title: "Job 0",
        company: "Acme",
        location: null,
        remote: true,
        salaryMin: null,
        salaryMax: null,
        salaryCurrency: null,
        overallScore: 80,
        explanation: null,
      },
    ];
    mockUseSwipeDeck({ data: { cards, hasMore: false } as SwipeDeck });
    render(<SwipeDeckView />, { wrapper });

    lastOnSwiped?.("right");
    expect(mutateMock).toHaveBeenCalledWith({ matchId: "m0", direction: "right" });
  });
});
