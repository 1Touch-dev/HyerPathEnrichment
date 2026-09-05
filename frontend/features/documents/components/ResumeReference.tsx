"use client";

import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { DocumentSummary } from "@/src/lib/types";

/**
 * Shared résumé reference control for practice + outreach generate flows.
 * Shows the selected filename; when ≥2 ready docs exist, offers a picker.
 */
export function ResumeReference({
  documents,
  selectedId,
  onSelect,
  label = "Résumé reference",
}: {
  documents: DocumentSummary[];
  selectedId: string;
  onSelect: (id: string) => void;
  label?: string;
}) {
  const selected = documents.find((doc) => doc.documentId === selectedId) ?? documents[0];
  if (!selected) return null;

  if (documents.length < 2) {
    return (
      <div className="space-y-1">
        <Label>{label}</Label>
        <p className="text-sm text-muted-foreground">Using: {selected.originalFilename}</p>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <Label htmlFor="resumeSelect">{label}</Label>
      <p className="text-sm text-muted-foreground">Using: {selected.originalFilename}</p>
      <Select value={selected.documentId} onValueChange={onSelect}>
        <SelectTrigger id="resumeSelect" aria-label="Choose résumé">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {documents.map((doc) => (
            <SelectItem key={doc.documentId} value={doc.documentId}>
              {doc.originalFilename}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
