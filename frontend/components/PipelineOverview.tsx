import { EnrichmentJob } from '@/src/lib/types';
import { formatPercent } from '@/src/lib/utils';

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
] as const;

type PipelineOverviewProps = {
  job: EnrichmentJob;
};

function getStepDetail(step: (typeof steps)[number], job: EnrichmentJob): string {
  const { dossier, input, status, id } = job;
  const identifier = dossier.metadata.identifierSummary || input.username || input.email || 'identifier';

  switch (step) {
    case 'Validate request':
      return `Validated: ${identifier}`;
    case 'Normalize identifiers':
      return `Prepared enrichment request for ${identifier}.`;
    case 'Suppression check':
      return status === 'completed' ? 'No suppression match recorded.' : `Current status: ${status}.`;
    case 'Create job':
      return `Created job ${id}.`;
    case 'Dispatch tiers':
      return `Requested: ${input.requestedTiers.join(', ')}`;
    case 'Merge outputs':
      return dossier.sources.length
        ? `Merged signals from ${dossier.sources.join(', ')}.`
        : 'No source signals merged yet.';
    case 'Score confidence':
      return dossier.confidence.length
        ? `${dossier.confidence[0].label}: ${formatPercent(dossier.confidence[0].score)}`
        : 'No confidence scores returned.';
    case 'LLM disambiguation':
      return dossier.confidence.some((item) =>
        item.evidence.some((entry) => entry.toLowerCase().includes('llm')),
      )
        ? 'LLM disambiguation contributed to confidence scoring.'
        : 'LLM disambiguation was not required for this result.';
    case 'Persist dossier':
      return dossier.metadata.pipelineId
        ? `Persisted under pipeline ${dossier.metadata.pipelineId}.`
        : 'Dossier persisted for downstream review.';
    case 'Return job id':
      return `Returned job ${id} with status ${status}.`;
    default:
      return `Step completed with status ${status}.`;
  }
}

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
              <p>{getStepDetail(step, job)}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
