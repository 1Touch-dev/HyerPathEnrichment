"use client";

import { useState } from 'react';
import { DossierView } from '@/components/DossierView';
import { HeroPanel } from '@/components/HeroPanel';
import { IntakeForm } from '@/components/IntakeForm';
import { PipelineOverview } from '@/components/PipelineOverview';
import { sampleJobs } from '@/src/lib/mock-data';
import { EnrichmentJob } from '@/src/lib/types';

export default function HomePage() {
  const [job, setJob] = useState<EnrichmentJob>(sampleJobs[0]);

  return (
    <main className="page-shell">
      <HeroPanel requestedTiers={job.input.requestedTiers} />
      <div className="content-stack">
        <IntakeForm onLoaded={setJob} />
        <PipelineOverview job={job} />
        <DossierView dossier={job.dossier} />
      </div>
    </main>
  );
}
