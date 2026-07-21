"use client";

import { useEffect, useMemo, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
  const [jobSearch, setJobSearch] = useState("");

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

  const fields = useMemo(
    () => ({ email, linkedinUrl, username, company, business, jobSearch }),
    [email, linkedinUrl, username, company, business, jobSearch],
  );

  const fieldsValid = isEnrichmentInputValidForTiers(fields, normalizedTiers);
  const canSubmit =
    hasValidTierSelection(requestedTiers, mode) && fieldsValid && online && !loading;

  const tier3Unsatisfied =
    requirements.emailOrCompanyOrUsername && !username.trim() && !email.trim() && !company.trim();

  const tier4Unsatisfied =
    requirements.businessOrJobSearch && !business.trim() && !jobSearch.trim();

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

      const trimmedJobSearch = jobSearch.trim();
      if (trimmedJobSearch) base.jobSearch = trimmedJobSearch;

      await onSubmit(base);
    } catch (submitError) {
      setError(formatApiErrorMessage(submitError));
    }
  };

  return (
    <Card>
      <CardHeader>
        <p className="text-xs uppercase tracking-widest text-muted-foreground">Request intake</p>
        <CardTitle className="text-2xl">Look up a person</CardTitle>
        <CardDescription>
          Choose tiers, then fill the fields they require. Unselected tiers leave their fields
          optional.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {mode === "sync" ? (
          <Alert className="mb-4">
            <AlertDescription>
              Tier 1 is disabled in sync mode — browser pipeline excluded.
            </AlertDescription>
          </Alert>
        ) : null}

        <form className="flex flex-col gap-6" onSubmit={handleSubmit}>
          <fieldset className="flex flex-col gap-3 rounded-lg border p-4">
            <legend className="px-1 text-sm font-medium">Tiers</legend>
            <div className="grid gap-3 sm:grid-cols-2">
              {ALL_TIERS.map((tier) => {
                const disabled = mode === "sync" && tier === "tier1";
                const checked = requestedTiers.includes(tier);
                const id = `tier-${tier}`;

                return (
                  <label
                    key={tier}
                    htmlFor={id}
                    className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 ${
                      disabled ? "cursor-not-allowed opacity-50" : ""
                    }`}
                  >
                    <Checkbox
                      id={id}
                      checked={checked}
                      disabled={disabled}
                      onCheckedChange={(value) => toggleTier(tier, value === true)}
                      className="mt-1"
                    />
                    <div>
                      <span className="block text-sm font-medium">{getTierLabel(tier)}</span>
                      <span className="block text-xs text-muted-foreground">
                        {tierDescriptions[tier]}
                      </span>
                    </div>
                  </label>
                );
              })}
            </div>
          </fieldset>

          <div className="grid gap-4 sm:grid-cols-2">
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
            <div className="flex flex-col gap-2">
              <Label htmlFor="company">Company {fieldSuffix(false)}</Label>
              <Input
                id="company"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder="Acme"
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="business">Business {fieldSuffix(false)}</Label>
              <Input
                id="business"
                value={business}
                onChange={(e) => setBusiness(e.target.value)}
                placeholder="Coffee roasters near SoMa"
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="jobSearch">Job search {fieldSuffix(false)}</Label>
              <Input
                id="jobSearch"
                value={jobSearch}
                onChange={(e) => setJobSearch(e.target.value)}
                placeholder="Staff Backend Engineer"
              />
            </div>
          </div>

          {tier3Unsatisfied ? (
            <p className="text-sm text-muted-foreground">
              Tier 3 needs username, email, or company.
            </p>
          ) : null}
          {tier4Unsatisfied ? (
            <p className="text-sm text-muted-foreground">Tier 4 needs business or job search.</p>
          ) : null}
          {requirements.linkedinUrl && !linkedinUrl.trim() ? (
            <p className="text-sm text-muted-foreground">Tier 1 needs a LinkedIn URL.</p>
          ) : null}
          {requirements.username && !username.trim() ? (
            <p className="text-sm text-muted-foreground">Tier 2 needs a username.</p>
          ) : null}

          <div className="flex flex-col gap-2">
            <Button type="submit" disabled={!canSubmit}>
              {loading ? "Looking up…" : "Look up"}
            </Button>
            {!online ? (
              <p className="text-sm text-destructive">Backend unreachable — submit disabled.</p>
            ) : null}
            {error ? <p className="text-sm text-destructive">{error}</p> : null}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
