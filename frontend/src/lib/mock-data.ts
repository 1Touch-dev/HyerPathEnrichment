import { EnrichmentJob, EnrichmentInput, RequestedTier, SocialHandle } from "@/src/lib/types";

const makeHandles = (username: string): SocialHandle[] => [
  {
    platform: "GitHub",
    username,
    profileUrl: `https://github.com/${username}`,
    confidence: 0.92,
    metadata: { provider: "GitRecon", matched: true },
  },
  {
    platform: "X",
    username,
    profileUrl: `https://x.com/${username}`,
    confidence: 0.75,
    metadata: { provider: "Sherlock", matched: true },
  },
  {
    platform: "LinkedIn",
    username,
    profileUrl: `https://linkedin.com/in/${username}`,
    confidence: 0.88,
    metadata: { provider: "Social Analyzer", matched: true },
  },
];

const normalizeIdentifierSummary = (input: EnrichmentInput) => {
  const values = [
    input.email,
    input.linkedinUrl,
    input.username,
    input.company,
    input.business,
    input.jobSearch,
  ].filter(Boolean);
  return values.join(" • ");
};

const SAMPLE_STABLE_ID = "job_alexhyrepath_demo";
const SAMPLE_STABLE_TIMESTAMP = "2026-01-01T12:00:00.000Z";

type MockJobOptions = {
  stableId?: string;
  stableGeneratedAt?: string;
};

export const createMockJob = (input: EnrichmentInput, options?: MockJobOptions): EnrichmentJob => {
  const username = input.username || input.email?.split("@")[0] || "candidate";
  const requestedTiers: RequestedTier[] = input.requestedTiers.length
    ? input.requestedTiers
    : ["tier1", "tier2", "tier3", "tier4"];
  const pipelineId = `pipe_${username}_${requestedTiers.join("_")}`;
  const jobId = options?.stableId ?? `job_${username}_${Date.now()}`;
  const generatedAt = options?.stableGeneratedAt ?? new Date().toISOString();

  return {
    id: jobId,
    status: "completed",
    input: {
      ...input,
      requestedTiers,
    },
    dossier: {
      photo: input.linkedinUrl
        ? {
            source: "linkedin-photo",
            assetUrl: "https://cdn.hyrepath.local/assets/linkedin-photo.jpg",
            capturedAt: generatedAt,
            confidence: 0.84,
          }
        : undefined,
      handles: makeHandles(username),
      emails: input.email
        ? [
            input.email,
            `${username}@${input.company?.toLowerCase().replace(/\s+/g, "") || "example"}.com`,
          ]
        : [`${username}@example.com`],
      verifiedEmails: [
        {
          value: input.email || `${username}@example.com`,
          status: "verified",
          confidence: 0.89,
          source: "Reacher",
        },
      ],
      github: {
        profile: `https://github.com/${username}`,
        organizations: input.company
          ? [input.company, "Open Source Collective"]
          : ["Open Source Collective"],
        publicCommits: 128,
      },
      coworkers: ["Jamie Flores", "Morgan Lee", "Taylor Patel"],
      jobs: input.jobSearch
        ? [
            {
              title: input.jobSearch,
              company: input.company || "Hyrepath Labs",
              location: "Remote",
              remote: true,
              source: "JobSpy",
            },
          ]
        : [
            {
              title: "Senior Platform Engineer",
              company: input.company || "Hyrepath Labs",
              location: "New York, NY",
              remote: true,
              source: "JobSpy",
            },
          ],
      business: input.business
        ? {
            name: input.business,
            address: "123 Market Street, San Francisco, CA",
            website: "https://www.example-business.com",
            rating: 4.7,
            phone: "+1 (415) 555-0133",
          }
        : undefined,
      confidence: [
        {
          label: "identity-match",
          score: 0.91,
          evidence: [
            "username agreement across 3 providers",
            "domain alignment",
            "LLM not required",
          ],
        },
        {
          label: "email-verification",
          score: 0.89,
          evidence: ["SMTP accepted mailbox", "not disposable", "cross-linked coworker domain"],
        },
        {
          label: "job-intel",
          score: input.jobSearch ? 0.78 : 0.66,
          evidence: ["provider normalized", "location confidence medium"],
        },
      ],
      sources: ["linkedin-photo", "Sherlock", "Social Analyzer", "GitRecon", "Reacher", "JobSpy"],
      metadata: {
        generatedAt,
        pipelineId,
        requestedTiers,
        identifierSummary: normalizeIdentifierSummary(input),
      },
    },
  };
};

export const sampleJobs = [
  createMockJob(
    {
      email: "alex@hyrepath.dev",
      linkedinUrl: "https://www.linkedin.com/in/alex-hyrepath",
      username: "alexhyrepath",
      company: "Hyrepath",
      jobSearch: "Staff Backend Engineer",
      requestedTiers: ["tier1", "tier2", "tier3", "tier4"],
    },
    { stableId: SAMPLE_STABLE_ID, stableGeneratedAt: SAMPLE_STABLE_TIMESTAMP },
  ),
];
