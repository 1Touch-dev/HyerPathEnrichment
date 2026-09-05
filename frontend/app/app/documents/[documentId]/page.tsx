"use client";

import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowLeft, RefreshCw, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DocumentStatusBadge } from "@/components/console/DocumentStatusBadge";
import { EmptyState } from "@/components/console/EmptyState";
import { RawJsonPanel } from "@/components/console/RawJsonPanel";
import { useDeleteDocument, useDocument, useReprocessDocument } from "@/features/documents";
import { CompletenessBanner, CvChatWidget, CvFeedbackPanel } from "@/features/cv-management";
import { formatApiErrorMessage } from "@/src/lib/format-api-error";

function LoadingSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Skeleton className="h-8 w-48" />
        <Skeleton className="mt-2 h-4 w-96" />
      </div>
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-32" />
        </CardHeader>
        <CardContent className="space-y-3">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
        </CardContent>
      </Card>
    </div>
  );
}

export default function DocumentDetailPage() {
  const params = useParams<{ documentId: string }>();
  const router = useRouter();
  const documentId = params.documentId;

  const { data: doc, isLoading, error } = useDocument(documentId);
  const reprocessMutation = useReprocessDocument();
  const deleteMutation = useDeleteDocument();
  const [showChat, setShowChat] = useState(false);

  const handleReprocess = async () => {
    try {
      await reprocessMutation.mutateAsync(documentId);
      toast.success("Reprocessing started", {
        description: "The document has been queued for reprocessing.",
      });
    } catch (err) {
      toast.error("Reprocess failed", { description: formatApiErrorMessage(err) });
    }
  };

  const handleDelete = async () => {
    const confirmed = window.confirm("Delete this document? This cannot be undone.");
    if (!confirmed) return;
    try {
      await deleteMutation.mutateAsync(documentId);
      toast.success("Document deleted");
      router.push("/app/documents");
    } catch (err) {
      toast.error("Delete failed", { description: formatApiErrorMessage(err) });
    }
  };

  if (isLoading && !doc) {
    return <LoadingSkeleton />;
  }

  if (error && !doc) {
    const isNotFound = error.message?.includes("404") || error.message?.includes("not found");
    return (
      <div className="flex flex-col gap-4">
        <Button variant="ghost" onClick={() => router.push("/app/documents")} className="w-fit">
          <ArrowLeft className="mr-2 size-4" />
          Back to Documents
        </Button>
        <Alert variant="destructive">
          <AlertDescription>
            {isNotFound
              ? `Document ${documentId} not found. It may have been deleted.`
              : formatApiErrorMessage(error)}
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  if (!doc) {
    return (
      <div className="flex flex-col gap-4">
        <Button variant="ghost" onClick={() => router.push("/app/documents")} className="w-fit">
          <ArrowLeft className="mr-2 size-4" />
          Back to Documents
        </Button>
        <EmptyState title="Document not found" description={`No document with id ${documentId}`} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <Button
            variant="ghost"
            onClick={() => router.push("/app/documents")}
            className="mb-2 w-fit"
          >
            <ArrowLeft className="mr-2 size-4" />
            Back to Documents
          </Button>
          <h1 className="text-2xl font-semibold tracking-tight">{doc.originalFilename}</h1>
          <p className="font-mono text-sm text-muted-foreground">{doc.documentId}</p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => void handleReprocess()}
            disabled={reprocessMutation.isPending}
          >
            <RefreshCw className="mr-2 size-4" />
            Reprocess
          </Button>
          <Button
            variant="destructive"
            onClick={() => void handleDelete()}
            disabled={deleteMutation.isPending}
          >
            <Trash2 className="mr-2 size-4" />
            Delete
          </Button>
        </div>
      </div>

      <CompletenessBanner documentId={documentId} onStartChat={() => setShowChat(true)} />

      {showChat && <CvChatWidget documentId={documentId} onComplete={() => setShowChat(false)} />}

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Metadata</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-muted-foreground">Type</dt>
              <dd>{doc.documentType === "cv" ? "CV" : "Cover letter"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Status</dt>
              <dd>
                <DocumentStatusBadge status={doc.processingStatus} />
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Size</dt>
              <dd>{formatFileSize(doc.fileSizeBytes)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Created</dt>
              <dd>{formatDate(doc.createdAt)}</dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      <Tabs defaultValue="feedback">
        <TabsList>
          <TabsTrigger value="feedback">AI feedback</TabsTrigger>
        </TabsList>
        <TabsContent value="feedback">
          <CvFeedbackPanel documentId={documentId} />
        </TabsContent>
      </Tabs>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Raw text</CardTitle>
        </CardHeader>
        <CardContent>
          {doc.rawText ? (
            <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-md bg-muted/30 p-4 text-xs">
              {doc.rawText}
            </pre>
          ) : (
            <p className="text-sm text-muted-foreground">
              No extracted text is available yet — this appears once processing completes.
            </p>
          )}
        </CardContent>
      </Card>

      <div>
        <h2 className="mb-2 text-lg font-semibold">Extracted CV data</h2>
        {doc.extractedData ? (
          <RawJsonPanel data={doc.extractedData} triggerLabel="Extracted data (JSON)" defaultOpen />
        ) : (
          <EmptyState
            title="No extracted data yet"
            description="Structured CV data appears here once processing completes."
          />
        )}
      </div>
    </div>
  );
}

function formatDate(value: string) {
  if (!value) return "—";
  return value.replace("T", " ").slice(0, 19);
}

function formatFileSize(bytes: number) {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
