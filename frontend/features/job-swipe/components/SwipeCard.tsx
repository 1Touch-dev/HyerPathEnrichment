"use client";

import { useState } from "react";
import { motion, useMotionValue, useTransform, type PanInfo } from "framer-motion";
import { UpgradeButton } from "@/features/billing";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import type { SwipeCard as SwipeCardData, SwipeDirection } from "@/src/lib/types";
import { getApplyRedirectUrl } from "@/features/job-matching/api/client";
import { useMarkApplied } from "@/features/job-matching/hooks/useMatches";

interface SwipeCardProps {
  card: SwipeCardData;
  onSwiped: (direction: SwipeDirection) => void;
  onDraftOutreach: (matchId: string, companyName: string) => void;
  isTop: boolean;
}

const SWIPE_THRESHOLD_X = 120;
const SWIPE_THRESHOLD_Y = -100;

function formatSalary(
  min: number | null,
  max: number | null,
  currency: string | null,
): string | null {
  if (min === null && max === null) return null;
  const cur = currency ?? "USD";
  if (min !== null && max !== null) return `${cur} ${min.toLocaleString()}–${max.toLocaleString()}`;
  return `${cur} ${(min ?? max)!.toLocaleString()}+`;
}

export function SwipeCard({ card, onSwiped, onDraftOutreach, isTop }: SwipeCardProps) {
  const [showExplanation, setShowExplanation] = useState(false);
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const rotate = useTransform(x, [-200, 200], [-15, 15]);
  const likeOpacity = useTransform(x, [20, SWIPE_THRESHOLD_X], [0, 1]);
  const passOpacity = useTransform(x, [-SWIPE_THRESHOLD_X, -20], [1, 0]);
  const superLikeOpacity = useTransform(y, [SWIPE_THRESHOLD_Y, -20], [1, 0]);
  const markApplied = useMarkApplied();

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
            <Badge
              className={
                card.belowSimilarityThreshold
                  ? "bg-muted text-muted-foreground"
                  : card.overallScore >= 80
                    ? "bg-green-100 text-green-800"
                    : "bg-yellow-100 text-yellow-800"
              }
            >
              {card.belowSimilarityThreshold
                ? "Broader match"
                : `${Math.round(card.overallScore)}/100`}
            </Badge>
          </div>
          {(card.location || card.remote) && (
            <p className="mt-2 text-sm text-muted-foreground">
              {card.remote ? "Remote" : card.location}
            </p>
          )}
          {salary && <p className="mt-1 text-sm font-medium">{salary}</p>}
        </div>

        {card.explanation && isTop && (
          <div className="mt-4">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setShowExplanation((prev) => !prev);
              }}
              className="rounded-full border px-3 py-1 text-xs font-medium text-muted-foreground hover:bg-muted"
            >
              Why we matched you
            </button>
            {showExplanation && (
              <div className={card.isBlurred ? "relative mt-2" : "mt-2"}>
                <p
                  className={
                    card.isBlurred
                      ? "rounded-lg bg-muted p-3 text-sm text-muted-foreground blur-sm select-none"
                      : "rounded-lg bg-muted p-3 text-sm text-muted-foreground"
                  }
                >
                  {card.explanation}
                </p>
                {card.isBlurred ? (
                  <div className="mt-2">
                    <UpgradeButton />
                  </div>
                ) : null}
              </div>
            )}
          </div>
        )}

        {isTop && (
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={(e) => {
                e.stopPropagation();
                onDraftOutreach(card.matchId, card.company);
              }}
            >
              Draft outreach
            </Button>
            <Button size="sm" asChild>
              <a
                href={getApplyRedirectUrl(card.matchId)}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
              >
                Apply
              </a>
            </Button>
            <div
              className="flex items-center gap-2"
              onClick={(e) => e.stopPropagation()}
              onPointerDown={(e) => e.stopPropagation()}
            >
              <Checkbox
                id={`applied-${card.matchId}`}
                checked={card.appliedAt !== null}
                onCheckedChange={(checked) =>
                  markApplied.mutate({ matchId: card.matchId, applied: checked === true })
                }
              />
              <Label htmlFor={`applied-${card.matchId}`} className="text-sm text-muted-foreground">
                Mark as applied
              </Label>
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
}
