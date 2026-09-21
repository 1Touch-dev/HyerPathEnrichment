"use client";

import { useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  SectionHeader,
  SectionHeaderContent,
  SectionHeaderDescription,
  SectionHeaderTitle,
} from "@/components/ui/section-header";
import { useHealth } from "@/hooks/useHealth";
import { tierDescriptions } from "@/src/lib/landing-content";
import {
  ALL_TIERS,
  getTierLabel,
  hasValidTierSelection,
  isEnrichmentInputValidForTiers,
  normalizeTiersForMode,
  tierFieldRequirements,
} from "@/src/lib/tier-utils";
import { formatApiErrorMessage } from "@/src/lib/format-api-error";
import { EnrichmentInput, EnrichMode, RequestedTier } from "@/src/lib/types";

type IntakeFormProps = {
  mode: EnrichMode;
  initialTiers?: EnrichmentInput["requestedTiers"];
  onSubmit: (input: EnrichmentInput) => Promise<void>;
  loading?: boolean;
};

function fieldSuffix(required: boolean): string {
  return required ? "(required)" : "(optional)";
}

export function IntakeForm({ mode, initialTiers, onSubmit, loading }: IntakeFormProps) {
  const { online } = useHealth();
  const [email, setEmail] = useState("");
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [username, setUsername] = useState("");
  const [company, setCompany] = useState("");
  const [business, setBusiness] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [jobLocation, setJobLocation] = useState("");
  const [jobCountry, setJobCountry] = useState("");

  const [requestedTiers, setRequestedTiers] = useState<RequestedTier[]>(() =>
    normalizeTiersForMode(initialTiers ?? ["tier2", "tier3"], mode),
  );
  const [error, setError] = useState("");

  useEffect(() => {
    setRequestedTiers(normalizeTiersForMode(initialTiers ?? ["tier2", "tier3"], mode));
    // Seed from query/draft tiers only; mode changes are handled below.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentionally ignore mode here
  }, [initialTiers]);

  useEffect(() => {
    setRequestedTiers((prev) => normalizeTiersForMode(prev, mode));
  }, [mode]);

  const normalizedTiers = useMemo(
    () => normalizeTiersForMode(requestedTiers, mode),
    [requestedTiers, mode],
  );

  const requirements = useMemo(() => tierFieldRequirements(normalizedTiers), [normalizedTiers]);

  const fields = useMemo(() => {
    const jobSearch = `${jobTitle.trim()} ${jobLocation.trim()}`.trim();
    return {
      email,
      linkedinUrl,
      username,
      company,
      business,
      jobSearch,
      jobTitle,
      jobLocation,
      jobCountry,
    };
  }, [email, linkedinUrl, username, company, business, jobTitle, jobLocation, jobCountry]);

  const fieldsValid = isEnrichmentInputValidForTiers(fields, normalizedTiers);
  const canSubmit =
    hasValidTierSelection(requestedTiers, mode) && fieldsValid && online && !loading;

  const tier3Unsatisfied =
    requirements.emailOrCompanyOrUsername && !username.trim() && !email.trim() && !company.trim();

  const tier4Unsatisfied =
    requirements.businessOrJobSearch && !business.trim() && !jobTitle.trim() && !jobLocation.trim();

  const selectedTierCount = normalizedTiers.length;
  const requirementHints = [
    requirements.linkedinUrl && !linkedinUrl.trim() ? "Tier 1 needs a LinkedIn URL." : null,
    requirements.username && !username.trim() ? "Tier 2 needs a username." : null,
    tier3Unsatisfied ? "Tier 3 needs username, email, or company." : null,
    tier4Unsatisfied ? "Tier 4 needs business or job search." : null,
  ].filter((hint): hint is string => Boolean(hint));

  const toggleTier = (tier: RequestedTier, checked: boolean) => {
    if (mode === "sync" && tier === "tier1") {
      return;
    }

    setRequestedTiers((prev) => {
      if (checked) {
        return normalizeTiersForMode([...prev, tier], mode);
      }
      return prev.filter((t) => t !== tier);
    });
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    try {
      const base: EnrichmentInput = {
        requestedTiers: normalizedTiers,
      };

      const trimmedEmail = email.trim();
      if (trimmedEmail) base.email = trimmedEmail;

      const trimmedLinkedin = linkedinUrl.trim();
      if (trimmedLinkedin) {
        base.linkedinUrl = trimmedLinkedin.startsWith("http")
          ? trimmedLinkedin
          : `https://${trimmedLinkedin}`;
      }

      const trimmedUsername = username.trim().replace(/^@/, "");
      if (trimmedUsername) base.username = trimmedUsername;

      const trimmedCompany = company.trim();
      if (trimmedCompany) base.company = trimmedCompany;

      const trimmedBusiness = business.trim();
      if (trimmedBusiness) base.business = trimmedBusiness;

      const trimmedJobTitle = jobTitle.trim();
      const trimmedJobLocation = jobLocation.trim();
      const trimmedJobCountry = jobCountry.trim();
      if (trimmedJobTitle) base.jobTitle = trimmedJobTitle;
      if (trimmedJobLocation) base.jobLocation = trimmedJobLocation;
      if (trimmedJobCountry) base.jobCountry = trimmedJobCountry;
      if (trimmedJobTitle || trimmedJobLocation) {
        base.jobSearch = `${trimmedJobTitle} ${trimmedJobLocation}`.trim();
      }

      await onSubmit(base);
    } catch (submitError) {
      setError(formatApiErrorMessage(submitError));
    }
  };

  return (
    <Card className="overflow-hidden">
      <CardHeader className="gap-4 border-b border-border/60 bg-surface-muted/40">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-2">
            <p className="text-xs uppercase tracking-widest text-muted-foreground">
              Request intake
            </p>
            <CardTitle className="text-2xl">Prepare a lookup</CardTitle>
            <CardDescription>
              Choose the tiers you want, then add the strongest identifiers you have. Blank optional
              fields stay out of the request.
            </CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant={online ? "success" : "destructive"}>
              {online ? "API reachable" : "API offline"}
            </Badge>
            <Badge variant="outline">
              {selectedTierCount} tier{selectedTierCount === 1 ? "" : "s"} selected
            </Badge>
            <Badge variant={mode === "async" ? "info" : "secondary"}>
              {mode === "async" ? "Async request" : "Sync request"}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-6">
        {mode === "sync" ? (
          <Alert className="mb-6">
            <AlertDescription>
              Tier 1 is disabled in sync mode because the browser pipeline only runs in async.
            </AlertDescription>
          </Alert>
        ) : null}

        {requirementHints.length > 0 ? (
          <Alert className="mb-6 border-warning/20 bg-warning/10 text-warning">
            <AlertDescription className="space-y-1">
              <p className="font-medium text-foreground">Missing fields for the selected tiers</p>
              <ul className="list-disc pl-5 text-sm">
                {requirementHints.map((hint) => (
                  <li key={hint}>{hint}</li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
        ) : null}

        <form className="flex flex-col gap-8" onSubmit={handleSubmit}>
          <fieldset className="flex flex-col gap-4 rounded-xl border border-border/70 bg-surface p-4 sm:p-5">
            <SectionHeader>
              <SectionHeaderContent>
                <SectionHeaderTitle>Requested tiers</SectionHeaderTitle>
                <SectionHeaderDescription>
                  Unselected tiers keep their related fields optional.
                </SectionHeaderDescription>
              </SectionHeaderContent>
            </SectionHeader>

            <legend className="sr-only">Requested tiers</legend>
            <div className="grid gap-3 xl:grid-cols-2">
              {ALL_TIERS.map((tier) => {
                const disabled = mode === "sync" && tier === "tier1";
                const checked = requestedTiers.includes(tier);
                const id = `tier-${tier}`;

                return (
                  <label
                    key={tier}
                    htmlFor={id}
                    className={`flex cursor-pointer items-start gap-3 rounded-xl border border-border/70 bg-background p-4 transition-colors hover:bg-surface-muted/50 ${
                      checked ? "border-primary/40 bg-primary/5" : ""
                    } ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
                  >
                    <Checkbox
                      id={id}
                      checked={checked}
                      disabled={disabled}
                      onCheckedChange={(value) => toggleTier(tier, value === true)}
                      className="mt-1"
                    />
                    <div className="min-w-0 space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="block text-sm font-medium">{getTierLabel(tier)}</span>
                        {checked ? <Badge variant="success">Selected</Badge> : null}
                        {disabled ? <Badge variant="outline">Async only</Badge> : null}
                      </div>
                      <span className="block text-sm text-muted-foreground">
                        {tierDescriptions[tier]}
                      </span>
                    </div>
                  </label>
                );
              })}
            </div>
          </fieldset>

          <div className="grid gap-6 xl:grid-cols-2">
            <section className="rounded-xl border border-border/70 bg-surface p-4 sm:p-5">
              <SectionHeader className="mb-4">
                <SectionHeaderContent>
                  <SectionHeaderTitle>Identity signals</SectionHeaderTitle>
                  <SectionHeaderDescription>
                    These clues help the lookup land on the right person quickly.
                  </SectionHeaderDescription>
                </SectionHeaderContent>
              </SectionHeader>

              <div className="grid gap-4">
                <div className="flex flex-col gap-2">
                  <Label htmlFor="linkedinUrl">
                    LinkedIn URL {fieldSuffix(requirements.linkedinUrl)}
                  </Label>
                  <Input
                    id="linkedinUrl"
                    value={linkedinUrl}
                    onChange={(e) => setLinkedinUrl(e.target.value)}
                    placeholder="https://linkedin.com/in/jane"
                    aria-required={requirements.linkedinUrl}
                  />
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="username">Username {fieldSuffix(requirements.username)}</Label>
                    <Input
                      id="username"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      placeholder="jane"
                      aria-required={requirements.username}
                    />
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="email">Email {fieldSuffix(false)}</Label>
                    <Input
                      id="email"
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="jane@example.com"
                    />
                  </div>
                </div>
                <div className="flex flex-col gap-2">
                  <Label htmlFor="company">Company {fieldSuffix(false)}</Label>
                  <Input
                    id="company"
                    value={company}
                    onChange={(e) => setCompany(e.target.value)}
                    placeholder="Acme"
                  />
                </div>
              </div>
            </section>

            <section className="rounded-xl border border-border/70 bg-surface p-4 sm:p-5">
              <SectionHeader className="mb-4">
                <SectionHeaderContent>
                  <SectionHeaderTitle>Search context</SectionHeaderTitle>
                  <SectionHeaderDescription>
                    Add business or role context when you want deeper public-web and job-market
                    evidence.
                  </SectionHeaderDescription>
                </SectionHeaderContent>
              </SectionHeader>

              <div className="grid gap-4">
                <div className="flex flex-col gap-2">
                  <Label htmlFor="business">Business {fieldSuffix(false)}</Label>
                  <Input
                    id="business"
                    value={business}
                    onChange={(e) => setBusiness(e.target.value)}
                    placeholder="Coffee roasters near SoMa"
                  />
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="jobTitle">Job title {fieldSuffix(false)}</Label>
                    <Input
                      id="jobTitle"
                      value={jobTitle}
                      onChange={(e) => setJobTitle(e.target.value)}
                      placeholder="e.g., Senior Backend Engineer"
                    />
                  </div>
                  <div className="flex flex-col gap-2">
                    <Label htmlFor="jobLocation">Job location {fieldSuffix(false)}</Label>
                    <Input
                      id="jobLocation"
                      value={jobLocation}
                      onChange={(e) => setJobLocation(e.target.value)}
                      placeholder="e.g., Remote, San Francisco, Berlin"
                    />
                  </div>
                </div>
                <div className="flex flex-col gap-2">
                  <Label htmlFor="jobCountry">Job country {fieldSuffix(false)}</Label>
                  <Input
                    id="jobCountry"
                    value={jobCountry}
                    onChange={(e) => setJobCountry(e.target.value)}
                    placeholder="e.g., USA, Germany, Canada"
                  />
                </div>
              </div>
            </section>
          </div>

          <div className="flex flex-col gap-3 rounded-xl border border-border/70 bg-surface p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <p className="text-sm font-medium text-foreground">Ready to submit</p>
              <p className="text-sm text-muted-foreground">
                The request stays read-only until the selected tiers have the fields they need.
              </p>
              {!online ? (
                <p className="text-sm text-destructive">Backend unreachable. Submit is disabled.</p>
              ) : null}
              {error ? <p className="text-sm text-destructive">{error}</p> : null}
            </div>
            <Button type="submit" disabled={!canSubmit} className="sm:min-w-40">
              {loading ? "Starting lookup…" : "Start lookup"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
