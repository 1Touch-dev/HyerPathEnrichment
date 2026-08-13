"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  useAddPortfolioItem,
  useDeletePortfolioItem,
  usePortfolioProfile,
  useSavePortfolioProfile,
} from "../hooks/usePortfolioProfile";
import { SlugField } from "./SlugField";
import type { PortfolioItem } from "@/src/lib/types";

const ITEM_TYPE_LABELS: Record<PortfolioItem["itemType"], string> = {
  github_repo: "GitHub repo",
  live_demo: "Live demo",
  case_study: "Case study",
  other_link: "Other link",
};

export function PortfolioEditor() {
  const { data: profile, isLoading } = usePortfolioProfile();
  const saveProfile = useSavePortfolioProfile();
  const addItem = useAddPortfolioItem();
  const deleteItem = useDeletePortfolioItem();

  const [slug, setSlug] = useState(profile?.slug ?? "");
  const [headline, setHeadline] = useState(profile?.headline ?? "");
  const [summary, setSummary] = useState(profile?.summary ?? "");
  const [isPublished, setIsPublished] = useState(profile?.isPublished ?? false);
  const [newItemUrl, setNewItemUrl] = useState("");
  const [newItemTitle, setNewItemTitle] = useState("");

  if (isLoading) return <div className="animate-pulse h-96 rounded-lg bg-muted" />;

  function handleSave(e: React.FormEvent) {
    e.preventDefault();
    saveProfile.mutate({ slug, headline: headline || null, summary: summary || null, isPublished });
  }

  function handleAddItem(e: React.FormEvent) {
    e.preventDefault();
    if (!newItemUrl.trim() || !newItemTitle.trim()) return;
    addItem.mutate(
      { itemType: "other_link", title: newItemTitle, description: null, url: newItemUrl },
      { onSuccess: () => { setNewItemUrl(""); setNewItemTitle(""); } },
    );
  }

  return (
    <div className="space-y-8">
      <form onSubmit={handleSave} className="space-y-4">
        <SlugField value={slug} onChange={setSlug} />
        <div>
          <Label htmlFor="headline">Headline</Label>
          <Input id="headline" value={headline} onChange={(e) => setHeadline(e.target.value)} maxLength={120} />
        </div>
        <div>
          <Label htmlFor="summary">Summary</Label>
          <Textarea id="summary" value={summary} onChange={(e) => setSummary(e.target.value)} maxLength={2000} rows={4} />
        </div>
        <div className="flex items-center justify-between rounded-lg border p-4">
          <div>
            <Label htmlFor="isPublished">Publish portfolio</Label>
            <p className="text-sm text-muted-foreground">
              Anyone with the link can view it once published.
            </p>
          </div>
          <Switch id="isPublished" checked={isPublished} onCheckedChange={setIsPublished} />
        </div>
        <Button type="submit" disabled={saveProfile.isPending || slug.length < 3}>
          {saveProfile.isPending ? "Saving..." : "Save profile"}
        </Button>
      </form>

      {profile && (
        <div>
          <h3 className="text-sm font-semibold">Portfolio items</h3>
          <ul className="mt-2 space-y-2">
            {profile.items.map((item) => (
              <li key={item.itemId} className="flex items-center justify-between rounded-lg border p-3">
                <div>
                  <p className="text-sm font-medium">{item.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {ITEM_TYPE_LABELS[item.itemType]} · {item.url}
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => deleteItem.mutate(item.itemId)}
                  disabled={deleteItem.isPending}
                >
                  Remove
                </Button>
              </li>
            ))}
          </ul>

          <form onSubmit={handleAddItem} className="mt-3 flex gap-2">
            <Input
              placeholder="Title"
              value={newItemTitle}
              onChange={(e) => setNewItemTitle(e.target.value)}
              className="w-32"
            />
            <Input
              placeholder="https://..."
              value={newItemUrl}
              onChange={(e) => setNewItemUrl(e.target.value)}
              className="flex-1"
            />
            <Button type="submit" disabled={addItem.isPending}>
              Add
            </Button>
          </form>
        </div>
      )}
    </div>
  );
}
