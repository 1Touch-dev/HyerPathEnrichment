import { Suspense } from "react";
import { MatchesView } from "./MatchesView";

export default function MatchesPage() {
  return (
    <Suspense fallback={<div className="animate-pulse h-96 rounded-lg bg-muted" />}>
      <MatchesView />
    </Suspense>
  );
}
