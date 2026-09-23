import type { Metadata } from "next";
import { HyrepathLogo } from "@/components/layout/HyrepathLogo";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Authentication - Hyrepath Enrichment",
  description: "Sign in or create an account",
};

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="absolute left-4 top-4 z-10 sm:left-6 sm:top-6">
        <Link
          href="/"
          className="flex items-center gap-2.5 text-muted-foreground transition-colors hover:text-foreground"
        >
          <div className="flex size-9 items-center justify-center rounded-xl bg-primary-soft text-primary">
            <HyrepathLogo className="size-5" />
          </div>
          <span className="text-sm font-semibold tracking-tight text-primary">Hyrepath</span>
        </Link>
      </div>
      {children}
    </div>
  );
}
