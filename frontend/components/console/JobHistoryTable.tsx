"use client";

import Link from "next/link";
import { useState } from "react";
import { Check, Copy, ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { JobStatusBadge } from "@/components/console/JobStatusBadge";
import { EmptyState } from "@/components/console/EmptyState";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatConsoleTimestamp, formatRelativeTime } from "@/components/console/formatters";
import { JobListItem } from "@/src/lib/types";
import { getTierLabel } from "@/src/lib/tier-utils";
import { copyToClipboard } from "@/src/lib/utils";

type JobHistoryTableProps = {
  jobs: JobListItem[];
  total: number;
  limit: number;
  offset?: number;
  jobsBasePath?: string;
  queryString?: string;
  loading?: boolean;
  refreshing?: boolean;
  onLoadMore?: () => void;
};

export function JobHistoryTable({
  jobs,
  total,
  limit: _limit,
  offset: _offset,
  jobsBasePath = "/osint/jobs",
  queryString = "",
  loading,
  refreshing,
  onLoadMore,
}: JobHistoryTableProps) {
  void _limit;
  void _offset;
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [showMore, setShowMore] = useState(false);

  const copyId = async (id: string) => {
    await copyToClipboard(id);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  if (loading && jobs.length === 0) {
    return (
      <div className="space-y-3 rounded-xl border border-border/70 bg-surface p-4">
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
      </div>
    );
  }

  if (!jobs.length && !loading) {
    return (
      <EmptyState
        title="No jobs yet"
        description="Run a lookup to start building a reusable request history."
      />
    );
  }

  const hasMore = jobs.length < total;
  const detailHref = (jobId: string) =>
    `${jobsBasePath}/${jobId}${queryString ? `?${queryString}` : ""}`;

  return (
    <div className="flex flex-col gap-4">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Request</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Requested tiers</TableHead>
            <TableHead>Updated</TableHead>
            <TableHead className="w-[180px]">Actions</TableHead>
            {showMore ? (
              <>
                <TableHead>Tiers</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>Request ID</TableHead>
              </>
            ) : null}
          </TableRow>
        </TableHeader>
        <TableBody>
          {jobs.map((job) => (
            <TableRow key={job.id}>
              <TableCell>
                <div className="min-w-0 space-y-2">
                  <div className="truncate text-sm font-medium text-foreground">
                    <Link href={detailHref(job.id)} className="text-primary hover:underline">
                      {job.identifierSummary || job.id}
                    </Link>
                  </div>
                  <div className="font-mono text-[11px] text-muted-foreground">{job.id}</div>
                  {showMore ? (
                    <p className="text-xs text-muted-foreground">
                      Open the request detail to inspect its merged dossier and raw response
                      payloads.
                    </p>
                  ) : null}
                </div>
              </TableCell>
              <TableCell>
                <JobStatusBadge status={job.status} />
              </TableCell>
              <TableCell>
                <div className="flex flex-wrap gap-1.5">
                  {job.requestedTiers.length > 0 ? (
                    job.requestedTiers.map((tier) => (
                      <Badge key={tier} variant="outline" className="font-normal">
                        {getTierLabel(tier)}
                      </Badge>
                    ))
                  ) : (
                    <span className="text-sm text-muted-foreground">—</span>
                  )}
                </div>
              </TableCell>
              <TableCell className="text-xs text-muted-foreground">
                <div>{formatRelativeTime(job.updatedAt)}</div>
                <div className="mt-1">{formatConsoleTimestamp(job.updatedAt)}</div>
              </TableCell>
              <TableCell>
                <div className="flex flex-wrap gap-2">
                  <Button asChild variant="outline" size="sm">
                    <Link href={detailHref(job.id)}>
                      <ExternalLink className="mr-1 size-3" />
                      Open
                    </Link>
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => void copyId(job.id)}>
                    {copiedId === job.id ? (
                      <>
                        <Check className="mr-1 size-3" />
                        Copied
                      </>
                    ) : (
                      <>
                        <Copy className="mr-1 size-3" />
                        Copy ID
                      </>
                    )}
                  </Button>
                </div>
              </TableCell>
              {showMore ? (
                <>
                  <TableCell className="text-sm text-muted-foreground">
                    {job.requestedTiers.join(", ") || "—"}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    <div>{formatRelativeTime(job.createdAt)}</div>
                    <div className="mt-1">{formatConsoleTimestamp(job.createdAt)}</div>
                  </TableCell>
                  <TableCell>
                    <Link
                      href={detailHref(job.id)}
                      className="font-mono text-sm text-primary hover:underline"
                    >
                      {job.id}
                    </Link>
                  </TableCell>
                </>
              ) : null}
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <div className="flex items-center justify-between gap-4 text-sm text-muted-foreground">
        <div className="flex flex-col gap-1">
          <span>
            Showing {jobs.length} of {total} requests
          </span>
          {refreshing ? <span className="text-xs">Refreshing in the background…</span> : null}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowMore((s) => !s)}
            disabled={loading || jobs.length === 0}
          >
            {showMore ? "Hide metadata" : "Show metadata"}
          </Button>
          {hasMore ? (
            <Button variant="outline" size="sm" disabled={loading} onClick={onLoadMore}>
              {loading ? "Loading…" : "Load more"}
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
