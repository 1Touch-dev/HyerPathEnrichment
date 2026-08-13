"use client";

import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cvManagementKeys } from "../api/keys";
import {
  useAcceptCvBullet,
  useCvFeedback,
  useCvFeedbackJobStatus,
  useRequestCvFeedback,
} from "../hooks/useCvFeedback";

interface CvFeedbackPanelProps {
  documentId: string;
}

export function CvFeedbackPanel({ documentId }: CvFeedbackPanelProps) {
  const queryClient = useQueryClient();
  const [pendingJobId, setPendingJobId] = useState<string | null>(null);

  const { data: report, isLoading } = useCvFeedback(documentId);
  const jobStatus = useCvFeedbackJobStatus(pendingJobId);
  const requestFeedback = useRequestCvFeedback(documentId);
  const acceptBullet = useAcceptCvBullet(documentId);

  const isGenerating =
    requestFeedback.isPending ||
    (pendingJobId !== null && jobStatus.data?.status !== "completed" && jobStatus.data?.status !== "failed");

  // Once the real job reaches a terminal state, stop tracking it and refetch the
  // report (on success) so the UI updates without a manual page reload.
  useEffect(() => {
    if (!jobStatus.data) return;
    if (jobStatus.data.status === "completed") {
      void queryClient.invalidateQueries({ queryKey: cvManagementKeys.feedback(documentId) });
      setPendingJobId(null);
    } else if (jobStatus.data.status === "failed") {
      setPendingJobId(null);
    }
  }, [jobStatus.data, queryClient, documentId]);

  if (isLoading) return <div className="animate-pulse h-48 rounded-lg bg-muted" />;

  if (isGenerating) {
    return <p className="text-sm text-muted-foreground">Analyzing your CV...</p>;
  }

  if (!report) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-muted-foreground">No feedback generated yet.</p>
        <Button
          onClick={() =>
            requestFeedback.mutate(undefined, {
              onSuccess: (data) => setPendingJobId(data.jobId),
            })
          }
          disabled={requestFeedback.isPending}
        >
          {requestFeedback.isPending ? "Requesting..." : "Get AI feedback"}
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium">ATS score</span>
        <Badge>{report.atsScore}/100</Badge>
      </div>

      {report.strengths.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold">Strengths</h3>
          <ul className="mt-1 list-inside list-disc text-sm text-muted-foreground">
            {report.strengths.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}

      {report.rewrittenBullets.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold">Suggested rewrites</h3>
          <div className="mt-2 space-y-3">
            {report.rewrittenBullets.map((bullet, index) => (
              <div key={index} className="rounded-lg border p-3">
                <p className="text-sm text-muted-foreground line-through">{bullet.original}</p>
                <p className="mt-1 text-sm font-medium">{bullet.rewritten}</p>
                <p className="mt-1 text-xs text-muted-foreground">{bullet.rationale}</p>
                <Button
                  size="sm"
                  variant="outline"
                  className="mt-2"
                  onClick={() => acceptBullet.mutate({ reportId: report.reportId, bulletIndex: index })}
                  disabled={acceptBullet.isPending}
                >
                  Use this version
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
