"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { fetchDocuments } from "@/src/lib/api-client";
import { formatApiErrorMessage } from "@/src/lib/format-api-error";
import { storeQuestions, useCreatePracticeSession, useQuestions } from "@/features/practice";

const JOB_ROLES = [
  { value: "software_engineer", label: "Software Engineer" },
  { value: "data_scientist", label: "Data Scientist" },
  { value: "product_manager", label: "Product Manager" },
  { value: "devops_engineer", label: "DevOps Engineer" },
] as const;

const CATEGORIES = [
  { value: "any", label: "Any" },
  { value: "behavioral", label: "Behavioral" },
  { value: "technical", label: "Technical" },
  { value: "system_design", label: "System Design" },
] as const;

const DIFFICULTIES = [
  { value: "any", label: "Any" },
  { value: "easy", label: "Easy" },
  { value: "medium", label: "Medium" },
  { value: "hard", label: "Hard" },
] as const;

/**
 * Deviation from the plan's §10.5 text: the plan describes an inline `<input type="file">`
 * upload widget reusing `POST /api/documents/upload` for candidates with no processed CV.
 * Verified directly that neither that BFF route nor any file-input upload UI exists
 * anywhere in this frontend yet (Module 2's gap, not Module 3's). Building a full upload
 * widget here is out of this module's scope, so instead: when no completed document
 * exists, the personalize checkbox is disabled with an inline note linking to
 * `/app/documents` (Module 2's existing upload page) rather than a dead-end file input.
 */
export function PracticeLandingView() {
  const router = useRouter();
  const [jobRole, setJobRole] = useState<string>(JOB_ROLES[0].value);
  const [category, setCategory] = useState<string>("any");
  const [difficulty, setDifficulty] = useState<string>("any");
  const [personalize, setPersonalize] = useState(false);

  const createSessionMutation = useCreatePracticeSession();
  const questionsMutation = useQuestions();

  const { data: documents } = useQuery({
    queryKey: ["documents", "list"],
    queryFn: async () => (await fetchDocuments()).data,
  });

  const hasCompletedDocument = Boolean(
    documents?.some((doc) => doc.processingStatus === "completed"),
  );

  const isStarting = createSessionMutation.isPending || questionsMutation.isPending;
  const error = createSessionMutation.error ?? questionsMutation.error;

  async function handleStart() {
    const session = await createSessionMutation.mutateAsync({ sessionType: "mock_interview" });
    const result = await questionsMutation.mutateAsync({
      jobRole,
      category: category === "any" ? undefined : category,
      difficulty: difficulty === "any" ? undefined : difficulty,
      personalize: personalize && hasCompletedDocument,
    });
    storeQuestions(session.id, result.questions);
    router.push(`/app/practice/${session.id}`);
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Interview prep</h1>
        <p className="text-sm text-muted-foreground">
          Pick a role and practice with AI-scored mock interview questions.
        </p>
      </div>

      {error ? (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{formatApiErrorMessage(error)}</AlertDescription>
        </Alert>
      ) : null}

      <div className="space-y-4 rounded-lg border p-4">
        <div>
          <Label htmlFor="jobRole">Job role</Label>
          <Select value={jobRole} onValueChange={setJobRole}>
            <SelectTrigger id="jobRole">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {JOB_ROLES.map((role) => (
                <SelectItem key={role.value} value={role.value}>
                  {role.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label htmlFor="category">Category</Label>
            <Select value={category} onValueChange={setCategory}>
              <SelectTrigger id="category">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CATEGORIES.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label htmlFor="difficulty">Difficulty</Label>
            <Select value={difficulty} onValueChange={setDifficulty}>
              <SelectTrigger id="difficulty">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {DIFFICULTIES.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Checkbox
            id="personalize"
            checked={personalize}
            disabled={!hasCompletedDocument}
            onCheckedChange={(checked) => setPersonalize(checked === true)}
          />
          <Label htmlFor="personalize">Personalize with my résumé</Label>
        </div>
        {!hasCompletedDocument && (
          <p className="pl-6 text-sm text-muted-foreground">
            Upload a CV first to personalize your questions.{" "}
            <Link href="/app/documents" className="underline">
              Go to Documents
            </Link>
          </p>
        )}

        <Button onClick={handleStart} disabled={isStarting} className="w-full" size="lg">
          {isStarting ? "Starting..." : "Start practice"}
        </Button>
      </div>
    </div>
  );
}
