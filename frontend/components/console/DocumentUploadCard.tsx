"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { FileText, UploadCloud } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import { DocumentStatusBadge } from "@/components/console/DocumentStatusBadge";
import { formatFileSize } from "@/components/console/formatters";
import { documentKeys, useDocumentJobQuery, useUploadDocument } from "@/features/documents";
import { formatApiErrorMessage } from "@/src/lib/format-api-error";
import type { DocumentType } from "@/src/lib/types";

const TERMINAL_STATUSES = ["completed", "failed", "duplicate"];

export function DocumentUploadCard() {
  const queryClient = useQueryClient();
  const uploadMutation = useUploadDocument();
  const [file, setFile] = useState<File | null>(null);
  const [documentType, setDocumentType] = useState<DocumentType>("cv");
  const [activeJobId, setActiveJobId] = useState<string | undefined>(undefined);
  const notifiedJobRef = useRef<string | null>(null);

  const { data: job, isFetching: isPolling } = useDocumentJobQuery(activeJobId);

  useEffect(() => {
    if (!job || !activeJobId) return;
    if (!TERMINAL_STATUSES.includes(job.status)) return;
    if (notifiedJobRef.current === activeJobId) return;
    notifiedJobRef.current = activeJobId;

    if (job.status === "completed") {
      toast.success("Document processed", {
        description: "Your document finished processing.",
      });
      void queryClient.invalidateQueries({ queryKey: documentKeys.list() });
    } else if (job.status === "duplicate") {
      toast.info("Duplicate document", {
        description: "This document was already uploaded — no new copy was created.",
      });
      void queryClient.invalidateQueries({ queryKey: documentKeys.list() });
    } else {
      toast.error("Processing failed", {
        description: job.error ?? "The document could not be processed.",
      });
    }
  }, [job, activeJobId, queryClient]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!file) return;

    notifiedJobRef.current = null;
    try {
      const result = await uploadMutation.mutateAsync({ file, documentType });
      setActiveJobId(result.jobId);
      toast.success("Upload started", { description: result.message });
      setFile(null);
    } catch (error) {
      toast.error("Upload failed", { description: formatApiErrorMessage(error) });
    }
  };

  const isTerminal = job ? TERMINAL_STATUSES.includes(job.status) : false;

  return (
    <Card className="overflow-hidden">
      <CardHeader className="gap-4 border-b border-border/60 bg-surface-muted/40">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-2">
            <p className="text-[0.7rem] font-semibold uppercase tracking-[0.16em] text-subtle-foreground">
              Documents
            </p>
            <CardTitle className="text-xl">Upload a document</CardTitle>
            <CardDescription>
              Add a CV or cover letter to power downstream matching, drafting, and document search.
            </CardDescription>
          </div>
          <Badge variant="outline">PDF, DOC, DOCX</Badge>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-5 pt-6">
        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_240px_auto]">
            <div className="flex flex-col gap-2">
              <Label htmlFor="document-file">File</Label>
              <Input
                id="document-file"
                type="file"
                accept=".pdf,.doc,.docx"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
              {file ? (
                <div className="flex items-center gap-2 rounded-lg border border-border/70 bg-surface p-3 text-sm">
                  <FileText className="size-4 text-primary" />
                  <div className="min-w-0">
                    <p className="truncate font-medium text-foreground">{file.name}</p>
                    <p className="text-xs text-muted-foreground">{formatFileSize(file.size)}</p>
                  </div>
                </div>
              ) : null}
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="document-type">Document type</Label>
              <Select
                value={documentType}
                onValueChange={(value) => setDocumentType(value as DocumentType)}
              >
                <SelectTrigger id="document-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="cv">CV / Resume</SelectItem>
                  <SelectItem value="cover_letter">Cover letter</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-end">
              <Button
                type="submit"
                disabled={!file || uploadMutation.isPending}
                className="w-full lg:w-fit"
              >
                <UploadCloud className="mr-2 size-4" />
                {uploadMutation.isPending ? "Uploading…" : "Upload"}
              </Button>
            </div>
          </div>
        </form>

        {job ? (
          <div className="rounded-xl border border-border/70 bg-surface p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-sm font-medium text-foreground">Latest processing status</p>
                <p className="font-mono text-xs text-muted-foreground">{job.jobId}</p>
              </div>
              <DocumentStatusBadge status={job.status} />
            </div>
            <div className="mt-4 space-y-2">
              <Progress
                value={job.progress * 100}
                className={isPolling && !isTerminal ? "animate-pulse" : ""}
              />
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>{Math.round(job.progress * 100)}% complete</span>
                <span>{isTerminal ? "Finished" : "Processing…"}</span>
              </div>
              {job.error ? <p className="text-sm text-destructive">{job.error}</p> : null}
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
