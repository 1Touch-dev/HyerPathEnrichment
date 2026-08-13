"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAcceptCvBullet, useCvFeedback, useRequestCvFeedback } from "../hooks/useCvFeedback";

interface CvFeedbackPanelProps {
  documentId: string;
}

export function CvFeedbackPanel({ documentId }: CvFeedbackPanelProps) {
  const { data: report, isLoading } = useCvFeedback(documentId, { poll: true });
  const requestFeedback = useRequestCvFeedback(documentId);
  const acceptBullet = useAcceptCvBullet(documentId);

  if (isLoading) return <div className="animate-pulse h-48 rounded-lg bg-muted" />;

  if (!report || report.status === "failed") {
    return (
      <div className="space-y-3">
        <p className="text-sm text-muted-foreground">No feedback generated yet.</p>
        <Button onClick={() => requestFeedback.mutate(undefined)} disabled={requestFeedback.isPending}>
          {requestFeedback.isPending ? "Requesting..." : "Get AI feedback"}
        </Button>
      </div>
    );
  }

  if (report.status === "pending" || report.status === "processing") {
    return <p className="text-sm text-muted-foreground">Analyzing your CV...</p>;
  }

  return (
    <div className="space-y-6">
      {report.atsScore !== null && (
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">ATS score</span>
          <Badge>{report.atsScore}/100</Badge>
        </div>
      )}

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
