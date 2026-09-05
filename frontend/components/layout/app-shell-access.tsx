"use client";

import {
  createContext,
  useContext,
  type AnchorHTMLAttributes,
  type ReactNode,
  type SyntheticEvent,
} from "react";

export type CandidateMutationAccess = "allowed" | "checking" | "unavailable" | "impersonating";

type AppShellAccess = {
  candidateMutationAccess: CandidateMutationAccess;
  candidateMutationsAllowed: boolean;
};

const AppShellAccessContext = createContext<AppShellAccess>({
  candidateMutationAccess: "unavailable",
  candidateMutationsAllowed: false,
});

export function AppShellAccessProvider({
  children,
  candidateMutationAccess,
}: {
  children: ReactNode;
  candidateMutationAccess: CandidateMutationAccess;
}) {
  const candidateMutationsAllowed = candidateMutationAccess === "allowed";
  return (
    <AppShellAccessContext.Provider
      value={{
        candidateMutationAccess,
        candidateMutationsAllowed,
      }}
    >
      {children}
    </AppShellAccessContext.Provider>
  );
}

export function useAppShellAccess(): AppShellAccess {
  return useContext(AppShellAccessContext);
}

const RESTRICTION_MESSAGES: Record<Exclude<CandidateMutationAccess, "allowed">, string> = {
  checking: "Candidate changes are unavailable while impersonation status is being verified.",
  unavailable:
    "Candidate changes are unavailable because impersonation status could not be verified.",
  impersonating: "Read-only impersonation is active. Candidate changes are disabled.",
};

type CandidateLinkAccess = "read-only-navigation" | "state-changing";

const STATE_CHANGING_CANDIDATE_GET_ROUTES: readonly RegExp[] = [
  /^\/api\/matches\/[^/]+\/apply-redirect\/?$/,
];

export function classifyCandidateLink(href: string): CandidateLinkAccess {
  try {
    const base = "https://hyrepath.local";
    const target = new URL(href, base);
    const isLocal = href.startsWith("/") && !href.startsWith("//");
    if (!isLocal && target.origin !== base) {
      return "read-only-navigation";
    }
    const pathname = target.pathname;
    return STATE_CHANGING_CANDIDATE_GET_ROUTES.some((route) => route.test(pathname))
      ? "state-changing"
      : "read-only-navigation";
  } catch {
    return "state-changing";
  }
}

const RESTRICTION_EXPLANATION_ID = "candidate-mutation-restriction";

export function CandidatePolicyLink({
  children,
  href,
  className,
  ...props
}: AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) {
  const { candidateMutationsAllowed } = useAppShellAccess();
  const stateChanging = classifyCandidateLink(href) === "state-changing";

  if (stateChanging && !candidateMutationsAllowed) {
    return (
      <span
        role="link"
        aria-disabled="true"
        aria-describedby={RESTRICTION_EXPLANATION_ID}
        className={className}
      >
        {children}
      </span>
    );
  }

  return (
    <a href={href} className={className} {...props}>
      {children}
    </a>
  );
}

export function CandidateMutationBoundary({ children }: { children: ReactNode }) {
  const { candidateMutationAccess } = useAppShellAccess();

  if (candidateMutationAccess === "allowed") {
    return <>{children}</>;
  }

  const blockNonNavigation = (event: SyntheticEvent) => {
    const target = event.target;
    if (target instanceof Element) {
      const anchor = target.closest("a[href]");
      const href = anchor?.getAttribute("href");
      if (href && classifyCandidateLink(href) === "read-only-navigation") {
        return;
      }
    }
    event.preventDefault();
    event.stopPropagation();
  };

  return (
    <>
      <p
        id={RESTRICTION_EXPLANATION_ID}
        role="status"
        aria-live="polite"
        className="mb-4 rounded-md border border-border bg-muted px-4 py-3 text-sm text-muted-foreground"
      >
        {RESTRICTION_MESSAGES[candidateMutationAccess]}
      </p>
      <fieldset
        disabled
        aria-describedby={RESTRICTION_EXPLANATION_ID}
        className="min-w-0 border-0 p-0 disabled:opacity-75"
        onClickCapture={blockNonNavigation}
        onKeyDownCapture={blockNonNavigation}
        onPointerDownCapture={blockNonNavigation}
        onSubmitCapture={blockNonNavigation}
      >
        {children}
      </fieldset>
    </>
  );
}
