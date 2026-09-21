import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { SettingsView } from "@/features/settings";

export default function OsintSettingsPage() {
  return (
    <div className="flex flex-col gap-6">
      <Card className="overflow-hidden">
        <CardHeader className="gap-4 border-b border-border/60 bg-surface-muted/40">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-2">
              <p className="text-[0.7rem] font-semibold uppercase tracking-[0.16em] text-subtle-foreground">
                OSINT operator profile
              </p>
              <CardTitle className="text-xl">
                Keep account controls close to the workbench
              </CardTitle>
              <CardDescription>
                Session, subscription, and security controls stay inside the OSINT shell so staff
                can harden access without losing the context of active research work.
              </CardDescription>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="info">Staff-only</Badge>
              <Badge variant="outline">Security stays local</Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent className="grid gap-3 pt-6 md:grid-cols-2">
          <div className="rounded-xl border border-border/70 bg-surface p-4">
            <p className="text-sm font-medium text-foreground">Session control</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Use the session actions below when a research machine changes hands or an operator
              needs to sign out quickly.
            </p>
          </div>
          <div className="rounded-xl border border-border/70 bg-surface p-4">
            <p className="text-sm font-medium text-foreground">Security handoff</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Two-factor authentication lives on the dedicated security route so it remains one
              click away from the rest of the workbench settings.
            </p>
          </div>
        </CardContent>
      </Card>

      <SettingsView securityHref="/osint/settings/security" showShellHeader={false} />
    </div>
  );
}
