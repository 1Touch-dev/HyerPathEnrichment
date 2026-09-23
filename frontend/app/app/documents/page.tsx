"use client";

import {
  ShellPageHeader,
  ShellPageHeaderContent,
  ShellPageHeaderDescription,
  ShellPageHeaderEyebrow,
  ShellPageHeaderTitle,
  ShellSection,
  ShellSectionHeader,
  ShellSectionHeaderContent,
  ShellSectionHeaderDescription,
  ShellSectionHeaderTitle,
} from "@/components/layout/ShellPage";
import { DocumentUploadCard } from "@/components/console/DocumentUploadCard";
import { DocumentList } from "@/components/console/DocumentList";
import { DocumentSearchPanel } from "@/components/console/DocumentSearchPanel";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useDocuments } from "@/features/documents";

export default function DocumentsPage() {
  const { data: documents, isLoading } = useDocuments();

  return (
    <div className="flex flex-col gap-6">
      <ShellPageHeader>
        <ShellPageHeaderContent>
          <ShellPageHeaderEyebrow>Candidate workspace</ShellPageHeaderEyebrow>
          <ShellPageHeaderTitle>Documents</ShellPageHeaderTitle>
          <ShellPageHeaderDescription>
            Upload your CV or cover letter to power job matching, then browse and search your
            documents below.
          </ShellPageHeaderDescription>
        </ShellPageHeaderContent>
      </ShellPageHeader>

      {/* White upload well — no muted/oxblood surface fills (Figma `22 /app/documents`). */}
      <ShellSection>
        <div className="rounded-[1.25rem] border border-dashed border-primary/30 bg-surface p-1 shadow-panel sm:p-2">
          <DocumentUploadCard />
        </div>
      </ShellSection>

      <ShellSection>
        <ShellSectionHeader>
          <ShellSectionHeaderContent>
            <ShellSectionHeaderTitle>Your document workspace</ShellSectionHeaderTitle>
            <ShellSectionHeaderDescription>
              Switch between the full list and document search without leaving the candidate shell.
            </ShellSectionHeaderDescription>
          </ShellSectionHeaderContent>
        </ShellSectionHeader>

        <Tabs defaultValue="documents">
          <TabsList>
            <TabsTrigger value="documents">Your documents</TabsTrigger>
            <TabsTrigger value="search">Search</TabsTrigger>
          </TabsList>
          <TabsContent value="documents" className="mt-4">
            <div className="overflow-x-auto rounded-[1.25rem] border border-border/70 bg-surface p-1 shadow-panel sm:p-2">
              <DocumentList documents={documents ?? []} loading={isLoading} />
            </div>
          </TabsContent>
          <TabsContent value="search" className="mt-4">
            <div className="rounded-[1.25rem] border border-border/70 bg-surface p-1 shadow-panel sm:p-2">
              <DocumentSearchPanel />
            </div>
          </TabsContent>
        </Tabs>
      </ShellSection>
    </div>
  );
}
