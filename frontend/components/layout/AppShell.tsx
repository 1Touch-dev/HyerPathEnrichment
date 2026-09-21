"use client";

import { ReactNode } from "react";
import { usePathname } from "next/navigation";
import { VerificationBanner } from "@/components/auth/verification-banner";
import { useUnreadMatchEvents } from "@/features/job-matching";
import { ImpersonationBanner, useImpersonationStatus } from "@/features/admin";
import { useAuth } from "@/providers/auth-provider";
import type { ProductDoorUser, Product } from "@/src/lib/product-doors";
import {
  AppShellAccessProvider,
  CandidateMutationBoundary,
  type CandidateMutationAccess,
} from "./app-shell-access";
import { AppBottomNav } from "./AppBottomNav";
import { AppNavRail } from "./AppNavRail";
import { AppSidebar } from "./AppSidebar";
import { AppTopbar } from "./AppTopbar";
import { ShellPage, ShellViewport } from "./ShellPage";
import { getNavSections } from "./nav-config";

type AppShellProps = {
  children: ReactNode;
  product: Product;
};

type AppShellChromeProps = AppShellProps & {
  matchesUnreadCount: number;
  user: ProductDoorUser | null;
};

function AppShellChrome({ children, product, matchesUnreadCount, user }: AppShellChromeProps) {
  const pathname = usePathname();
  const sections = getNavSections(product, user);

  return (
    <div className="flex h-screen overflow-hidden bg-background text-foreground">
      <div className="hidden lg:flex lg:shrink-0">
        <AppSidebar product={product} sections={sections} matchesUnreadCount={matchesUnreadCount} />
      </div>
      <AppNavRail
        product={product}
        sections={sections}
        pathname={pathname}
        matchesUnreadCount={matchesUnreadCount}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <AppTopbar product={product} sections={sections} />
        <VerificationBanner />
        <ImpersonationBanner />
        <main className="min-h-0 flex-1 overflow-y-auto">
          <ShellViewport product={product}>
            <ShellPage product={product}>
              {product === "candidate" ? (
                <CandidateMutationBoundary>{children}</CandidateMutationBoundary>
              ) : (
                children
              )}
            </ShellPage>
          </ShellViewport>
        </main>
        <AppBottomNav
          sections={sections}
          pathname={pathname}
          matchesUnreadCount={matchesUnreadCount}
        />
      </div>
    </div>
  );
}

function CandidateAppShell({
  children,
  user,
}: Omit<AppShellChromeProps, "matchesUnreadCount" | "product">) {
  // Keep the candidate match stream out of staff shells while retaining a live
  // badge throughout the Candidate product.
  const { unreadCount } = useUnreadMatchEvents();
  return (
    <AppShellChrome product="candidate" user={user} matchesUnreadCount={unreadCount ?? 0}>
      {children}
    </AppShellChrome>
  );
}

export function AppShell({ children, product }: AppShellProps) {
  const { user } = useAuth();
  const {
    data: impersonation,
    isError: impersonationError,
    isSuccess: impersonationConfirmed,
  } = useImpersonationStatus();
  let candidateMutationAccess: CandidateMutationAccess = "allowed";
  if (product === "candidate") {
    if (impersonationConfirmed && impersonation?.isImpersonating === false) {
      candidateMutationAccess = "allowed";
    } else if (impersonationConfirmed && impersonation?.isImpersonating === true) {
      candidateMutationAccess = "impersonating";
    } else if (impersonationError || impersonationConfirmed) {
      candidateMutationAccess = "unavailable";
    } else {
      candidateMutationAccess = "checking";
    }
  }
  const shell =
    product === "candidate" ? (
      <CandidateAppShell user={user}>{children}</CandidateAppShell>
    ) : (
      <AppShellChrome product={product} user={user} matchesUnreadCount={0}>
        {children}
      </AppShellChrome>
    );

  return (
    <AppShellAccessProvider candidateMutationAccess={candidateMutationAccess}>
      {shell}
    </AppShellAccessProvider>
  );
}
