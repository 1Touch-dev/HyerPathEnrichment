"use client";

import { useMemo, useState } from 'react';
import { EnrichmentJob, EnrichmentInput, RequestedTier } from '@/src/lib/types';

const allTiers: RequestedTier[] = ['tier1', 'tier2', 'tier3', 'tier4'];

type IntakeFormProps = {
  onLoaded: (job: EnrichmentJob) => void;
};

const emptyInput: EnrichmentInput = {
  email: '',
  linkedinUrl: '',
  username: '',
  company: '',
  business: '',
  jobSearch: '',
  requestedTiers: allTiers,
};

export function IntakeForm({ onLoaded }: IntakeFormProps) {
  const [form, setForm] = useState<EnrichmentInput>(emptyInput);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const canSubmit = useMemo(() => {
    return Boolean(
      form.email || form.linkedinUrl || form.username || form.company || form.business || form.jobSearch,
    );
  }, [form]);

  const handleTierToggle = (tier: RequestedTier) => {
    setForm((current) => ({
      ...current,
      requestedTiers: current.requestedTiers.includes(tier)
        ? current.requestedTiers.filter((value) => value !== tier)
        : [...current.requestedTiers, tier],
    }));
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await fetch('/api/enrich', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });

      if (!response.ok) {
        throw new Error('Unable to load enrichment dossier');
      }

      const payload = (await response.json()) as EnrichmentJob;
      onLoaded(payload);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Unexpected error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Request intake</span>
          <h2>Submit one identifier, then let the pipeline correlate the rest.</h2>
        </div>
      </div>
      <form className="intake-form" onSubmit={handleSubmit}>
        <div className="field-grid">
          <label>
            <span>Email</span>
            <input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="alex@company.com" />
          </label>
          <label>
            <span>LinkedIn URL</span>
            <input value={form.linkedinUrl} onChange={(e) => setForm({ ...form, linkedinUrl: e.target.value })} placeholder="https://linkedin.com/in/example" />
          </label>
          <label>
            <span>Username</span>
            <input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} placeholder="alexhyrepath" />
          </label>
          <label>
            <span>Company</span>
            <input value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} placeholder="Hyrepath" />
          </label>
          <label>
            <span>Local business query</span>
            <input value={form.business} onChange={(e) => setForm({ ...form, business: e.target.value })} placeholder="Coffee roasters near SoMa" />
          </label>
          <label>
            <span>Job search query</span>
            <input value={form.jobSearch} onChange={(e) => setForm({ ...form, jobSearch: e.target.value })} placeholder="Staff Backend Engineer" />
          </label>
        </div>

        <fieldset>
          <legend>Requested tiers</legend>
          <div className="checkbox-row">
            {allTiers.map((tier) => (
              <label key={tier} className="checkbox-pill">
                <input
                  type="checkbox"
                  checked={form.requestedTiers.includes(tier)}
                  onChange={() => handleTierToggle(tier)}
                />
                <span>{tier.toUpperCase()}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <div className="form-footer">
          <button type="submit" disabled={!canSubmit || loading}>
            {loading ? 'Running pipeline…' : 'Generate dossier'}
          </button>
          {error ? <p className="error-text">{error}</p> : null}
        </div>
      </form>
    </section>
  );
}
