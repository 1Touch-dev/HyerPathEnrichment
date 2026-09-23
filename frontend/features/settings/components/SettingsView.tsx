"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import { SubscriptionCard } from "@/features/billing";
import {
  ShellPageHeader,
  ShellPageHeaderActions,
  ShellPageHeaderContent,
  ShellPageHeaderDescription,
  ShellPageHeaderEyebrow,
  ShellPageHeaderTitle,
} from "@/components/layout/ShellPage";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { LogOut, ShieldCheck, Trash2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type SettingsViewProps = {
  securityHref?: string;
  showShellHeader?: boolean;
};

export function SettingsView({
  securityHref = "/app/settings/security",
  showShellHeader = true,
}: SettingsViewProps) {
  const router = useRouter();
  const { user, logout, deleteAccount } = useAuth();
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  const handleDeleteAccount = async () => {
    setDeleting(true);
    try {
      await deleteAccount();
      router.push("/login?deleted=true");
    } catch (error) {
      console.error("Failed to delete account:", error);
      alert("Failed to delete account. Please try again.");
    } finally {
      setDeleting(false);
      setShowDeleteDialog(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      {showShellHeader ? (
        <ShellPageHeader>
          <ShellPageHeaderContent>
            <ShellPageHeaderEyebrow>Candidate workspace</ShellPageHeaderEyebrow>
            <ShellPageHeaderTitle>Settings</ShellPageHeaderTitle>
            <ShellPageHeaderDescription>
              Manage your account, security setup, and subscription details without drifting into
              staff-only controls.
            </ShellPageHeaderDescription>
          </ShellPageHeaderContent>
          <ShellPageHeaderActions className="items-start sm:items-center">
            <Badge variant={user?.is_verified ? "success" : "warning"}>
              {user?.is_verified ? "Email verified" : "Verification pending"}
            </Badge>
          </ShellPageHeaderActions>
        </ShellPageHeader>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Profile</CardTitle>
              <CardDescription>Your account information</CardDescription>
            </CardHeader>
            <CardContent className="grid max-w-md gap-4">
              <div className="flex flex-col gap-2">
                <Label>Name</Label>
                <Input disabled value={user ? `${user.first_name} ${user.last_name}` : ""} />
              </div>
              <div className="flex flex-col gap-2">
                <Label>Email</Label>
                <div className="flex items-center gap-2">
                  <Input disabled value={user?.email || ""} />
                  {user?.is_verified ? (
                    <Badge variant="success" className="shrink-0">
                      Verified
                    </Badge>
                  ) : (
                    <Badge variant="warning" className="shrink-0">
                      Unverified
                    </Badge>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          <SubscriptionCard />

          <Card>
            <CardHeader>
              <CardTitle>General</CardTitle>
              <CardDescription>Default mode and integration base.</CardDescription>
            </CardHeader>
            <CardContent className="grid max-w-md gap-4">
              <div className="flex flex-col gap-2">
                <Label htmlFor="default-mode">Default enrich mode</Label>
                <Input id="default-mode" disabled value="async (coming soon)" />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="api-base">API base</Label>
                <Input
                  id="api-base"
                  disabled
                  value="BFF /api/* (configured server-side)"
                  className="font-mono text-xs"
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Security</CardTitle>
              <CardDescription>Two-factor authentication and account security.</CardDescription>
            </CardHeader>
            <CardContent>
              <Button asChild variant="outline" className="w-fit">
                <Link href={securityHref}>
                  <ShieldCheck className="mr-2 h-4 w-4" />
                  Manage two-factor authentication
                </Link>
              </Button>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Session</CardTitle>
              <CardDescription>Manage your current session</CardDescription>
            </CardHeader>
            <CardContent className="max-w-md space-y-4">
              <Button onClick={handleLogout} variant="outline" className="w-full justify-start">
                <LogOut className="mr-2 h-4 w-4" />
                Logout
              </Button>
              <p className="text-sm text-muted-foreground">
                End your current session. You can login again anytime.
              </p>
            </CardContent>
          </Card>

          <Card className="border-destructive/20 bg-surface">
            <CardHeader>
              <CardTitle className="text-destructive">Danger Zone</CardTitle>
              <CardDescription>Irreversible and destructive actions</CardDescription>
            </CardHeader>
            <CardContent className="max-w-md space-y-4">
              <Button
                onClick={() => setShowDeleteDialog(true)}
                variant="destructive"
                className="w-full justify-start"
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete Account
              </Button>
              <p className="text-sm text-muted-foreground">
                Permanently delete your account. This cannot be undone without contacting support.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>

      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent className="gap-0 overflow-hidden border-border/70 p-0 sm:max-w-md">
          <div className="border-b border-border/60 bg-primary-soft/50 px-6 py-5">
            <DialogHeader className="space-y-2 text-left">
              <p className="text-[0.7rem] font-semibold uppercase tracking-[0.16em] text-destructive">
                Danger zone
              </p>
              <DialogTitle>Are you absolutely sure?</DialogTitle>
              <DialogDescription>
                This will permanently delete your account and all associated data. You will not be
                able to login again unless you contact support.
              </DialogDescription>
            </DialogHeader>
          </div>
          <DialogFooter className="gap-2 bg-card px-6 py-5 sm:justify-end sm:gap-2">
            <Button variant="outline" onClick={() => setShowDeleteDialog(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDeleteAccount} disabled={deleting}>
              {deleting ? "Deleting..." : "Yes, delete my account"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
