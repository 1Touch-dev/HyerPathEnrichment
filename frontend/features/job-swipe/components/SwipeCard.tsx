"use client";

import { motion, useMotionValue, useTransform, type PanInfo } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { SwipeCard as SwipeCardData, SwipeDirection } from "@/src/lib/types";

interface SwipeCardProps {
  card: SwipeCardData;
  onSwiped: (direction: SwipeDirection) => void;
  onDraftOutreach: (matchId: string, companyName: string) => void;
  isTop: boolean;
}

const SWIPE_THRESHOLD_X = 120;
const SWIPE_THRESHOLD_Y = -100;

function formatSalary(min: number | null, max: number | null, currency: string | null): string | null {
  if (min === null && max === null) return null;
  const cur = currency ?? "USD";
  if (min !== null && max !== null) return `${cur} ${min.toLocaleString()}–${max.toLocaleString()}`;
  return `${cur} ${(min ?? max)!.toLocaleString()}+`;
}

export function SwipeCard({ card, onSwiped, onDraftOutreach, isTop }: SwipeCardProps) {
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const rotate = useTransform(x, [-200, 200], [-15, 15]);
  const likeOpacity = useTransform(x, [20, SWIPE_THRESHOLD_X], [0, 1]);
  const passOpacity = useTransform(x, [-SWIPE_THRESHOLD_X, -20], [1, 0]);
  const superLikeOpacity = useTransform(y, [SWIPE_THRESHOLD_Y, -20], [1, 0]);

  function handleDragEnd(_event: unknown, info: PanInfo) {
    if (info.offset.y < SWIPE_THRESHOLD_Y && Math.abs(info.offset.x) < Math.abs(info.offset.y)) {
      onSwiped("up");
    } else if (info.offset.x > SWIPE_THRESHOLD_X) {
      onSwiped("right");
    } else if (info.offset.x < -SWIPE_THRESHOLD_X) {
      onSwiped("left");
    }
    // Below threshold — Framer Motion's `dragSnapToOrigin` (set on the motion.div) springs
    // the card back to center automatically; no manual reset needed here.
  }

  const salary = formatSalary(card.salaryMin, card.salaryMax, card.salaryCurrency);

  return (
    <motion.div
      className="absolute inset-0 select-none rounded-2xl border bg-card p-6 shadow-lg"
      style={{ x, y, rotate }}
      drag={isTop}
      dragSnapToOrigin
      dragElastic={0.6}
      onDragEnd={handleDragEnd}
      data-testid="swipe-card"
      data-match-id={card.matchId}
    >
      <motion.div
        className="absolute left-4 top-4 rounded border-4 border-green-500 px-3 py-1 text-xl font-bold text-green-500"
        style={{ opacity: likeOpacity }}
      >
        INTERESTED
      </motion.div>
      <motion.div
        className="absolute right-4 top-4 rounded border-4 border-red-500 px-3 py-1 text-xl font-bold text-red-500"
        style={{ opacity: passOpacity }}
      >
        PASS
      </motion.div>
      <motion.div
        className="absolute left-1/2 top-4 -translate-x-1/2 rounded border-4 border-blue-500 px-3 py-1 text-xl font-bold text-blue-500"
        style={{ opacity: superLikeOpacity }}
      >
        SUPER LIKE
      </motion.div>

      <div className="flex h-full flex-col justify-between">
        <div>
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-xl font-semibold">{card.title}</h2>
              <p className="text-muted-foreground">{card.company}</p>
            </div>
            <Badge className={card.overallScore >= 80 ? "bg-green-100 text-green-800" : "bg-yellow-100 text-yellow-800"}>
              {Math.round(card.overallScore)}/100
            </Badge>
          </div>
          {(card.location || card.remote) && (
            <p className="mt-2 text-sm text-muted-foreground">
              {card.remote ? "Remote" : card.location}
            </p>
          )}
          {salary && <p className="mt-1 text-sm font-medium">{salary}</p>}
        </div>

        {card.explanation && (
          <p className="mt-4 rounded-lg bg-muted p-3 text-sm text-muted-foreground">
            {card.explanation}
          </p>
        )}

        <Button
          size="sm"
          variant="outline"
          onClick={(e) => {
            e.stopPropagation();
            onDraftOutreach(card.matchId, card.company);
          }}
          className="mt-2"
        >
          Draft outreach
        </Button>
      </div>
    </motion.div>
  );
}
