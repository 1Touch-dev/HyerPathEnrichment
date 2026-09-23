"use client";

import { useEffect, useState } from "react";
import { ExternalLink, Globe2, Link2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
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

const ITEM_TYPE_OPTIONS = Object.entries(ITEM_TYPE_LABELS) as [PortfolioItem["itemType"], string][];

export function PortfolioEditor() {
  const { data: profile, isLoading } = usePortfolioProfile();
  const saveProfile = useSavePortfolioProfile();
  const addItem = useAddPortfolioItem();
  const deleteItem = useDeletePortfolioItem();

  const [slug, setSlug] = useState("");
  const [headline, setHeadline] = useState("");
  const [summary, setSummary] = useState("");
  const [isPublished, setIsPublished] = useState(false);
  const [newItemUrl, setNewItemUrl] = useState("");
  const [newItemTitle, setNewItemTitle] = useState("");
  const [newItemType, setNewItemType] = useState<PortfolioItem["itemType"]>("other_link");

  useEffect(() => {
    if (!profile) return;
    setSlug(profile.slug);
    setHeadline(profile.headline ?? "");
    setSummary(profile.summary ?? "");
    setIsPublished(profile.isPublished);
  }, [profile]);

  if (isLoading)
    return (
      <div className="h-96 animate-pulse rounded-xl border border-border/70 bg-surface shadow-panel" />
    );

  function handleSave(e: React.FormEvent) {
    e.preventDefault();
    saveProfile.mutate({ slug, headline: headline || null, summary: summary || null, isPublished });
  }

  function handleAddItem(e: React.FormEvent) {
    e.preventDefault();
    if (!newItemUrl.trim() || !newItemTitle.trim()) return;
    addItem.mutate(
      { itemType: newItemType, title: newItemTitle, description: null, url: newItemUrl },
      {
        onSuccess: () => {
          setNewItemUrl("");
          setNewItemTitle("");
          setNewItemType("other_link");
        },
      },
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={profile?.isPublished ? "success" : "outline"}>
            {profile?.isPublished ? "Published" : "Draft"}
          </Badge>
          <Badge variant="outline">{profile?.items.length ?? 0} items</Badge>
        </div>
        {profile ? (
          <Button asChild size="sm" variant="outline">
            <a href={profile.publicUrl} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="mr-2 h-4 w-4" />
              View public page
            </a>
          </Button>
        ) : (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <span>
                  <Button size="sm" variant="outline" disabled>
                    View public page
                  </Button>
                </span>
              </TooltipTrigger>
              <TooltipContent>Save your profile to get a public link.</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Profile</CardTitle>
            <CardDescription>Control your public URL, headline, and summary.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSave} className="space-y-4">
              <SlugField value={slug} onChange={setSlug} />
              <div>
                <Label htmlFor="headline">Headline</Label>
                <Input
                  id="headline"
                  value={headline}
                  onChange={(e) => setHeadline(e.target.value)}
                  maxLength={120}
                />
              </div>
              <div>
                <Label htmlFor="summary">Summary</Label>
                <Textarea
                  id="summary"
                  value={summary}
                  onChange={(e) => setSummary(e.target.value)}
                  maxLength={2000}
                  rows={4}
                />
              </div>
              <div className="flex items-center justify-between rounded-xl border border-border/70 bg-surface p-4">
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
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Public link</CardTitle>
            <CardDescription>Keep the shareable version honest and easy to scan.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-xl border border-border/70 bg-surface p-4 text-sm text-muted-foreground">
              <div className="mb-2 flex items-center gap-2 font-medium text-foreground">
                <Globe2 className="h-4 w-4 text-primary" />
                Visibility
              </div>
              {profile?.isPublished
                ? "Your public page is live and ready to share."
                : "Your profile stays private until you publish it."}
            </div>
            <div className="rounded-xl border border-border/70 bg-surface p-4 text-sm text-muted-foreground">
              <div className="mb-2 flex items-center gap-2 font-medium text-foreground">
                <Link2 className="h-4 w-4 text-primary" />
                URL preview
              </div>
              {slug.length >= 3 ? `/p/${slug}` : "Pick a slug with at least 3 characters."}
            </div>
          </CardContent>
        </Card>
      </div>

      {profile && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Portfolio items</CardTitle>
            <CardDescription>Add links that strengthen your public profile.</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {profile.items.map((item) => (
                <li
                  key={item.itemId}
                  className="flex items-center justify-between rounded-xl border border-border/70 bg-surface p-3"
                >
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

            <form onSubmit={handleAddItem} className="mt-4 flex flex-col gap-2 md:flex-row">
              <Select
                value={newItemType}
                onValueChange={(v) => setNewItemType(v as PortfolioItem["itemType"])}
              >
                <SelectTrigger className="w-full md:w-40" aria-label="Item type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ITEM_TYPE_OPTIONS.map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Input
                placeholder="Title"
                value={newItemTitle}
                onChange={(e) => setNewItemTitle(e.target.value)}
                className="w-full md:w-48"
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
          </CardContent>
        </Card>
      )}
    </div>
  );
}
