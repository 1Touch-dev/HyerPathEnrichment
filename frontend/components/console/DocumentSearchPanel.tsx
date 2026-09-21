"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { FilterBar, FilterBarActions, FilterBarGroup } from "@/components/ui/filter-bar";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/console/EmptyState";
import { useDocumentSearch } from "@/features/documents";
import { formatApiErrorMessage } from "@/src/lib/format-api-error";

export function DocumentSearchPanel() {
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");

  const { data, isFetching, error } = useDocumentSearch(submittedQuery);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    setSubmittedQuery(query.trim());
  };

  const results = data?.results ?? [];
  const hasSearched = submittedQuery.length > 0;

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={handleSubmit}>
        <FilterBar>
          <FilterBarGroup className="min-w-0">
            <div className="min-w-0 flex-1">
              <p className="mb-2 text-sm font-medium text-foreground">Semantic document search</p>
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search your documents, e.g. 'led a team of 5 engineers'"
              />
            </div>
          </FilterBarGroup>
          <FilterBarActions>
            <Button
              type="submit"
              disabled={!query.trim() || isFetching}
              className="w-full sm:w-auto"
            >
              <Search className="mr-2 size-4" />
              {isFetching ? "Searching…" : "Search"}
            </Button>
          </FilterBarActions>
        </FilterBar>
      </form>

      {error ? <p className="text-sm text-destructive">{formatApiErrorMessage(error)}</p> : null}

      {!hasSearched ? (
        <EmptyState
          title="Search your documents"
          description="Enter a query above to search across your uploaded CVs and cover letters by meaning, not just keywords."
        />
      ) : results.length === 0 && !isFetching ? (
        <EmptyState
          title="No results yet"
          description="No matches were found. This can happen if embedding processing hasn't finished (or isn't available) yet for your documents — try again in a bit rather than assuming something is broken."
        />
      ) : (
        <div className="flex flex-col gap-3">
          <div className="rounded-xl border border-border/70 bg-surface p-4">
            <p className="text-sm font-medium text-foreground">
              {results.length} match{results.length === 1 ? "" : "es"} for &ldquo;{submittedQuery}
              &rdquo;
            </p>
            <p className="text-sm text-muted-foreground">
              Results are ranked by semantic similarity, not exact keyword matches.
            </p>
          </div>
          {results.map((result) => (
            <Card key={result.documentId} className="overflow-hidden">
              <CardContent className="flex flex-col gap-3 py-4">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="text-sm font-medium text-foreground">Matched document excerpt</p>
                    <span className="font-mono text-[11px] text-muted-foreground">
                      {result.documentId}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="rounded-full border border-border/70 bg-surface-muted px-2.5 py-1 text-xs text-muted-foreground">
                      {(result.similarityScore * 100).toFixed(1)}% similar
                    </span>
                    <Button asChild variant="outline" size="sm">
                      <Link href={`/app/documents/${result.documentId}`}>Open document</Link>
                    </Button>
                  </div>
                </div>
                <p className="rounded-lg border border-border/70 bg-surface p-3 text-sm leading-6">
                  {result.excerpt}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
