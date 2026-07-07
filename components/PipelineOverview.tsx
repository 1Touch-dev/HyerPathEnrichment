import { EnrichmentJob } from '@/src/lib/types';

const steps = [
  'Validate request',
  'Normalize identifiers',
  'Suppression check',
  'Create job',
  'Dispatch tiers',
  'Merge outputs',
  'Score confidence',
  'LLM disambiguation',
  'Persist dossier',
  'Return job id',
];

type PipelineOverviewProps = {
  job: EnrichmentJob;
};

export function PipelineOverview({ job }: PipelineOverviewProps) {
  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Pipeline trace</span>
          <h2>{job.id}</h2>
        </div>
        <span className="status-chip">{job.status}</span>
      </div>
      <ol className="timeline">
        {steps.map((step, index) => (
          <li key={step}>
            <span>{index + 1}</span>
            <div>
              <strong>{step}</strong>
              <p>
                {step === 'Dispatch tiers'
                  ? `Requested: ${job.input.requestedTiers.join(', ')}`
                  : 'Completed successfully in this mocked production-safe flow.'}
              </p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
