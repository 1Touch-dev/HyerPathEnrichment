"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { RangeSlider } from "@/components/ui/range-slider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ResumeReference } from "@/features/documents/components/ResumeReference";
import { useJdPracticeQuestions } from "@/features/jd-practice";
import { useMatches } from "@/features/job-matching/hooks/useMatches";
import { storeQuestions, useCreatePracticeSession, useQuestions } from "@/features/practice";
import { fetchDocuments } from "@/src/lib/api-client";
import { formatApiErrorMessage } from "@/src/lib/format-api-error";
import type { DocumentSummary, InterviewQuestion, JdPracticeQuestion } from "@/src/lib/types";

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

const QUESTION_COUNT_MIN = 5;
const QUESTION_COUNT_MAX = 15;

function isReadyDocument(doc: DocumentSummary): boolean {
  return doc.processingStatus === "completed" || doc.processingStatus === "embedded";
}

function toInterviewQuestions(questions: JdPracticeQuestion[]): InterviewQuestion[] {
  return questions.map((q) => ({
    id: q.id,
    questionText: q.questionText,
    category: q.category,
    difficulty: q.difficulty,
    jobRoles: [],
    technologies: [],
    isPersonalized: true,
  }));
}

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
  const [practiceMode, setPracticeMode] = useState<"role" | "jd">("role");
  const [jdSource, setJdSource] = useState<"tracked" | "paste">("tracked");
  const [jobRole, setJobRole] = useState<string>(JOB_ROLES[0].value);
  const [category, setCategory] = useState<string>("any");
  const [difficulty, setDifficulty] = useState<string>("any");
  const [questionCount, setQuestionCount] = useState(5);
  const [personalize, setPersonalize] = useState(false);
  const [documentId, setDocumentId] = useState<string | undefined>(undefined);
  const [selectedMatchId, setSelectedMatchId] = useState<string>("");
  const [pastedJd, setPastedJd] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [company, setCompany] = useState("");

  const createSessionMutation = useCreatePracticeSession();
  const questionsMutation = useQuestions();
  const jdQuestionsMutation = useJdPracticeQuestions();

  const { data: documents } = useQuery({
    queryKey: ["documents", "list"],
    queryFn: async () => (await fetchDocuments()).data,
  });

  const { data: matchesData, isLoading: matchesLoading } = useMatches(50, 0);

  const readyDocuments = useMemo(() => {
    const ready = (documents ?? []).filter(isReadyDocument);
    return [...ready].sort(
      (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
    );
  }, [documents]);

  const latestDocument = readyDocuments[0];
  const selectedDocument =
    readyDocuments.find((doc) => doc.documentId === documentId) ?? latestDocument;

  useEffect(() => {
    if (!latestDocument) {
      setDocumentId(undefined);
      return;
    }
    setDocumentId((current) => {
      if (current && readyDocuments.some((doc) => doc.documentId === current)) {
        return current;
      }
      return latestDocument.documentId;
    });
  }, [latestDocument, readyDocuments]);

  useEffect(() => {
    const matches = matchesData?.matches ?? [];
    if (!selectedMatchId && matches.length > 0) {
      setSelectedMatchId(matches[0].matchId);
    }
  }, [matchesData, selectedMatchId]);

  const hasReadyDocument = readyDocuments.length > 0;
  const count = questionCount;

  const isStarting =
    createSessionMutation.isPending || questionsMutation.isPending || jdQuestionsMutation.isPending;
  const error = createSessionMutation.error ?? questionsMutation.error ?? jdQuestionsMutation.error;

  async function handleStartRole() {
    const session = await createSessionMutation.mutateAsync({ sessionType: "mock_interview" });
    const result = await questionsMutation.mutateAsync({
      jobRole,
      category: category === "any" ? undefined : category,
      difficulty: difficulty === "any" ? undefined : difficulty,
      count,
      personalize: personalize && hasReadyDocument,
      documentId: personalize && hasReadyDocument ? selectedDocument?.documentId : undefined,
    });
    storeQuestions(session.id, result.questions);
    router.push(`/app/practice/${session.id}`);
  }

  async function handleStartJd() {
    const categoryArg = category === "any" ? undefined : category;
    const difficultyArg = difficulty === "any" ? undefined : difficulty;
    const resumeId = hasReadyDocument ? selectedDocument?.documentId : undefined;

    const result =
      jdSource === "tracked"
        ? await jdQuestionsMutation.mutateAsync({
            jobMatchId: selectedMatchId,
            category: categoryArg,
            difficulty: difficultyArg,
            count,
            documentId: resumeId,
          })
        : await jdQuestionsMutation.mutateAsync({
            jobDescription: pastedJd.trim(),
            jobTitle: jobTitle.trim() || undefined,
            company: company.trim() || undefined,
            category: categoryArg,
            difficulty: difficultyArg,
            count,
            documentId: resumeId,
          });

    storeQuestions(result.practiceSessionId, toInterviewQuestions(result.questions));
    router.push(`/app/practice/${result.practiceSessionId}`);
  }

  async function handleStart() {
    if (practiceMode === "role") {
      await handleStartRole();
      return;
    }
    await handleStartJd();
  }

  const canStartJd =
    jdSource === "tracked" ? Boolean(selectedMatchId) : pastedJd.trim().length >= 50;

  const canStart = practiceMode === "role" ? true : canStartJd;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Interview prep</h1>
        <p className="text-sm text-muted-foreground">
          Practice with AI-scored mock interview questions by role or job description.
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
          <Label className="mb-2 block">Practice mode</Label>
          <RadioGroup
            value={practiceMode}
            onValueChange={(value) => setPracticeMode(value as "role" | "jd")}
            className="grid gap-3 sm:grid-cols-2"
          >
            <label className="flex cursor-pointer items-start gap-3 rounded-lg border p-3">
              <RadioGroupItem value="role" id="mode-role" className="mt-1" />
              <div>
                <Label htmlFor="mode-role" className="cursor-pointer">
                  Role-based
                </Label>
                <p className="text-xs text-muted-foreground">Pick a target role from the bank.</p>
              </div>
            </label>
            <label className="flex cursor-pointer items-start gap-3 rounded-lg border p-3">
              <RadioGroupItem value="jd" id="mode-jd" className="mt-1" />
              <div>
                <Label htmlFor="mode-jd" className="cursor-pointer">
                  Job description
                </Label>
                <p className="text-xs text-muted-foreground">Use a tracked job or paste a JD.</p>
              </div>
            </label>
          </RadioGroup>
        </div>

        {practiceMode === "role" ? (
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
        ) : (
          <div className="space-y-4">
            <div>
              <Label className="mb-2 block">JD source</Label>
              <RadioGroup
                value={jdSource}
                onValueChange={(value) => setJdSource(value as "tracked" | "paste")}
                className="grid gap-3 sm:grid-cols-2"
              >
                <label className="flex cursor-pointer items-center gap-3 rounded-lg border p-3">
                  <RadioGroupItem value="tracked" id="jd-tracked" />
                  <Label htmlFor="jd-tracked" className="cursor-pointer">
                    Tracked job
                  </Label>
                </label>
                <label className="flex cursor-pointer items-center gap-3 rounded-lg border p-3">
                  <RadioGroupItem value="paste" id="jd-paste" />
                  <Label htmlFor="jd-paste" className="cursor-pointer">
                    Paste JD
                  </Label>
                </label>
              </RadioGroup>
            </div>

            {jdSource === "tracked" ? (
              <div>
                <Label htmlFor="trackedJob">Tracked job</Label>
                {matchesLoading ? (
                  <p className="text-sm text-muted-foreground">Loading matches…</p>
                ) : (matchesData?.matches.length ?? 0) === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No tracked jobs yet.{" "}
                    <Link href="/app/matches" className="underline">
                      Go to Job matching
                    </Link>
                  </p>
                ) : (
                  <Select value={selectedMatchId} onValueChange={setSelectedMatchId}>
                    <SelectTrigger id="trackedJob">
                      <SelectValue placeholder="Select a job" />
                    </SelectTrigger>
                    <SelectContent>
                      {matchesData?.matches.map((match) => (
                        <SelectItem key={match.matchId} value={match.matchId}>
                          {match.title} · {match.company}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </div>
            ) : (
              <div className="space-y-3">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <Label htmlFor="jobTitle">Job title (optional)</Label>
                    <Input
                      id="jobTitle"
                      value={jobTitle}
                      onChange={(e) => setJobTitle(e.target.value)}
                      placeholder="e.g. Backend Engineer"
                    />
                  </div>
                  <div>
                    <Label htmlFor="company">Company (optional)</Label>
                    <Input
                      id="company"
                      value={company}
                      onChange={(e) => setCompany(e.target.value)}
                      placeholder="e.g. Acme"
                    />
                  </div>
                </div>
                <div>
                  <Label htmlFor="pastedJd">Job description</Label>
                  <Textarea
                    id="pastedJd"
                    value={pastedJd}
                    onChange={(e) => setPastedJd(e.target.value)}
                    placeholder="Paste the full job description (at least 50 characters)."
                    rows={8}
                  />
                  {pastedJd.trim().length > 0 && pastedJd.trim().length < 50 ? (
                    <p className="mt-1 text-xs text-muted-foreground">
                      Need {50 - pastedJd.trim().length} more characters.
                    </p>
                  ) : null}
                </div>
              </div>
            )}
          </div>
        )}

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

        <div>
          <div className="mb-2 flex items-center justify-between">
            <Label htmlFor="questionCount">Question range</Label>
            <span className="text-sm tabular-nums text-muted-foreground transition-opacity duration-150">
              {questionCount} questions
            </span>
          </div>
          <RangeSlider
            id="questionCount"
            min={QUESTION_COUNT_MIN}
            max={QUESTION_COUNT_MAX}
            step={1}
            value={questionCount}
            onValueChange={setQuestionCount}
            aria-valuemin={QUESTION_COUNT_MIN}
            aria-valuemax={QUESTION_COUNT_MAX}
            aria-valuenow={questionCount}
          />
          <div className="mt-1 flex justify-between text-xs text-muted-foreground">
            <span>{QUESTION_COUNT_MIN}</span>
            <span>{QUESTION_COUNT_MAX}</span>
          </div>
        </div>

        {practiceMode === "role" ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Checkbox
                id="personalize"
                checked={personalize}
                disabled={!hasReadyDocument}
                onCheckedChange={(checked) => setPersonalize(checked === true)}
              />
              <Label htmlFor="personalize">Personalize with my résumé</Label>
            </div>
            {!hasReadyDocument ? (
              <p className="pl-6 text-sm text-muted-foreground">
                Upload a CV first to personalize your questions.{" "}
                <Link href="/app/documents" className="underline">
                  Go to Documents
                </Link>
              </p>
            ) : personalize && selectedDocument ? (
              <ResumeReference
                documents={readyDocuments}
                selectedId={selectedDocument.documentId}
                onSelect={setDocumentId}
              />
            ) : null}
          </div>
        ) : (
          <div className="space-y-2">
            {!hasReadyDocument ? (
              <>
                <Label>Résumé reference</Label>
                <p className="text-sm text-muted-foreground">
                  No processed CV yet — questions will not use résumé context.{" "}
                  <Link href="/app/documents" className="underline">
                    Go to Documents
                  </Link>
                </p>
              </>
            ) : selectedDocument ? (
              <ResumeReference
                documents={readyDocuments}
                selectedId={selectedDocument.documentId}
                onSelect={setDocumentId}
              />
            ) : null}
          </div>
        )}

        <Button
          onClick={handleStart}
          disabled={isStarting || !canStart}
          className="w-full"
          size="lg"
        >
          {isStarting ? "Starting..." : "Start practice"}
        </Button>
      </div>
    </div>
  );
}
