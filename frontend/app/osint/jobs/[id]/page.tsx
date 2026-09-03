"use client";

import { useParams } from "next/navigation";
import { JobDetailView } from "@/features/enrich";

export default function OsintJobDetailPage() {
  const { id } = useParams<{ id: string }>();

  return <JobDetailView jobId={id} jobsHref="/osint/jobs" />;
}
