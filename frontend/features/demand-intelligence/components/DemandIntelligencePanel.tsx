"use client";

import { useState, type FormEvent } from "react";
import { Search } from "lucide-react";
import { EmptyState } from "@/components/console/EmptyState";
import { DeskMetricCard, DeskMetricGrid } from "@/components/desk/desk-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FilterBar, FilterBarActions, FilterBarGroup } from "@/components/ui/filter-bar";
import { Input } from "@/components/ui/input";
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
import { formatApiErrorMessage } from "@/src/lib/format-api-error";
import type { CountryDemandRow, CountryTier } from "../hooks/useDemandIntelligence";
import { useTopCountriesForRole } from "../hooks/useDemandIntelligence";

const TIER_LABEL: Record<CountryTier, string> = {
  tier_1: "Tier 1",
  tier_2: "Tier 2",
  tier_3: "Tier 3",
};

const TIER_VARIANT: Record<CountryTier, "default" | "secondary" | "outline"> = {
  tier_1: "default",
  tier_2: "secondary",
  tier_3: "outline",
};

function formatSalaryRange(min: number | null, max: number | null): string {
  if (min === null && max === null) return "—";
  if (min !== null && max !== null) {
    return `$${min.toLocaleString()} – $${max.toLocaleString()}`;
  }
  return `$${(min ?? max)!.toLocaleString()}`;
}

/**
 * Role-search table over `GET /api/demand-intelligence/top-countries` — recruiter-facing
 * sourcing signal for where to focus candidate outreach, tiered `tier_1`/`tier_2`/`tier_3`
 * per the market-research methodology in `02-country-demand-intelligence.md`.
 */
export function DemandIntelligencePanel() {
  const [role, setRole] = useState("");
  const [submittedRole, setSubmittedRole] = useState("");

  const { data, isFetching, error } = useTopCountriesForRole(submittedRole);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmittedRole(role.trim());
  }

  const results = data?.results ?? [];
  const hasSearched = submittedRole.length > 0;
  const tierOneCount = results.filter((row) => row.tier === "tier_1").length;

  return (
    <div className="flex flex-col gap-4">
      <DeskMetricGrid className="xl:grid-cols-3">
        <DeskMetricCard
          label="Search state"
          value={hasSearched ? submittedRole : "Awaiting query"}
          hint="Role bucket currently in view"
          tone={hasSearched ? "info" : "default"}
        />
        <DeskMetricCard
          label="Results returned"
          value={results.length}
          hint={hasSearched ? "Matching country buckets" : "Run a search to populate results"}
        />
        <DeskMetricCard
          label="Tier 1 countries"
          value={tierOneCount}
          hint="Highest sourcing priority in this result set"
          tone={tierOneCount > 0 ? "success" : "default"}
        />
      </DeskMetricGrid>

      <form onSubmit={handleSubmit}>
        <FilterBar className="items-stretch sm:items-end">
          <FilterBarGroup>
            <div className="flex-1">
              <Input
                value={role}
                onChange={(event) => setRole(event.target.value)}
                placeholder="Search by role, e.g. 'software engineer'"
              />
            </div>
          </FilterBarGroup>
          <FilterBarActions>
            <Button type="submit" disabled={!role.trim() || isFetching}>
              <Search className="mr-2 size-4" />
              {isFetching ? "Searching…" : "Search"}
            </Button>
          </FilterBarActions>
        </FilterBar>
      </form>

      {error ? <p className="text-sm text-destructive">{formatApiErrorMessage(error)}</p> : null}

      {!hasSearched ? (
        <EmptyState
          title="Search for a role"
          description="Enter a role above to see the countries with the most demand for it, tiered by sourcing priority."
        />
      ) : results.length === 0 && !isFetching ? (
        <EmptyState
          title="No results yet"
          description="No country-demand data was found for that role. This can happen if the daily aggregation job hasn't run yet, or no postings currently match — try a broader role query."
        />
      ) : (
        <div className="flex flex-col gap-3">
          <SectionHeader>
            <SectionHeaderContent>
              <SectionHeaderTitle>Country demand results</SectionHeaderTitle>
              <SectionHeaderDescription>
                Recruiter-facing country ranking for the submitted role, grouped by sourcing tier.
              </SectionHeaderDescription>
            </SectionHeaderContent>
            <SectionHeaderActions>
              <Badge variant="outline">{submittedRole}</Badge>
            </SectionHeaderActions>
          </SectionHeader>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Country</TableHead>
                <TableHead>Postings</TableHead>
                <TableHead>Remote postings</TableHead>
                <TableHead>Avg. salary</TableHead>
                <TableHead>Tier</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {results.map((row: CountryDemandRow) => (
                <TableRow key={`${row.country_iso2}-${row.role_bucket}`}>
                  <TableCell className="uppercase">{row.country_iso2}</TableCell>
                  <TableCell>{row.posting_count.toLocaleString()}</TableCell>
                  <TableCell>{row.remote_posting_count.toLocaleString()}</TableCell>
                  <TableCell>{formatSalaryRange(row.avg_salary_min, row.avg_salary_max)}</TableCell>
                  <TableCell>
                    <Badge variant={TIER_VARIANT[row.tier]}>{TIER_LABEL[row.tier]}</Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
