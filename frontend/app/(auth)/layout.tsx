import type { Metadata } from "next";
import { HyrepathLogo } from "@/components/layout/HyrepathLogo";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Authentication - Hyrepath Enrichment",
  description: "Sign in or create an account",
};

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800">
      <div className="absolute top-4 left-4">
        <Link
          href="/"
          className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
        >
          <div className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <HyrepathLogo className="size-5" />
          </div>
          <span className="font-semibold">Hyrepath</span>
        </Link>
      </div>
      {children}
    </div>
  );
}
