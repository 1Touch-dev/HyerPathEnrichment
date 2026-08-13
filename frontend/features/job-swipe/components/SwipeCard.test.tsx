import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import type { PanInfo } from "framer-motion";
import { SwipeCard } from "./SwipeCard";
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
  scoreBreakdown: {},
  explanation: "Great fit for your skills.",
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
  });

  it("renders the card content", () => {
    render(<SwipeCard card={baseCard} onSwiped={() => {}} isTop />);
    expect(screen.getByText("Senior Engineer")).toBeInTheDocument();
    expect(screen.getByText("Acme")).toBeInTheDocument();
    expect(screen.getByText("Great fit for your skills.")).toBeInTheDocument();
    expect(screen.getByText("88/100")).toBeInTheDocument();
  });

  it('calls onSwiped("right") when dragged right past the x threshold', () => {
    const onSwiped = vi.fn();
    render(<SwipeCard card={baseCard} onSwiped={onSwiped} isTop />);
    capturedOnDragEnd?.(undefined, makePanInfo(150, 0));
    expect(onSwiped).toHaveBeenCalledWith("right");
  });

  it('calls onSwiped("left") when dragged left past the x threshold', () => {
    const onSwiped = vi.fn();
    render(<SwipeCard card={baseCard} onSwiped={onSwiped} isTop />);
    capturedOnDragEnd?.(undefined, makePanInfo(-150, 0));
    expect(onSwiped).toHaveBeenCalledWith("left");
  });

  it('calls onSwiped("up") when dragged up past the y threshold', () => {
    const onSwiped = vi.fn();
    render(<SwipeCard card={baseCard} onSwiped={onSwiped} isTop />);
    capturedOnDragEnd?.(undefined, makePanInfo(0, -150));
    expect(onSwiped).toHaveBeenCalledWith("up");
  });

  it("calls neither when below both thresholds", () => {
    const onSwiped = vi.fn();
    render(<SwipeCard card={baseCard} onSwiped={onSwiped} isTop />);
    capturedOnDragEnd?.(undefined, makePanInfo(50, -20));
    expect(onSwiped).not.toHaveBeenCalled();
  });

  it('calls onSwiped("right"), not "up", when both thresholds are crossed but |y| < |x|', () => {
    const onSwiped = vi.fn();
    render(<SwipeCard card={baseCard} onSwiped={onSwiped} isTop />);
    capturedOnDragEnd?.(undefined, makePanInfo(130, -110));
    expect(onSwiped).toHaveBeenCalledWith("right");
    expect(onSwiped).not.toHaveBeenCalledWith("up");
  });

  it("only enables drag on the top card", () => {
    render(<SwipeCard card={baseCard} onSwiped={() => {}} isTop />);
    expect(capturedDragProps).toContain(true);

    capturedDragProps = [];
    render(<SwipeCard card={baseCard} onSwiped={() => {}} isTop={false} />);
    expect(capturedDragProps).toContain(false);
  });
});
