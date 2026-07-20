'use client';

import { ExternalLink } from 'lucide-react';
import { EmptyState } from '@/components/console/EmptyState';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { SignalListItem } from '@/src/lib/types';

type SignalsTableProps = {
  signals: SignalListItem[];
  total: number;
  loading?: boolean;
  onLoadMore?: () => void;
};

export function SignalsTable({ signals, total, loading, onLoadMore }: SignalsTableProps) {
  if (!signals.length && !loading) {
    return (
      <EmptyState
        title="No change signals yet"
        description="Configure changedetection.io watches to monitor pages; signals appear here when changes are detected."
      />
    );
  }

  const hasMore = signals.length < total;

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Title</TableHead>
              <TableHead>Source</TableHead>
              <TableHead>Detected</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {signals.map((signal) => (
              <TableRow key={signal.id}>
                <TableCell className="max-w-[280px] truncate">
                  {signal.url ? (
                    <a
                      href={signal.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-primary hover:underline"
                    >
                      {signal.title}
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  ) : (
                    signal.title
                  )}
                </TableCell>
                <TableCell>{signal.source}</TableCell>
                <TableCell className="text-muted-foreground text-sm">
                  {signal.timestamp || signal.createdAt}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {hasMore && onLoadMore ? (
        <Button variant="outline" onClick={onLoadMore} disabled={loading}>
          {loading ? 'Loading…' : 'Load more'}
        </Button>
      ) : null}
    </div>
  );
}
