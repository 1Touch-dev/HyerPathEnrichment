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

      <ShellSection surface="muted">
        <DocumentUploadCard />
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
          <TabsContent value="documents">
            <DocumentList documents={documents ?? []} loading={isLoading} />
          </TabsContent>
          <TabsContent value="search">
            <DocumentSearchPanel />
          </TabsContent>
        </Tabs>
      </ShellSection>
    </div>
  );
}
