"use client";

import { useState } from "react";
import { EmptyState } from "@/components/console/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { useFeatureFlags, useUpsertFeatureFlag } from "../hooks/useFeatureFlags";

/**
 * Toggle-then-confirm UX, matching PreferencesForm.tsx's notification-channel
 * switches: the switch flips immediately, backed by an optimistic mutation
 * that reverts (via query invalidation) if the request fails.
 */
export function FeatureFlagsPanel() {
  const { data: flags, isLoading } = useFeatureFlags();
  const upsertFlag = useUpsertFeatureFlag();

  const [createOpen, setCreateOpen] = useState(false);
  const [newKey, setNewKey] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);

  function handleToggle(key: string, enabled: boolean) {
    upsertFlag.mutate({ key, payload: { enabled } });
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreateError(null);
    if (!newKey.trim()) {
      setCreateError("Key is required.");
      return;
    }
    try {
      await upsertFlag.mutateAsync({
        key: newKey.trim(),
        payload: { enabled: false, description: newDescription.trim() || null },
      });
      setCreateOpen(false);
      setNewKey("");
      setNewDescription("");
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Failed to create flag.");
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-end">
        <Button onClick={() => setCreateOpen(true)}>Create flag</Button>
      </div>

      {!flags?.length && !isLoading ? (
        <EmptyState
          title="No feature flags yet"
          description="Create one to gate a feature without a deploy."
        />
      ) : (
        <div className="flex flex-col gap-2">
          {(flags ?? []).map((flag) => (
            <div
              key={flag.key}
              className="flex items-center justify-between rounded-lg border p-4"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm font-medium">{flag.key}</span>
                  {flag.updatedBy ? (
                    <Badge variant="outline" className="text-[10px]">
                      updated by {flag.updatedBy}
                    </Badge>
                  ) : null}
                </div>
                {flag.description ? (
                  <p className="text-sm text-muted-foreground">{flag.description}</p>
                ) : null}
              </div>
              <Switch
                checked={flag.enabled}
                onCheckedChange={(checked) => handleToggle(flag.key, checked)}
                aria-label={`Toggle ${flag.key}`}
              />
            </div>
          ))}
        </div>
      )}

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create feature flag</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <Label htmlFor="flag-key">Key</Label>
              <Input
                id="flag-key"
                placeholder="e.g. new_matching_algorithm"
                value={newKey}
                onChange={(e) => setNewKey(e.target.value)}
                required
              />
            </div>
            <div>
              <Label htmlFor="flag-description">Description</Label>
              <Textarea
                id="flag-description"
                placeholder="What does this flag control?"
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
              />
            </div>
            {createError ? <p className="text-sm text-destructive">{createError}</p> : null}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setCreateOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={upsertFlag.isPending}>
                {upsertFlag.isPending ? "Creating…" : "Create flag"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
