import Link from "next/link";
import { ArrowLeft, LockKeyhole } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  PageHeader,
  PageHeaderActions,
  PageHeaderContent,
  PageHeaderDescription,
  PageHeaderEyebrow,
  PageHeaderTitle,
} from "@/components/ui/page-header";
import { MfaSetupCard } from "@/features/admin";

export default function OsintSecuritySettingsPage() {
  return (
    <div className="flex flex-col gap-6">
      <Button asChild variant="ghost" className="w-fit">
        <Link href="/osint/settings">
          <ArrowLeft className="mr-2 size-4" />
          Back to settings
        </Link>
      </Button>

      <PageHeader>
        <PageHeaderContent>
          <PageHeaderEyebrow>OSINT security</PageHeaderEyebrow>
          <PageHeaderTitle>Protect staff research sessions</PageHeaderTitle>
          <PageHeaderDescription>
            Lock down operator access with multi-factor authentication before opening sensitive
            public-web research or leaving an authenticated workstation unattended.
          </PageHeaderDescription>
        </PageHeaderContent>
        <PageHeaderActions className="items-start sm:items-center">
          <Badge variant="info">Staff access</Badge>
          <Badge variant="success">MFA available</Badge>
        </PageHeaderActions>
      </PageHeader>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0 space-y-6">
          <Alert variant="info">
            <LockKeyhole className="h-4 w-4" />
            <AlertTitle>Harden operator access</AlertTitle>
            <AlertDescription>
              Use MFA on any machine that can open staff-only routes, inspect stored dossiers, or
              trigger new OSINT jobs.
            </AlertDescription>
          </Alert>

          <MfaSetupCard />
        </div>

        <div className="flex flex-col gap-6">
          <Card className="overflow-hidden border-border/70 bg-card shadow-sm">
            <CardHeader className="gap-3 border-b border-border/60 bg-primary-soft/40">
              <p className="text-[0.7rem] font-semibold uppercase tracking-[0.16em] text-primary">
                Operator guidance
              </p>
              <CardTitle className="text-xl">Why this matters</CardTitle>
              <CardDescription>
                Research tooling often stays open for long stretches. Strong session protection
                reduces accidental access when the queue is still live.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 pt-6">
              <div className="rounded-xl border border-border/70 bg-card p-4">
                <p className="text-sm font-medium text-foreground">Shared environments</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  MFA helps when operators switch machines, borrow workstations, or leave an active
                  session behind.
                </p>
              </div>
              <div className="rounded-xl border border-border/70 bg-card p-4">
                <p className="text-sm font-medium text-foreground">Sensitive outcomes</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  The same account can inspect dossiers, review identifiers, and launch new jobs, so
                  the staff shell should stay harder to reuse.
                </p>
              </div>
            </CardContent>
          </Card>

          <Card className="border-border/70 bg-card shadow-sm">
            <CardContent className="space-y-3 p-5">
              <p className="text-sm font-medium text-foreground">Need another account change?</p>
              <p className="text-sm text-muted-foreground">
                Session controls, account metadata, and subscription details remain on the parent
                settings route.
              </p>
              <Button asChild variant="outline" className="w-full justify-center">
                <Link href="/osint/settings">Return to settings</Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
