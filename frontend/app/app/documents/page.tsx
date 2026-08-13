import { Suspense } from "react";
import { DocumentsView } from "./DocumentsView";

export default function DocumentsPage() {
  return (
    <Suspense fallback={<div className="animate-pulse h-96 rounded-lg bg-muted" />}>
      <DocumentsView />
    </Suspense>
  );
}
