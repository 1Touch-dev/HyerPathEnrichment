"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
import { toast } from "sonner";
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

  const [salaryMin, setSalaryMin] = useState("");
  const [salaryMax, setSalaryMax] = useState("");
  const [remotePreference, setRemotePreference] = useState("");
  const [isScanEnabled, setIsScanEnabled] = useState(true);
  const [desiredRoles, setDesiredRoles] = useState("");
  const [desiredLocations, setDesiredLocations] = useState("");
  const [notificationChannels, setNotificationChannels] = useState<string[]>(["email"]);
  const [webhookUrl, setWebhookUrl] = useState("");
  const [digestFrequency, setDigestFrequency] = useState<"daily" | "weekly" | "off">("daily");
  const [pushError, setPushError] = useState<string | null>(null);

  useEffect(() => {
    if (!preferences) return;
    setSalaryMin(preferences.salaryMin?.toString() ?? "");
    setSalaryMax(preferences.salaryMax?.toString() ?? "");
    setRemotePreference(preferences.remotePreference ?? "");
    setIsScanEnabled(preferences.isScanEnabled ?? true);
    setDesiredRoles(preferences.desiredRoles?.join(", ") ?? "");
    setDesiredLocations(preferences.desiredLocations?.join(", ") ?? "");
    setNotificationChannels(preferences.notificationChannels ?? ["email"]);
    setWebhookUrl(preferences.webhookUrl ?? "");
    setDigestFrequency(preferences.digestFrequency ?? "daily");
  }, [preferences]);

  if (isLoading)
    return (
      <div className="h-64 animate-pulse rounded-xl border border-border/70 bg-surface shadow-panel" />
    );

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
    updateMutation.mutate(
      {
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
      },
      {
        onSuccess: () => toast.success("Preferences saved"),
        onError: () => toast.error("Couldn't save preferences"),
      },
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="flex flex-wrap items-center gap-2">
        {preferences?.sourceDocumentId ? (
          <Link href={`/app/documents/${preferences.sourceDocumentId}`}>
            <Badge variant="secondary">Source CV: {preferences.sourceDocumentId}</Badge>
          </Link>
        ) : (
          <Badge variant="outline">No source CV linked yet</Badge>
        )}
        <Badge variant={isScanEnabled ? "success" : "outline"}>
          {isScanEnabled ? "Daily scan on" : "Daily scan off"}
        </Badge>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Role targeting</CardTitle>
            <CardDescription>
              Tell job matching what a strong role looks like for you.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="desiredRoles">Desired roles</Label>
              <Input
                id="desiredRoles"
                placeholder="e.g. Backend Engineer, Staff Engineer"
                value={desiredRoles}
                onChange={(e) => setDesiredRoles(e.target.value)}
              />
              <p className="text-sm text-muted-foreground">
                Comma-separated, most preferred first.
              </p>
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
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Compensation and cadence</CardTitle>
            <CardDescription>
              Set the pay range and how often updates should arrive.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
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

            <div className="flex items-center justify-between rounded-xl border border-border/70 bg-surface p-4">
              <div>
                <Label htmlFor="scanEnabled">Daily job scan</Label>
                <p className="text-sm text-muted-foreground">
                  Scan job boards daily and email you the top matches.
                </p>
              </div>
              <Switch id="scanEnabled" checked={isScanEnabled} onCheckedChange={setIsScanEnabled} />
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Notification channels</CardTitle>
          <CardDescription>Choose how match updates should reach you.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
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
                      ? "flex items-center gap-2 rounded-xl border border-border/70 bg-surface px-4 py-3"
                      : "flex items-center justify-between rounded-xl border border-dashed border-border/70 bg-surface px-4 py-3 opacity-60"
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
                {isPush && pushError ? (
                  <p className="pl-6 text-sm text-destructive">{pushError}</p>
                ) : null}
              </div>
            );
          })}

          {notificationChannels.includes("webhook") ? (
            <div className="rounded-xl border border-border/70 bg-surface p-4">
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
          ) : null}
        </CardContent>
      </Card>

      <Button type="submit" disabled={updateMutation.isPending}>
        {updateMutation.isPending ? "Saving..." : "Save preferences"}
      </Button>
    </form>
  );
}
