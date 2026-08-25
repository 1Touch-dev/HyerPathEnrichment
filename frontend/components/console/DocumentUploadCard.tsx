"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { UploadCloud } from "lucide-react";
import { Button } from "@/components/ui/button";
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
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Upload a document</CardTitle>
        <CardDescription>
          Upload a CV or cover letter (.pdf, .doc, .docx) to extract structured data.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <Label htmlFor="document-file">File</Label>
            <Input
              id="document-file"
              type="file"
              accept=".pdf,.doc,.docx"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
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
          <Button type="submit" disabled={!file || uploadMutation.isPending} className="w-fit">
            <UploadCloud className="mr-2 size-4" />
            {uploadMutation.isPending ? "Uploading…" : "Upload"}
          </Button>
        </form>

        {job ? (
          <div className="flex flex-col gap-2 rounded-lg border p-4">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium">Processing status</span>
              <DocumentStatusBadge status={job.status} />
            </div>
            <Progress
              value={job.progress * 100}
              className={isPolling && !isTerminal ? "animate-pulse" : ""}
            />
            {job.error ? <p className="text-sm text-destructive">{job.error}</p> : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
