"use client";

import { ReactNode } from "react";
import { usePathname } from "next/navigation";
import { VerificationBanner } from "@/components/auth/verification-banner";
import { useUnreadMatchEvents } from "@/features/job-matching";
import { AppBottomNav } from "./AppBottomNav";
import { AppNavRail } from "./AppNavRail";
import { AppSidebar } from "./AppSidebar";
import { AppTopbar } from "./AppTopbar";

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  // Lifted here (rather than in MatchesView) so the "Matches" nav badge stays
  // live on every /app/* page, not just while the matches view is mounted.
  const { unreadCount } = useUnreadMatchEvents();
  const matchesUnreadCount = unreadCount ?? 0;

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <div className="hidden lg:flex">
        <AppSidebar matchesUnreadCount={matchesUnreadCount} />
      </div>
      <AppNavRail pathname={pathname} matchesUnreadCount={matchesUnreadCount} />
      <div className="flex min-w-0 flex-1 flex-col">
        <AppTopbar />
        <VerificationBanner />
        <main className="flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-6">{children}</main>
        <AppBottomNav pathname={pathname} matchesUnreadCount={matchesUnreadCount} />
      </div>
    </div>
  );
}
