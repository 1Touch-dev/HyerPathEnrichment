"use client";

import { useState } from 'react';
import { DossierView } from '@/components/DossierView';
import { HeroPanel } from '@/components/HeroPanel';
import { IntakeForm } from '@/components/IntakeForm';
import { PipelineOverview } from '@/components/PipelineOverview';
import { EnrichmentJob, RequestedTier } from '@/src/lib/types';

const defaultTiers: RequestedTier[] = ['tier1', 'tier2', 'tier3', 'tier4'];

export default function HomePage() {
  const [job, setJob] = useState<EnrichmentJob | null>(null);

  return (
    <main className="page-shell">
      <HeroPanel requestedTiers={job?.input.requestedTiers ?? defaultTiers} />
      <div className="content-stack">
        <IntakeForm onLoaded={setJob} />
        {job ? (
          <>
            <PipelineOverview job={job} />
            <DossierView dossier={job.dossier} />
          </>
        ) : (
          <section className="panel">
            <div className="section-heading">
              <div>
                <span className="eyebrow">Results</span>
                <h2>Submit an identifier to run the enrichment pipeline.</h2>
              </div>
            </div>
            <p className="muted">
              Pipeline trace and dossier details will appear here after a successful enrichment request.
            </p>
          </section>
        )}
      </div>
    </main>
  );
}
