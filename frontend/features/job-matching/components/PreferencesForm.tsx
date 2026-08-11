"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import { usePushSubscription } from "../hooks/usePushSubscription";

const NOTIFICATION_CHANNELS = [
  { value: "email", label: "Email", enabled: true },
  { value: "sms", label: "SMS", enabled: false },
  { value: "webhook", label: "Webhook", enabled: true },
  { value: "push", label: "Push", enabled: true },
] as const;

const DISABLED_CHANNEL_REASON: Record<string, string> = {
  sms: "Coming soon.",
  push: "Not supported in this browser.",
};

function splitCommaSeparated(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function PreferencesForm() {
  const { data: preferences, isLoading } = usePreferences();
  const updateMutation = useUpdatePreferences();
  const pushSubscription = usePushSubscription();

  const [salaryMin, setSalaryMin] = useState(preferences?.salaryMin?.toString() ?? "");
  const [salaryMax, setSalaryMax] = useState(preferences?.salaryMax?.toString() ?? "");
  const [remotePreference, setRemotePreference] = useState(preferences?.remotePreference ?? "");
  const [isScanEnabled, setIsScanEnabled] = useState(preferences?.isScanEnabled ?? true);
  const [desiredRoles, setDesiredRoles] = useState(preferences?.desiredRoles?.join(", ") ?? "");
  const [desiredLocations, setDesiredLocations] = useState(
    preferences?.desiredLocations?.join(", ") ?? "",
  );
  const [notificationChannels, setNotificationChannels] = useState<string[]>(
    preferences?.notificationChannels ?? ["email"],
  );
  const [webhookUrl, setWebhookUrl] = useState(preferences?.webhookUrl ?? "");
  const [digestFrequency, setDigestFrequency] = useState(preferences?.digestFrequency ?? "daily");
  const [pushError, setPushError] = useState<string | null>(null);

  if (isLoading) return <div className="animate-pulse h-64 rounded-lg bg-muted" />;

  function toggleChannel(channel: string, checked: boolean) {
    setNotificationChannels((prev) =>
      checked ? [...new Set([...prev, channel])] : prev.filter((c) => c !== channel),
    );
  }

  async function handlePushToggle(checked: boolean) {
    setPushError(null);

    if (!checked) {
      toggleChannel("push", false);
      try {
        await pushSubscription.unsubscribe();
      } catch {
        // Best-effort — the box is already unchecked regardless of cleanup outcome.
      }
      return;
    }

    try {
      await pushSubscription.subscribe();
      toggleChannel("push", true);
    } catch (err) {
      setPushError(err instanceof Error ? err.message : "Failed to enable push notifications.");
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    updateMutation.mutate({
      desiredRoles: splitCommaSeparated(desiredRoles),
      desiredLocations: splitCommaSeparated(desiredLocations),
      salaryMin: salaryMin ? Number(salaryMin) : null,
      salaryMax: salaryMax ? Number(salaryMax) : null,
      remotePreference: remotePreference
        ? (remotePreference as "remote" | "hybrid" | "onsite")
        : null,
      notificationChannels: notificationChannels as ("email" | "sms" | "webhook" | "push")[],
      webhookUrl: webhookUrl.trim() ? webhookUrl.trim() : null,
      digestFrequency: digestFrequency as "daily" | "weekly" | "off",
      isScanEnabled,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div>
        <Label htmlFor="desiredRoles">Desired roles</Label>
        <Input
          id="desiredRoles"
          placeholder="e.g. Backend Engineer, Staff Engineer"
          value={desiredRoles}
          onChange={(e) => setDesiredRoles(e.target.value)}
        />
        <p className="text-sm text-muted-foreground">Comma-separated, most preferred first.</p>
      </div>

      <div>
        <Label htmlFor="desiredLocations">Desired locations</Label>
        <Input
          id="desiredLocations"
          placeholder="e.g. New York, NY, Remote"
          value={desiredLocations}
          onChange={(e) => setDesiredLocations(e.target.value)}
        />
        <p className="text-sm text-muted-foreground">Comma-separated.</p>
      </div>

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

      <div>
        <Label htmlFor="digestFrequency">Digest frequency</Label>
        <Select
          value={digestFrequency}
          onValueChange={(value) => setDigestFrequency(value as "daily" | "weekly" | "off")}
        >
          <SelectTrigger id="digestFrequency">
            <SelectValue placeholder="Daily" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="daily">Daily</SelectItem>
            <SelectItem value="weekly">Weekly</SelectItem>
            <SelectItem value="off">Off</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label>Notification channels</Label>
        {NOTIFICATION_CHANNELS.map((channel) => {
          const isPush = channel.value === "push";
          const isEnabled = isPush
            ? channel.enabled && pushSubscription.isSupported
            : channel.enabled;

          return (
            <div key={channel.value}>
              <div
                className={
                  isEnabled
                    ? "flex items-center gap-2"
                    : "flex items-center justify-between rounded-lg border border-dashed p-4 opacity-60"
                }
              >
                {isEnabled ? (
                  <>
                    <Checkbox
                      id={`channel-${channel.value}`}
                      checked={notificationChannels.includes(channel.value)}
                      onCheckedChange={(checked) =>
                        isPush
                          ? handlePushToggle(checked === true)
                          : toggleChannel(channel.value, checked === true)
                      }
                    />
                    <Label htmlFor={`channel-${channel.value}`}>{channel.label}</Label>
                  </>
                ) : (
                  <>
                    <div>
                      <Label>{channel.label} notifications</Label>
                      <p className="text-sm text-muted-foreground">
                        {DISABLED_CHANNEL_REASON[channel.value] ?? "Coming soon."}
                      </p>
                    </div>
                    <Switch disabled checked={false} />
                  </>
                )}
              </div>
              {isPush && pushError && <p className="pl-6 text-sm text-destructive">{pushError}</p>}
            </div>
          );
        })}

        {notificationChannels.includes("webhook") && (
          <div className="pl-6">
            <Label htmlFor="webhookUrl">Webhook URL</Label>
            <Input
              id="webhookUrl"
              type="url"
              placeholder="https://example.com/webhooks/job-matches"
              value={webhookUrl}
              onChange={(e) => setWebhookUrl(e.target.value)}
            />
            <p className="text-sm text-muted-foreground">
              We&apos;ll POST your top matches here on every digest.
            </p>
          </div>
        )}
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

      <Button type="submit" disabled={updateMutation.isPending}>
        {updateMutation.isPending ? "Saving..." : "Save preferences"}
      </Button>
    </form>
  );
}
