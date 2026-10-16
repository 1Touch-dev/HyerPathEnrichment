import { Suspense } from "react";
import {
  ShellPageHeader,
  ShellPageHeaderContent,
  ShellPageHeaderDescription,
  ShellPageHeaderEyebrow,
  ShellPageHeaderTitle,
  ShellSection,
} from "@/components/layout/ShellPage";
import { PortfolioStudio } from "@/features/portfolio";

export default function PortfolioPage() {
  return (
    <div className="space-y-6">
      <ShellPageHeader>
        <ShellPageHeaderContent>
          <ShellPageHeaderEyebrow>Candidate workspace</ShellPageHeaderEyebrow>
          <ShellPageHeaderTitle>Portfolio Studio</ShellPageHeaderTitle>
          <ShellPageHeaderDescription>
            Choose a template, shape your story, preview live, and publish a professional public
            portfolio when you&apos;re ready.
          </ShellPageHeaderDescription>
        </ShellPageHeaderContent>
      </ShellPageHeader>

      <ShellSection>
        <Suspense
          fallback={
            <div className="h-96 w-full animate-pulse rounded-xl border border-border/70 bg-surface shadow-panel" />
          }
        >
          <PortfolioStudio />
        </Suspense>
      </ShellSection>
    </div>
  );
}
