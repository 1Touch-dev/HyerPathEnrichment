"use client";

import { useEffect } from "react";
import Link from "next/link";
import { ChevronDown, ChevronUp, X, ExternalLink } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { JobStatusBadge } from "@/components/console/JobStatusBadge";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { useLocalStorageJobs } from "@/hooks/useLocalStorageJobs";
import { useState } from "react";

type JobQueuePanelProps = {
  onJobStatusUpdate?: (jobId: string, status: "completed" | "failed" | "suppressed") => void;
};

export function JobQueuePanel({ onJobStatusUpdate }: JobQueuePanelProps) {
  const { jobs, activeJobs, removeJob, clearCompleted } = useLocalStorageJobs();
  const [isOpen, setIsOpen] = useState(true);

  // Notify parent of status changes for completed jobs
  useEffect(() => {
    if (!onJobStatusUpdate) return;
    
    jobs.forEach((job) => {
      if (job.status === "completed" || job.status === "failed" || job.status === "suppressed") {
        if (job.completedAt && Date.now() - job.completedAt < 1000) {
          onJobStatusUpdate(job.id, job.status);
        }
      }
    });
  }, [jobs, onJobStatusUpdate]);

  if (jobs.length === 0) {
    return null;
  }

  const completedJobs = jobs.filter(
    (job) => job.status === "completed" || job.status === "failed" || job.status === "suppressed"
  );

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CardTitle className="text-base">
                Active Jobs
                {activeJobs.length > 0 && (
                  <span className="ml-2 rounded-full bg-primary px-2 py-0.5 text-xs text-primary-foreground">
                    {activeJobs.length}
                  </span>
                )}
              </CardTitle>
            </div>
            <div className="flex items-center gap-2">
              {completedJobs.length > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={clearCompleted}
                  className="text-xs"
                >
                  Clear completed
                </Button>
              )}
              <CollapsibleTrigger asChild>
                <Button variant="ghost" size="sm">
                  {isOpen ? (
                    <ChevronUp className="size-4" />
                  ) : (
                    <ChevronDown className="size-4" />
                  )}
                </Button>
              </CollapsibleTrigger>
            </div>
          </div>
        </CardHeader>
        <CollapsibleContent>
          <CardContent className="pt-0">
            <div className="space-y-2">
              {jobs.map((job) => (
                <div
                  key={job.id}
                  className="flex items-center justify-between gap-3 rounded-lg border p-3"
                >
                  <div className="flex min-w-0 flex-1 items-center gap-3">
                    <JobStatusBadge status={job.status} />
                    <code className="truncate text-xs text-muted-foreground">{job.id}</code>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button variant="ghost" size="sm" asChild>
                      <Link href={`/app/jobs/${job.id}`}>
                        <ExternalLink className="size-3" />
                      </Link>
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => removeJob(job.id)}
                    >
                      <X className="size-3" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  );
}
