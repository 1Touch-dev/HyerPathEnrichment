import { Suspense } from "react";
import { PracticeLandingView } from "./PracticeLandingView";

export default function PracticePage() {
  return (
    <Suspense fallback={<div className="animate-pulse h-96 rounded-lg bg-muted" />}>
      <PracticeLandingView />
    </Suspense>
  );
}
