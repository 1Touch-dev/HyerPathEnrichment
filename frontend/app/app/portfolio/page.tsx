import { Suspense } from "react";
import {
  ShellPageHeader,
  ShellPageHeaderContent,
  ShellPageHeaderDescription,
  ShellPageHeaderEyebrow,
  ShellPageHeaderTitle,
  ShellSection,
} from "@/components/layout/ShellPage";
import { PortfolioEditor } from "@/features/portfolio";

export default function PortfolioPage() {
  return (
    <div className="space-y-6">
      <ShellPageHeader>
        <ShellPageHeaderContent>
          <ShellPageHeaderEyebrow>Candidate workspace</ShellPageHeaderEyebrow>
          <ShellPageHeaderTitle>Portfolio</ShellPageHeaderTitle>
          <ShellPageHeaderDescription>
            Shape the public story you want recruiters and hiring teams to see, then control when
            the link is live.
          </ShellPageHeaderDescription>
        </ShellPageHeaderContent>
      </ShellPageHeader>

      <ShellSection>
        <Suspense fallback={<div className="animate-pulse h-96 rounded-lg bg-muted" />}>
          <PortfolioEditor />
        </Suspense>
      </ShellSection>
    </div>
  );
}
