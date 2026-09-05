import { Suspense } from "react";
import { TrackerView } from "./TrackerView";

export default function TrackerPage() {
  return (
    <Suspense fallback={<div className="animate-pulse h-96 rounded-lg bg-muted" />}>
      <TrackerView />
    </Suspense>
  );
}
