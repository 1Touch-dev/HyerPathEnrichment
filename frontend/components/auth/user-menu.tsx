"use client";

import { useRouter } from "next/navigation";
import { useAuth } from "@/providers/auth-provider";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { User, Settings, LogOut, Mail } from "lucide-react";
import { Separator } from "@/components/ui/separator";

export function UserMenu() {
  const router = useRouter();
  const { user, logout } = useAuth();

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  if (!user) {
    return null;
  }

  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="ghost" size="sm" className="gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary">
            <User className="h-4 w-4" />
          </div>
          <span className="hidden md:inline-block">{user.first_name}</span>
        </Button>
      </SheetTrigger>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>Account</SheetTitle>
        </SheetHeader>
        <div className="mt-6 space-y-4">
          <div className="rounded-lg bg-muted/50 p-4">
            <div className="flex items-start justify-between">
              <div>
                <p className="font-medium">
                  {user.first_name} {user.last_name}
                </p>
                <p className="text-sm text-muted-foreground">{user.email}</p>
              </div>
              {user.is_verified ? (
                <Badge variant="default" className="text-xs">
                  Verified
                </Badge>
              ) : (
                <Badge variant="secondary" className="text-xs">
                  Unverified
                </Badge>
              )}
            </div>
            {!user.is_verified && (
              <div className="mt-3 flex items-center gap-2 text-xs text-yellow-600">
                <Mail className="h-3 w-3" />
                <span>Please verify your email</span>
              </div>
            )}
          </div>

          <Separator />

          <div className="space-y-2">
            <Button
              variant="ghost"
              className="w-full justify-start"
              onClick={() => router.push("/app/settings")}
            >
              <Settings className="mr-2 h-4 w-4" />
              Settings
            </Button>
            <Button
              variant="ghost"
              className="w-full justify-start text-destructive hover:text-destructive"
              onClick={handleLogout}
            >
              <LogOut className="mr-2 h-4 w-4" />
              Logout
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
