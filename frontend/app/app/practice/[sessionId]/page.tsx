import { Suspense } from "react";
import { PracticeSessionView } from "./PracticeSessionView";

export default async function PracticeSessionPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;
  return (
    <Suspense fallback={<div className="animate-pulse h-96 rounded-lg bg-muted" />}>
      <PracticeSessionView sessionId={sessionId} />
    </Suspense>
  );
}
