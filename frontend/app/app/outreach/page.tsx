import { Suspense } from "react";
import { OutreachView } from "./OutreachView";

export default function OutreachPage() {
  return (
    <Suspense fallback={<div className="animate-pulse h-96 rounded-lg bg-muted" />}>
      <OutreachView />
    </Suspense>
  );
}
