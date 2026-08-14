import { Suspense } from "react";
import { PracticeReportView } from "./PracticeReportView";

export default async function PracticeReportPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;
  return (
    <Suspense fallback={<div className="animate-pulse h-96 rounded-lg bg-muted" />}>
      <PracticeReportView sessionId={sessionId} />
    </Suspense>
  );
}
