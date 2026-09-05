"use client";

import { useState, type FormEvent } from "react";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
      <form onSubmit={handleSubmit} className="flex gap-2">
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search your documents, e.g. 'led a team of 5 engineers'"
        />
        <Button type="submit" disabled={!query.trim() || isFetching}>
          <Search className="mr-2 size-4" />
          {isFetching ? "Searching…" : "Search"}
        </Button>
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
          {results.map((result) => (
            <Card key={result.documentId}>
              <CardContent className="flex flex-col gap-2 py-4">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-[11px] text-muted-foreground">
                    {result.documentId}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    Similarity: {(result.similarityScore * 100).toFixed(1)}%
                  </span>
                </div>
                <p className="text-sm">{result.excerpt}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
