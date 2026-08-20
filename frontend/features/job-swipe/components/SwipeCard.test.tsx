import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { PanInfo } from "framer-motion";
import { SwipeCard } from "./SwipeCard";
import * as jobMatchingClient from "@/features/job-matching/api/client";
import type { SwipeCard as SwipeCardData } from "@/src/lib/types";
import type { ReactNode } from "react";

// framer-motion's real drag gestures require a browser pointer-event environment
// that jsdom doesn't simulate. Mocking motion.div down to a plain div lets us
// capture the `onDragEnd` handler and `drag` prop it receives and invoke/assert
// them directly, which is what actually exercises SwipeCard's swipe-direction logic.
let capturedOnDragEnd: ((event: unknown, info: PanInfo) => void) | undefined;
let capturedDragProps: unknown[] = [];

vi.mock("framer-motion", async () => {
  const React = await import("react");
  return {
    motion: {
      div: ({
        children,
        onDragEnd,
        drag,
        style,
        dragSnapToOrigin,
        dragElastic,
        ...rest
      }: {
        children?: ReactNode;
        onDragEnd?: (event: unknown, info: PanInfo) => void;
        drag?: boolean;
        style?: unknown;
        dragSnapToOrigin?: boolean;
        dragElastic?: number;
        [key: string]: unknown;
      }) => {
        if (onDragEnd) {
          capturedOnDragEnd = onDragEnd;
          capturedDragProps.push(drag);
        }
        return React.createElement("div", { ...rest, "data-drag": String(!!drag) }, children);
      },
    },
    useMotionValue: () => ({ get: () => 0, set: () => {} }),
    useTransform: () => 0,
  };
});

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

const baseCard: SwipeCardData = {
  matchId: "m1",
  jobPostingId: "jp1",
  title: "Senior Engineer",
  company: "Acme",
  location: "Remote",
  remote: true,
  salaryMin: null,
  salaryMax: null,
  salaryCurrency: null,
  overallScore: 88,
  explanation: "Great fit for your skills.",
  belowSimilarityThreshold: false,
  sourceUrl: "https://example.com/job/1",
  appliedAt: null,
};

function makePanInfo(x: number, y: number): PanInfo {
  return {
    point: { x, y },
    delta: { x: 0, y: 0 },
    offset: { x, y },
    velocity: { x: 0, y: 0 },
  };
}

describe("SwipeCard", () => {
  beforeEach(() => {
    capturedOnDragEnd = undefined;
    capturedDragProps = [];
    vi.restoreAllMocks();
    vi.spyOn(jobMatchingClient, "markApplied").mockResolvedValue(undefined);
  });

  it("renders the card content", () => {
    render(<SwipeCard card={baseCard} onSwiped={() => {}} onDraftOutreach={() => {}} isTop />, {
      wrapper,
    });
    expect(screen.getByText("Senior Engineer")).toBeInTheDocument();
    expect(screen.getByText("Acme")).toBeInTheDocument();
    expect(screen.getByText("Great fit for your skills.")).toBeInTheDocument();
    expect(screen.getByText("88/100")).toBeInTheDocument();
  });

  it('renders a "Broader match" badge instead of the score badge when belowSimilarityThreshold is true', () => {
    const relaxedCard: SwipeCardData = { ...baseCard, belowSimilarityThreshold: true };
    render(<SwipeCard card={relaxedCard} onSwiped={() => {}} onDraftOutreach={() => {}} isTop />, {
      wrapper,
    });
    expect(screen.getByText("Broader match")).toBeInTheDocument();
    expect(screen.queryByText("88/100")).not.toBeInTheDocument();
  });

  it('calls onSwiped("right") when dragged right past the x threshold', () => {
    const onSwiped = vi.fn();
    render(<SwipeCard card={baseCard} onSwiped={onSwiped} onDraftOutreach={() => {}} isTop />, {
      wrapper,
    });
    capturedOnDragEnd?.(undefined, makePanInfo(150, 0));
    expect(onSwiped).toHaveBeenCalledWith("right");
  });

  it('calls onSwiped("left") when dragged left past the x threshold', () => {
    const onSwiped = vi.fn();
    render(<SwipeCard card={baseCard} onSwiped={onSwiped} onDraftOutreach={() => {}} isTop />, {
      wrapper,
    });
    capturedOnDragEnd?.(undefined, makePanInfo(-150, 0));
    expect(onSwiped).toHaveBeenCalledWith("left");
  });

  it('calls onSwiped("up") when dragged up past the y threshold', () => {
    const onSwiped = vi.fn();
    render(<SwipeCard card={baseCard} onSwiped={onSwiped} onDraftOutreach={() => {}} isTop />, {
      wrapper,
    });
    capturedOnDragEnd?.(undefined, makePanInfo(0, -150));
    expect(onSwiped).toHaveBeenCalledWith("up");
  });

  it("calls neither when below both thresholds", () => {
    const onSwiped = vi.fn();
    render(<SwipeCard card={baseCard} onSwiped={onSwiped} onDraftOutreach={() => {}} isTop />, {
      wrapper,
    });
    capturedOnDragEnd?.(undefined, makePanInfo(50, -20));
    expect(onSwiped).not.toHaveBeenCalled();
  });

  it('calls onSwiped("right"), not "up", when both thresholds are crossed but |y| < |x|', () => {
    const onSwiped = vi.fn();
    render(<SwipeCard card={baseCard} onSwiped={onSwiped} onDraftOutreach={() => {}} isTop />, {
      wrapper,
    });
    capturedOnDragEnd?.(undefined, makePanInfo(130, -110));
    expect(onSwiped).toHaveBeenCalledWith("right");
    expect(onSwiped).not.toHaveBeenCalledWith("up");
  });

  it("only enables drag on the top card", () => {
    render(<SwipeCard card={baseCard} onSwiped={() => {}} onDraftOutreach={() => {}} isTop />, {
      wrapper,
    });
    expect(capturedDragProps).toContain(true);

    capturedDragProps = [];
    render(
      <SwipeCard card={baseCard} onSwiped={() => {}} onDraftOutreach={() => {}} isTop={false} />,
      { wrapper },
    );
    expect(capturedDragProps).toContain(false);
  });

  it('calls onDraftOutreach with the matchId and company when "Draft outreach" is clicked', () => {
    const onDraftOutreach = vi.fn();
    render(
      <SwipeCard card={baseCard} onSwiped={() => {}} onDraftOutreach={onDraftOutreach} isTop />,
      { wrapper },
    );
    fireEvent.click(screen.getByRole("button", { name: "Draft outreach" }));
    expect(onDraftOutreach).toHaveBeenCalledWith("m1", "Acme");
  });

  it("renders an Apply link with rel=noopener noreferrer, target=_blank, and the correct href", () => {
    render(<SwipeCard card={baseCard} onSwiped={() => {}} onDraftOutreach={() => {}} isTop />, {
      wrapper,
    });
    const applyLink = screen.getByRole("link", { name: "Apply" });
    expect(applyLink).toHaveAttribute("href", "/api/matches/m1/apply-redirect");
    expect(applyLink).toHaveAttribute("target", "_blank");
    expect(applyLink).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("does not render the Apply button/Mark-as-applied toggle when isTop is false", () => {
    render(
      <SwipeCard card={baseCard} onSwiped={() => {}} onDraftOutreach={() => {}} isTop={false} />,
      { wrapper },
    );
    expect(screen.queryByRole("link", { name: "Apply" })).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: "Mark as applied" })).not.toBeInTheDocument();
  });

  it("Mark-as-applied checkbox is unchecked when appliedAt is null", () => {
    render(<SwipeCard card={baseCard} onSwiped={() => {}} onDraftOutreach={() => {}} isTop />, {
      wrapper,
    });
    expect(screen.getByRole("checkbox", { name: "Mark as applied" })).not.toBeChecked();
  });

  it("Mark-as-applied checkbox is checked when appliedAt is set", () => {
    const appliedCard: SwipeCardData = { ...baseCard, appliedAt: "2026-01-02T00:00:00Z" };
    render(<SwipeCard card={appliedCard} onSwiped={() => {}} onDraftOutreach={() => {}} isTop />, {
      wrapper,
    });
    expect(screen.getByRole("checkbox", { name: "Mark as applied" })).toBeChecked();
  });

  it("calls markApplied with applied=true when the Mark-as-applied checkbox is toggled on", async () => {
    render(<SwipeCard card={baseCard} onSwiped={() => {}} onDraftOutreach={() => {}} isTop />, {
      wrapper,
    });
    fireEvent.click(screen.getByRole("checkbox", { name: "Mark as applied" }));
    await waitFor(() => expect(jobMatchingClient.markApplied).toHaveBeenCalledWith("m1", true));
  });

  it("calls markApplied with applied=false when the Mark-as-applied checkbox is toggled off", async () => {
    const appliedCard: SwipeCardData = { ...baseCard, appliedAt: "2026-01-02T00:00:00Z" };
    render(<SwipeCard card={appliedCard} onSwiped={() => {}} onDraftOutreach={() => {}} isTop />, {
      wrapper,
    });
    fireEvent.click(screen.getByRole("checkbox", { name: "Mark as applied" }));
    await waitFor(() => expect(jobMatchingClient.markApplied).toHaveBeenCalledWith("m1", false));
  });
});
