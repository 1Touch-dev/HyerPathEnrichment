"use client";

import { useCallback } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import type { ApplicationStatus } from "@/src/lib/types";

const STATUS_OPTIONS: { value: ApplicationStatus | "all"; label: string }[] = [
  { value: "all", label: "All statuses" },
  { value: "new", label: "New" },
  { value: "applied", label: "Applied" },
  { value: "replied", label: "Replied" },
  { value: "interview", label: "Interview" },
  { value: "offer", label: "Offer" },
  { value: "rejected", label: "Rejected" },
];

const SORT_OPTIONS: { value: string; label: string }[] = [
  { value: "newest", label: "Newest" },
  { value: "oldest", label: "Oldest" },
  { value: "score", label: "Score" },
  { value: "recently_updated", label: "Recently updated" },
];

/**
 * Filter state lives entirely in URL search params (`?status=interview&sort=score`)
 * rather than component state, so the tracker view is linkable/shareable/back-button-safe
 * (§7.6). Changing a filter replaces the current history entry (not push) so the browser
 * back button steps out of the tracker rather than through every filter change.
 */
export function TrackerFilterBar() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const status = searchParams.get("status") ?? "all";
  const sort = searchParams.get("sort") ?? "newest";

  const setParam = useCallback(
    (key: string, value: string) => {
      const params = new URLSearchParams(searchParams.toString());
      if (value === "all") {
        params.delete(key);
      } else {
        params.set(key, value);
      }
      const query = params.toString();
      router.replace(query ? `${pathname}?${query}` : pathname);
    },
    [pathname, router, searchParams],
  );

  return (
    <div className="flex flex-wrap items-end gap-4">
      <div>
        <Label htmlFor="tracker-status-filter">Status</Label>
        <Select value={status} onValueChange={(value) => setParam("status", value)}>
          <SelectTrigger id="tracker-status-filter" className="w-[180px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div>
        <Label htmlFor="tracker-sort">Sort</Label>
        <Select value={sort} onValueChange={(value) => setParam("sort", value)}>
          <SelectTrigger id="tracker-sort" className="w-[180px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {SORT_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
