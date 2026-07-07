import { RequestedTier } from '@/src/lib/types';
import { tierLabels } from '@/src/lib/utils';

type HeroPanelProps = {
  requestedTiers: RequestedTier[];
};

export function HeroPanel({ requestedTiers }: HeroPanelProps) {
  return (
    <section className="panel hero-panel">
      <div>
        <span className="eyebrow">Hyrepath Enrichment</span>
        <h1>Unified enrichment dossiers for people, companies, jobs, and local businesses.</h1>
        <p className="hero-copy">
          This console shows how a single identifier fans out across tiered engines, merges signals,
          scores confidence, and returns a clean dossier for downstream review.
        </p>
      </div>
      <div className="tier-grid">
        {requestedTiers.map((tier) => (
          <div key={tier} className="tier-card">
            <span className="tier-pill">{tier.toUpperCase()}</span>
            <strong>{tierLabels[tier]}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}
