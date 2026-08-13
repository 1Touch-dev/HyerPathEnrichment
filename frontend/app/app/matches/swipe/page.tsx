import { Suspense } from "react";
import { SwipeDeckView } from "@/features/job-swipe";

export default function SwipeDeckPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">Swipe your matches</h1>
        <p className="text-sm text-muted-foreground">
          Swipe right if you&apos;re interested, left to pass, up for a super like.
        </p>
      </div>
      <Suspense fallback={<div className="animate-pulse h-[32rem] rounded-2xl bg-muted" />}>
        <SwipeDeckView />
      </Suspense>
    </div>
  );
}
