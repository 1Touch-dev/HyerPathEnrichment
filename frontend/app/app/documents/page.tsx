"use client";

import { DocumentUploadCard } from "@/components/console/DocumentUploadCard";
import { DocumentList } from "@/components/console/DocumentList";
import { DocumentSearchPanel } from "@/components/console/DocumentSearchPanel";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useDocuments } from "@/features/documents";

export default function DocumentsPage() {
  const { data: documents, isLoading } = useDocuments();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Documents</h1>
        <p className="text-sm text-muted-foreground">
          Upload your CV or cover letter to power job matching, then browse and search your
          documents below.
        </p>
      </div>

      <DocumentUploadCard />

      <Tabs defaultValue="documents">
        <TabsList>
          <TabsTrigger value="documents">Your documents</TabsTrigger>
          <TabsTrigger value="search">Search</TabsTrigger>
        </TabsList>
        <TabsContent value="documents">
          <DocumentList documents={documents ?? []} loading={isLoading} />
        </TabsContent>
        <TabsContent value="search">
          <DocumentSearchPanel />
        </TabsContent>
      </Tabs>
    </div>
  );
}
