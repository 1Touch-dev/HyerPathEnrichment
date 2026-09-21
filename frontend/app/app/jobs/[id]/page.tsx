"use client";

import { useParams, useSearchParams } from "next/navigation";
import { JobDetailView } from "@/features/enrich";

export default function CandidateJobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryString = useSearchParams().toString();
  const jobsHref = `/app/jobs${queryString ? `?${queryString}` : ""}`;

  return <JobDetailView jobId={id} jobsHref={jobsHref} />;
}
