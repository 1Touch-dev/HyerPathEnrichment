import { Suspense } from "react";
import { PortfolioEditor } from "@/features/portfolio";

export default function PortfolioPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Portfolio</h1>
      <Suspense fallback={<div className="animate-pulse h-96 rounded-lg bg-muted" />}>
        <PortfolioEditor />
      </Suspense>
    </div>
  );
}
