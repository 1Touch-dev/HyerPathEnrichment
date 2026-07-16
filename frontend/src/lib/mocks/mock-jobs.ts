import { createMockJob } from '@/src/lib/mock-data';
import { Dossier, EnrichmentInput, EnrichmentJob, JobListItem } from '@/src/lib/types';

type MockJobGlobal = typeof globalThis & {
  __hyrepathMockJobStore?: Map<string, EnrichmentJob>;
};

const mockGlobal = globalThis as MockJobGlobal;
const mockJobStore = mockGlobal.__hyrepathMockJobStore ?? new Map<string, EnrichmentJob>();
mockGlobal.__hyrepathMockJobStore = mockJobStore;

const emptyDossier = (input: EnrichmentInput): Dossier => ({
  handles: [],
  emails: [],
  verifiedEmails: [],
  coworkers: [],
  jobs: [],
  confidence: [],
  sources: [],
  metadata: {
    generatedAt: new Date().toISOString(),
    pipelineId: 'mock-pipeline',
    requestedTiers: input.requestedTiers,
    identifierSummary: [input.email, input.linkedinUrl, input.username, input.company, input.business, input.jobSearch]
      .filter(Boolean)
      .join(' • '),
  },
});

export function createMockJobWithLifecycle(input: EnrichmentInput): EnrichmentJob {
  const job = createMockJob(input);
  const queued: EnrichmentJob = { ...job, status: 'queued', dossier: emptyDossier(input) };
  mockJobStore.set(queued.id, queued);

  setTimeout(() => {
    const running = mockJobStore.get(queued.id);
    if (running && running.status === 'queued') {
      mockJobStore.set(queued.id, { ...running, status: 'running' });
    }
  }, 800);

  setTimeout(() => {
    mockJobStore.set(queued.id, job);
  }, 2400);

  return queued;
}

export function getMockJob(id: string): EnrichmentJob | undefined {
  return mockJobStore.get(id);
}

export function listMockJobs(limit = 50, offset = 0): { jobs: JobListItem[]; total: number } {
  const all = Array.from(mockJobStore.values()).map(
    (job): JobListItem => ({
      id: job.id,
      status: job.status,
      createdAt: job.dossier.metadata.generatedAt,
      updatedAt: job.dossier.metadata.generatedAt,
      identifierSummary: job.dossier.metadata.identifierSummary,
      requestedTiers: job.input.requestedTiers,
    }),
  );
  return { jobs: all.slice(offset, offset + limit), total: all.length };
}
