"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { usePreferences, useUpdatePreferences } from "../hooks/usePreferences";

export function PreferencesForm() {
  const { data: preferences, isLoading } = usePreferences();
  const updateMutation = useUpdatePreferences();

  const [salaryMin, setSalaryMin] = useState(preferences?.salaryMin?.toString() ?? "");
  const [salaryMax, setSalaryMax] = useState(preferences?.salaryMax?.toString() ?? "");
  const [remotePreference, setRemotePreference] = useState(preferences?.remotePreference ?? "");
  const [isScanEnabled, setIsScanEnabled] = useState(preferences?.isScanEnabled ?? true);

  if (isLoading) return <div className="animate-pulse h-64 rounded-lg bg-muted" />;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    updateMutation.mutate({
      salaryMin: salaryMin ? Number(salaryMin) : null,
      salaryMax: salaryMax ? Number(salaryMax) : null,
      remotePreference: remotePreference
        ? (remotePreference as "remote" | "hybrid" | "onsite")
        : null,
      isScanEnabled,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label htmlFor="salaryMin">Minimum salary</Label>
          <Input
            id="salaryMin"
            type="number"
            value={salaryMin}
            onChange={(e) => setSalaryMin(e.target.value)}
          />
        </div>
        <div>
          <Label htmlFor="salaryMax">Maximum salary</Label>
          <Input
            id="salaryMax"
            type="number"
            value={salaryMax}
            onChange={(e) => setSalaryMax(e.target.value)}
          />
        </div>
      </div>

      <div>
        <Label htmlFor="remotePreference">Work arrangement</Label>
        <Select value={remotePreference} onValueChange={setRemotePreference}>
          <SelectTrigger id="remotePreference">
            <SelectValue placeholder="No preference" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="remote">Remote</SelectItem>
            <SelectItem value="hybrid">Hybrid</SelectItem>
            <SelectItem value="onsite">Onsite</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="flex items-center justify-between rounded-lg border p-4">
        <div>
          <Label htmlFor="scanEnabled">Daily job scan</Label>
          <p className="text-sm text-muted-foreground">
            Scan job boards daily and email you the top matches.
          </p>
        </div>
        <Switch id="scanEnabled" checked={isScanEnabled} onCheckedChange={setIsScanEnabled} />
      </div>

      <div className="flex items-center justify-between rounded-lg border border-dashed p-4 opacity-60">
        <div>
          <Label>SMS notifications</Label>
          <p className="text-sm text-muted-foreground">Coming soon.</p>
        </div>
        <Switch disabled checked={false} />
      </div>

      <Button type="submit" disabled={updateMutation.isPending}>
        {updateMutation.isPending ? "Saving..." : "Save preferences"}
      </Button>
    </form>
  );
}
