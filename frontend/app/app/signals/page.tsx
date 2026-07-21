"use client";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { SignalsTable, useSignalListQuery } from "@/features/signals";
import { formatApiErrorMessage } from "@/src/lib/format-api-error";

export default function SignalsPage() {
  const { data, isLoading, error, isFetching, fetchNextPage, hasNextPage } = useSignalListQuery();

  const signals = data?.pages.flatMap((page) => page.signals) ?? [];
  const total = data?.pages[0]?.total ?? 0;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Signals</h1>
        <p className="text-sm text-muted-foreground">
          Monitored page changes from changedetection.io watches.
        </p>
      </div>

      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{formatApiErrorMessage(error)}</AlertDescription>
        </Alert>
      ) : null}

      <SignalsTable
        signals={signals}
        total={total}
        loading={isLoading || isFetching}
        onLoadMore={hasNextPage ? () => void fetchNextPage() : undefined}
      />
    </div>
  );
}
