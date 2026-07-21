"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function SettingsView() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Defaults for lookups and operational integrations.
        </p>
      </div>

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
    </div>
  );
}
