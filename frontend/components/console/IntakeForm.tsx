'use client';

import { useEffect, useMemo, useState } from 'react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { useHealth } from '@/hooks/useHealth';
import {
  DepthPreset,
  getTiersFromDepthPreset,
  hasValidTierSelection,
  inferDepthPresetFromTiers,
} from '@/src/lib/tier-utils';
import { EnrichmentInput, EnrichMode } from '@/src/lib/types';

type IntakeFormProps = {
  mode: EnrichMode;
  initialTiers?: EnrichmentInput['requestedTiers'];
  onSubmit: (input: EnrichmentInput) => Promise<void>;
  loading?: boolean;
};

export function IntakeForm({ mode, initialTiers, onSubmit, loading }: IntakeFormProps) {
  const { online } = useHealth();
  const [identifier, setIdentifier] = useState('');
  const [company, setCompany] = useState('');
  const [business, setBusiness] = useState('');
  const [jobSearch, setJobSearch] = useState('');

  const [depthPreset, setDepthPreset] = useState<DepthPreset>(() => inferDepthPresetFromTiers(initialTiers ?? [], mode));
  const [error, setError] = useState('');

  useEffect(() => {
    if (initialTiers?.length) {
      setDepthPreset(inferDepthPresetFromTiers(initialTiers, mode));
    }
  }, [initialTiers, mode]);

  const requestedTiers = useMemo(() => getTiersFromDepthPreset(depthPreset, mode), [depthPreset, mode]);
  const hasIdentifier = useMemo(() => Boolean(identifier.trim()), [identifier]);
  const canSubmit = hasIdentifier && hasValidTierSelection(requestedTiers, mode) && online && !loading;

  const parseIdentifier = (raw: string): Pick<EnrichmentInput, 'email' | 'linkedinUrl' | 'username'> => {
    const value = raw.trim();
    const looksLikeEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
    const looksLikeLinkedIn = /linkedin\.com/i.test(value);

    if (looksLikeEmail) {
      return { email: value };
    }

    if (looksLikeLinkedIn) {
      const normalized = value.startsWith('http') ? value : `https://${value}`;
      return { linkedinUrl: normalized };
    }

    // Treat everything else as a username (strip leading '@' if present).
    return { username: value.replace(/^@/, '') };
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    try {
      const base: EnrichmentInput = {
        requestedTiers,
      };

      const identifierInput = parseIdentifier(identifier);
      if (identifierInput.email) base.email = identifierInput.email;
      if (identifierInput.linkedinUrl) base.linkedinUrl = identifierInput.linkedinUrl;
      if (identifierInput.username) base.username = identifierInput.username;

      const trimmedCompany = company.trim();
      if (trimmedCompany) base.company = trimmedCompany;

      const trimmedBusiness = business.trim();
      if (trimmedBusiness) base.business = trimmedBusiness;

      const trimmedJobSearch = jobSearch.trim();
      if (trimmedJobSearch) base.jobSearch = trimmedJobSearch;

      await onSubmit(base);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Submit failed');
    }
  };

  return (
    <Card>
      <CardHeader>
        <p className="text-xs uppercase tracking-widest text-muted-foreground">Request intake</p>
        <CardTitle className="text-2xl">Look up a person</CardTitle>
        <CardDescription>Paste one identifier. Choose depth and extras under Advanced.</CardDescription>
      </CardHeader>
      <CardContent>
        {mode === 'sync' ? (
          <Alert className="mb-4">
            <AlertDescription>Tier 1 is disabled in sync mode — browser pipeline excluded.</AlertDescription>
          </Alert>
        ) : null}

        <form className="flex flex-col gap-6" onSubmit={handleSubmit}>
          <div className="flex flex-col gap-2">
            <Label htmlFor="identifier">Identifier</Label>
            <Input
              id="identifier"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              placeholder="Email, LinkedIn URL, or username"
            />
          </div>

          <Collapsible defaultOpen={false}>
            <CollapsibleTrigger asChild>
              <Button variant="ghost" type="button" className="w-fit px-0">
                Advanced
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <div className="mt-4 flex flex-col gap-6 rounded-lg border bg-card p-4">
                <div className="flex flex-col gap-4">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="flex flex-col gap-2">
                      <Label htmlFor="company">Company (optional)</Label>
                      <Input id="company" value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Acme" />
                    </div>
                    <div className="flex flex-col gap-2">
                      <Label htmlFor="business">Business (optional)</Label>
                      <Input id="business" value={business} onChange={(e) => setBusiness(e.target.value)} placeholder="Coffee roasters near SoMa" />
                    </div>
                  </div>

                  <div className="flex flex-col gap-2">
                    <Label htmlFor="jobSearch">Job search (optional)</Label>
                    <Input
                      id="jobSearch"
                      value={jobSearch}
                      onChange={(e) => setJobSearch(e.target.value)}
                      placeholder="Staff Backend Engineer"
                    />
                  </div>
                </div>

                <fieldset className="flex flex-col gap-3 rounded-lg border p-4">
                  <legend className="px-1 text-sm font-medium">Depth</legend>
                  <RadioGroup
                    value={depthPreset}
                    onValueChange={(v) => setDepthPreset(v as DepthPreset)}
                    className="grid gap-3 sm:grid-cols-3"
                  >
                    <label className="flex cursor-pointer items-start gap-3 rounded-lg border p-3">
                      <RadioGroupItem value="quick" className="mt-1" />
                      <div>
                        <span className="block text-sm font-medium">Quick</span>
                        <span className="block text-xs text-muted-foreground">Tier 2</span>
                      </div>
                    </label>
                    <label className="flex cursor-pointer items-start gap-3 rounded-lg border p-3">
                      <RadioGroupItem value="standard" className="mt-1" />
                      <div>
                        <span className="block text-sm font-medium">Standard</span>
                        <span className="block text-xs text-muted-foreground">Tier 2 + 3</span>
                      </div>
                    </label>
                    <label className="flex cursor-pointer items-start gap-3 rounded-lg border p-3">
                      <RadioGroupItem value="deep" className="mt-1" />
                      <div>
                        <span className="block text-sm font-medium">Deep</span>
                        <span className="block text-xs text-muted-foreground">
                          Tier 1–4 {mode === 'sync' ? '(tier 1 excluded)' : ''}
                        </span>
                      </div>
                    </label>
                  </RadioGroup>
                </fieldset>
              </div>
            </CollapsibleContent>
          </Collapsible>

          <div className="flex flex-col gap-2">
            <Button type="submit" disabled={!canSubmit}>
              {loading ? 'Looking up…' : 'Look up'}
            </Button>
            {!online ? <p className="text-sm text-destructive">Backend unreachable — submit disabled.</p> : null}
            {error ? <p className="text-sm text-destructive">{error}</p> : null}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
