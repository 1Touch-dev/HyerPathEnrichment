"use client";

import { useState } from "react";
import { EmptyState } from "@/components/console/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { AdminPortfolioProfile } from "@/src/lib/types";
import type { AdminPortfolioFilters } from "../api/client";
import {
  useAdminPortfolioProfiles,
  useModeratePortfolioProfile,
} from "../hooks/usePortfolioModeration";

type PublishedFilter = "all" | "published" | "unpublished";
type VisibilityFilter = "all" | "hidden" | "visible";

function toIsPublished(filter: PublishedFilter): boolean | null {
  if (filter === "published") return true;
  if (filter === "unpublished") return false;
  return null;
}

function toAdminHidden(filter: VisibilityFilter): boolean | null {
  if (filter === "hidden") return true;
  if (filter === "visible") return false;
  return null;
}

/**
 * Cursor-paginated portfolio moderation table, following UsersTable.tsx's
 * cursor-stack pagination pattern (Decision 4 — no page-number UI). The
 * moderate action follows UsersTable's handleToggleStatus: no client-side
 * permission gating, the backend enforces portfolio:moderate via 403.
 */
export function PortfolioModerationPanel() {
  const [publishedFilter, setPublishedFilter] = useState<PublishedFilter>("all");
  const [visibilityFilter, setVisibilityFilter] = useState<VisibilityFilter>("all");
  const [cursorStack, setCursorStack] = useState<(string | null)[]>([null]);

  const cursor = cursorStack[cursorStack.length - 1];
  const filters: AdminPortfolioFilters = {
    isPublished: toIsPublished(publishedFilter),
    adminHidden: toAdminHidden(visibilityFilter),
  };

  const { data, isLoading } = useAdminPortfolioProfiles(cursor, filters);
  const moderate = useModeratePortfolioProfile();

  function handlePublishedFilterChange(value: string) {
    setPublishedFilter(value as PublishedFilter);
    setCursorStack([null]);
  }

  function handleVisibilityFilterChange(value: string) {
    setVisibilityFilter(value as VisibilityFilter);
    setCursorStack([null]);
  }

  function handleNext() {
    if (data?.nextCursor) {
      setCursorStack((stack) => [...stack, data.nextCursor]);
    }
  }

  function handlePrevious() {
    setCursorStack((stack) => (stack.length > 1 ? stack.slice(0, -1) : stack));
  }

  function handleToggleHidden(profile: AdminPortfolioProfile) {
    const nextAdminHidden = !profile.adminHidden;
    const confirmed = window.confirm(
      nextAdminHidden ? `Hide portfolio "${profile.slug}"?` : `Unhide portfolio "${profile.slug}"?`,
    );
    if (!confirmed) return;
    moderate.mutate({ profileId: profile.profileId, adminHidden: nextAdminHidden });
  }

  const items = data?.items ?? [];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <Select value={publishedFilter} onValueChange={handlePublishedFilterChange}>
          <SelectTrigger className="w-[180px]" aria-label="Filter by published status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All profiles</SelectItem>
            <SelectItem value="published">Published</SelectItem>
            <SelectItem value="unpublished">Unpublished</SelectItem>
          </SelectContent>
        </Select>
        <Select value={visibilityFilter} onValueChange={handleVisibilityFilterChange}>
          <SelectTrigger className="w-[180px]" aria-label="Filter by moderation status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All visibility</SelectItem>
            <SelectItem value="hidden">Hidden</SelectItem>
            <SelectItem value="visible">Visible</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {!items.length && !isLoading ? (
        <EmptyState title="No portfolio profiles found" description="Try a different filter." />
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Slug</TableHead>
                <TableHead>Display name</TableHead>
                <TableHead>Published</TableHead>
                <TableHead>Moderation</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((profile) => (
                <TableRow key={profile.profileId}>
                  <TableCell className="font-mono text-sm">{profile.slug}</TableCell>
                  <TableCell>{profile.displayName ?? "—"}</TableCell>
                  <TableCell>
                    <Badge variant={profile.isPublished ? "success" : "outline"}>
                      {profile.isPublished ? "Published" : "Unpublished"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant={profile.adminHidden ? "warning" : "success"}>
                      {profile.adminHidden ? "Hidden" : "Visible"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={moderate.isPending}
                      onClick={() => handleToggleHidden(profile)}
                    >
                      {profile.adminHidden ? "Unhide" : "Hide"}
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <div className="flex items-center justify-end gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={cursorStack.length <= 1 || isLoading}
          onClick={handlePrevious}
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={!data?.hasMore || isLoading}
          onClick={handleNext}
        >
          Next page
        </Button>
      </div>
    </div>
  );
}
