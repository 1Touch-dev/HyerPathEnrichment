import { Suspense } from "react";
import {
  ShellPageHeader,
  ShellPageHeaderActions,
  ShellPageHeaderContent,
  ShellPageHeaderDescription,
  ShellPageHeaderEyebrow,
  ShellPageHeaderTitle,
  ShellSection,
} from "@/components/layout/ShellPage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SwipeDeckView } from "@/features/job-swipe";
import Link from "next/link";

export default function SwipeDeckPage() {
  return (
    <div className="space-y-6">
      <ShellPageHeader>
        <ShellPageHeaderContent>
          <ShellPageHeaderEyebrow>Candidate workspace</ShellPageHeaderEyebrow>
          <ShellPageHeaderTitle>Swipe through matches</ShellPageHeaderTitle>
          <ShellPageHeaderDescription>
            Move quickly when you want momentum: swipe right if interested, left to pass, or up when
            a role deserves extra attention.
          </ShellPageHeaderDescription>
        </ShellPageHeaderContent>
        <ShellPageHeaderActions className="items-start sm:items-center">
          <Badge variant="outline">Right = interested</Badge>
          <Badge variant="outline">Left = pass</Badge>
          <Badge variant="outline">Up = super like</Badge>
          <Button asChild variant="ghost">
            <Link href="/app/matches">Back to list</Link>
          </Button>
        </ShellPageHeaderActions>
      </ShellPageHeader>

      <ShellSection surface="muted" className="items-center">
        <Suspense
          fallback={<div className="animate-pulse h-[32rem] w-full rounded-2xl bg-muted" />}
        >
          <SwipeDeckView />
        </Suspense>
      </ShellSection>
    </div>
  );
}
