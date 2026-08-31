"use client";

import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { UpgradeButton } from "@/features/billing";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
  const [targetRole, setTargetRole] = useState("");

  const { data: report, isLoading } = useCvFeedback(documentId);
  const jobStatus = useCvFeedbackJobStatus(pendingJobId);
  const requestFeedback = useRequestCvFeedback(documentId);
  const acceptBullet = useAcceptCvBullet(documentId);

  const isGenerating =
    requestFeedback.isPending ||
    (pendingJobId !== null &&
      jobStatus.data?.status !== "completed" &&
      jobStatus.data?.status !== "failed");

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
        <Input
          value={targetRole}
          onChange={(e) => setTargetRole(e.target.value)}
          placeholder="Target role (optional, e.g. Senior Backend Engineer)"
          aria-label="Target role"
        />
        <Button
          onClick={() =>
            requestFeedback.mutate(targetRole.trim() || undefined, {
              onSuccess: (data) => setPendingJobId(data.jobId),
            })
          }
          disabled={requestFeedback.isPending}
        >
          {requestFeedback.isPending ? "Requesting..." : "Get AI feedback"}
        </Button>
        {requestFeedback.isError ? (
          <p className="text-sm text-destructive">
            {requestFeedback.error instanceof Error
              ? requestFeedback.error.message
              : "Couldn't request feedback, please try again."}
          </p>
        ) : null}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {report.isBlurred ? (
        <div className="rounded-lg border border-dashed p-4">
          <p className="text-sm text-muted-foreground">
            Premium CV feedback is blurred on free accounts. Upgrade to unlock strengths,
            improvements, and rewritten bullets.
          </p>
          <div className="mt-3">
            <UpgradeButton />
          </div>
        </div>
      ) : null}

      <div className="flex items-center gap-2">
        <span className="text-sm font-medium">ATS score</span>
        <Badge>{report.atsScore}/100</Badge>
      </div>

      {report.strengths.length > 0 && (
        <div className={report.isBlurred ? "blur-sm select-none" : undefined}>
          <h3 className="text-sm font-semibold">Strengths</h3>
          <ul className="mt-1 list-inside list-disc text-sm text-muted-foreground">
            {report.strengths.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}

      {report.improvements.length > 0 && (
        <div className={report.isBlurred ? "blur-sm select-none" : undefined}>
          <h3 className="text-sm font-semibold">Improvements</h3>
          <ul className="mt-1 list-inside list-disc text-sm text-muted-foreground">
            {report.improvements.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      {report.rewrittenBullets.length > 0 && (
        <div className={report.isBlurred ? "blur-sm select-none" : undefined}>
          <h3 className="text-sm font-semibold">Suggested rewrites</h3>
          <div className="mt-2 space-y-3">
            {report.rewrittenBullets.map((bullet, index) => {
              const isAccepted = report.acceptedBulletIndices.includes(index);
              return (
                <div key={index} className="rounded-lg border p-3">
                  <p className="text-sm text-muted-foreground line-through">{bullet.original}</p>
                  <p className="mt-1 text-sm font-medium">{bullet.rewritten}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{bullet.rationale}</p>
                  {isAccepted ? (
                    <Badge variant="outline" className="mt-2 gap-1 text-green-700">
                      ✓ Applied
                    </Badge>
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      className="mt-2"
                      onClick={() =>
                        acceptBullet.mutate({ reportId: report.reportId, bulletIndex: index })
                      }
                      disabled={acceptBullet.isPending}
                    >
                      Use this version
                    </Button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
