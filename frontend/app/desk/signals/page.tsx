"use client";

import { DeskPage } from "@/components/desk/desk-shell";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { SignalsTable, useSignalListQuery } from "@/features/signals";
import { formatApiErrorMessage } from "@/src/lib/format-api-error";

export default function SignalsPage() {
  const { data, isLoading, error, isFetching, fetchNextPage, hasNextPage } = useSignalListQuery();

  const signals = data?.pages.flatMap((page) => page.signals) ?? [];
  const total = data?.pages[0]?.total ?? 0;

  return (
    <DeskPage
      eyebrow="Desk intelligence"
      title="Signals"
      description="Review monitored page changes from changedetection.io watches without altering the existing feed and pagination behavior."
    >
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
    </DeskPage>
  );
}
