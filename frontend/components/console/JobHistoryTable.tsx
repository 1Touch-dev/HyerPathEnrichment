'use client';

import Link from 'next/link';
import { useState } from 'react';
import { Copy } from 'lucide-react';
import { JobStatusBadge } from '@/components/console/JobStatusBadge';
import { EmptyState } from '@/components/console/EmptyState';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { JobListItem } from '@/src/lib/types';
import { copyToClipboard } from '@/src/lib/utils';

type JobHistoryTableProps = {
  jobs: JobListItem[];
  total: number;
  limit: number;
  offset: number;
  loading?: boolean;
  onLoadMore?: () => void;
};

export function JobHistoryTable({ jobs, total, limit, offset, loading, onLoadMore }: JobHistoryTableProps) {
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [showMore, setShowMore] = useState(false);

  const copyId = async (id: string) => {
    await copyToClipboard(id);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  if (!jobs.length && !loading) {
    return <EmptyState title="No jobs yet" description="Run an enrichment from the console to populate history." />;
  }

  const hasMore = offset + jobs.length < total;

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Who</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>When</TableHead>
              {showMore ? (
                <>
                  <TableHead>Job ID</TableHead>
                  <TableHead>Identifier</TableHead>
                  <TableHead>Tiers</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Updated</TableHead>
                  <TableHead>Actions</TableHead>
                </>
              ) : null}
            </TableRow>
          </TableHeader>
          <TableBody>
            {jobs.map((job) => (
              <TableRow key={job.id}>
                <TableCell>
                  <div className="min-w-0">
                    <div className="truncate">
                      <Link href={`/app/jobs/${job.id}`} className="text-primary hover:underline">
                        {job.identifierSummary || job.id}
                      </Link>
                    </div>
                    <div className="mt-0.5 font-mono text-[11px] text-muted-foreground">{job.id}</div>
                  </div>
                </TableCell>
                <TableCell>
                  <JobStatusBadge status={job.status} />
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">{formatDate(job.createdAt)}</TableCell>
                {showMore ? (
                  <>
                    <TableCell>
                      <Link href={`/app/jobs/${job.id}`} className="font-mono text-sm text-primary hover:underline">
                        {job.id}
                      </Link>
                    </TableCell>
                    <TableCell className="max-w-[240px] truncate">{job.identifierSummary || '—'}</TableCell>
                    <TableCell>{job.requestedTiers.join(', ') || '—'}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{formatDate(job.createdAt)}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{formatDate(job.updatedAt)}</TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <Button asChild variant="outline" size="sm">
                          <Link href={`/app/jobs/${job.id}`}>View</Link>
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => void copyId(job.id)}>
                          <Copy className="size-3" />
                          {copiedId === job.id ? 'Copied' : 'Copy ID'}
                        </Button>
                      </div>
                    </TableCell>
                  </>
                ) : null}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <div className="flex items-center justify-between gap-4 text-sm text-muted-foreground">
        <span>
          Showing {offset + 1}–{offset + jobs.length} of {total}
        </span>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowMore((s) => !s)}
            disabled={loading || (!hasMore && jobs.length === 0)}
          >
            {showMore ? 'Show less' : 'Show more columns'}
          </Button>
          {hasMore ? (
            <Button variant="outline" size="sm" disabled={loading} onClick={onLoadMore}>
              {loading ? 'Loading…' : 'Load more'}
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function formatDate(value: string) {
  if (!value) return '—';
  return value.replace('T', ' ').slice(0, 19);
}
