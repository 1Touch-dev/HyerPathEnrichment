"use client";

import { ExternalLink } from "lucide-react";
import { EmptyState } from "@/components/console/EmptyState";
import { DeskMetricCard, DeskMetricGrid } from "@/components/desk/desk-shell";
import { Button } from "@/components/ui/button";
import {
  SectionHeader,
  SectionHeaderActions,
  SectionHeaderContent,
  SectionHeaderDescription,
  SectionHeaderTitle,
} from "@/components/ui/section-header";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { SignalListItem } from "@/src/lib/types";

/** White KPI surface — mirrors admin desk-kpi (no pastel tone fills). */
const SIGNAL_KPI_CARD_CLASS = "border-border/70 bg-card";

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
      <DeskMetricGrid className="xl:grid-cols-3">
        <DeskMetricCard
          label="Signals loaded"
          value={signals.length}
          hint={`${total} total signal(s)`}
          className={SIGNAL_KPI_CARD_CLASS}
        />
        <DeskMetricCard
          label="Remaining records"
          value={Math.max(total - signals.length, 0)}
          hint={hasMore ? "More pages available" : "Current view is complete"}
          className={SIGNAL_KPI_CARD_CLASS}
        />
        <DeskMetricCard
          label="Source posture"
          value={signals[0]?.source ?? "Awaiting signals"}
          hint="Top row source in the current feed"
          className={SIGNAL_KPI_CARD_CLASS}
        />
      </DeskMetricGrid>

      <div className="flex flex-col gap-3">
        <SectionHeader>
          <SectionHeaderContent>
            <SectionHeaderTitle>Change-detection feed</SectionHeaderTitle>
            <SectionHeaderDescription>
              External watch alerts presented as a dense desk feed with direct source links.
            </SectionHeaderDescription>
          </SectionHeaderContent>
          <SectionHeaderActions>
            <Button
              variant="outline"
              onClick={onLoadMore}
              disabled={!hasMore || !onLoadMore || loading}
            >
              {loading ? "Loading…" : hasMore ? "Load more" : "All loaded"}
            </Button>
          </SectionHeaderActions>
        </SectionHeader>
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
    </div>
  );
}
