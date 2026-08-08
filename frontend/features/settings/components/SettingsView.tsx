"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { LogOut, Trash2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export function SettingsView() {
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
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground">Manage your account and preferences.</p>
      </div>

      {/* Profile Section */}
      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardDescription>Your account information</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 max-w-md">
          <div className="flex flex-col gap-2">
            <Label>Name</Label>
            <Input disabled value={user ? `${user.first_name} ${user.last_name}` : ""} />
          </div>
          <div className="flex flex-col gap-2">
            <Label>Email</Label>
            <div className="flex items-center gap-2">
              <Input disabled value={user?.email || ""} />
              {user?.is_verified ? (
                <Badge variant="default" className="shrink-0">
                  Verified
                </Badge>
              ) : (
                <Badge variant="secondary" className="shrink-0">
                  Unverified
                </Badge>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* General Settings */}
      <Card>
        <CardHeader>
          <CardTitle>General</CardTitle>
          <CardDescription>Default mode and integration base.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 max-w-md">
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

      {/* Session Section */}
      <Card>
        <CardHeader>
          <CardTitle>Session</CardTitle>
          <CardDescription>Manage your current session</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 max-w-md">
          <Button onClick={handleLogout} variant="outline" className="w-full justify-start">
            <LogOut className="mr-2 h-4 w-4" />
            Logout
          </Button>
          <p className="text-sm text-gray-600">
            End your current session. You can login again anytime.
          </p>
        </CardContent>
      </Card>

      {/* Danger Zone */}
      <Card className="border-red-200">
        <CardHeader>
          <CardTitle className="text-red-600">Danger Zone</CardTitle>
          <CardDescription>Irreversible and destructive actions</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 max-w-md">
          <Button
            onClick={() => setShowDeleteDialog(true)}
            variant="destructive"
            className="w-full justify-start"
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Delete Account
          </Button>
          <p className="text-sm text-gray-600">
            Permanently delete your account. This cannot be undone without contacting support.
          </p>
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Are you absolutely sure?</DialogTitle>
            <DialogDescription>
              This will permanently delete your account and all associated data. You will not be
              able to login again unless you contact support.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
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
