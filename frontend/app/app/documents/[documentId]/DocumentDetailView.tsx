"use client";

import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CompletenessBanner, CvChatWidget, CvFeedbackPanel } from "@/features/cv-management";

interface DocumentDetailViewProps {
  documentId: string;
}

export function DocumentDetailView({ documentId }: DocumentDetailViewProps) {
  const [showChat, setShowChat] = useState(false);

  return (
    <div className="space-y-4">
      <CompletenessBanner documentId={documentId} onStartChat={() => setShowChat(true)} />

      {showChat && (
        <CvChatWidget documentId={documentId} onComplete={() => setShowChat(false)} />
      )}

      <Tabs defaultValue="feedback">
        <TabsList>
          <TabsTrigger value="feedback">AI feedback</TabsTrigger>
        </TabsList>
        <TabsContent value="feedback">
          <CvFeedbackPanel documentId={documentId} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
