import { Suspense } from "react";
import { DocumentDetailView } from "./DocumentDetailView";

export default async function DocumentDetailPage({
  params,
}: {
  params: Promise<{ documentId: string }>;
}) {
  const { documentId } = await params;
  return (
    <Suspense fallback={<div className="animate-pulse h-96 rounded-lg bg-muted" />}>
      <DocumentDetailView documentId={documentId} />
    </Suspense>
  );
}
