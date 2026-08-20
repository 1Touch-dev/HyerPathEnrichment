"use client";

import { useEffect, useRef, useState } from "react";
import { AlertCircle, Loader2 } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/console/EmptyState";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { AudioRecorder, useAddAttempt, useAudioUpload } from "@/features/practice";
import { ApiError } from "@/src/lib/api-envelope";
import { useJdPracticeQuestions } from "../hooks/useJdPracticeQuestions";

const RATE_LIMIT_MESSAGE = "You've hit today's practice question limit, try again tomorrow";
const GENERIC_ERROR_MESSAGE = "Couldn't generate questions, please try again";

interface JdPracticeSessionViewProps {
  jobMatchId: string;
}

/**
 * The JD-tailored practice flow (phase2_module4 §9.6): calls `useJdPracticeQuestions` on
 * mount (a real, multi-second LLM call, §9.8/§15.5 — not instant, must show a spinner not
 * a blank screen), then walks the candidate through one question at a time. The sample
 * answer for a question is only revealed after that question's attempt is submitted
 * (§9.4's non-spoiler UX note) — this is UI-layer discipline, not a schema-layer omission,
 * since the API response already includes `sampleAnswer` for every question up front.
 *
 * Reuses Module 3's existing practice UI building blocks (frontend/features/practice)
 * rather than re-building them: `AudioRecorder` for audio answers, `useAudioUpload` +
 * `useAddAttempt` for submitting an attempt against the session created by this request.
 * `questionId` is intentionally omitted (left `undefined`) when submitting an attempt for
 * a JD-tailored question — per §9.4, JD-tailored questions are never persisted to the
 * shared `interview_questions` bank, so there is no real bank row for `QuestionAttempt`'s
 * nullable `question_id` FK to reference. The existing `QuestionAttemptRequest` schema
 * (backend/app/modules/sessions/schemas.py) has no `attempt_metadata` field yet to carry
 * the JD question's text/category/difficulty alongside a null `question_id` — extending
 * that schema is backend scope out of this frontend-only chunk, so for now a submitted
 * JD-practice attempt is recorded without that extra context, tracked as a follow-up.
 */
export function JdPracticeSessionView({ jobMatchId }: JdPracticeSessionViewProps) {
  const questionsMutation = useJdPracticeQuestions();
  const audioUploadMutation = useAudioUpload();
  const addAttemptMutation = useAddAttempt();

  const [currentIndex, setCurrentIndex] = useState(0);
  const [submittedIndices, setSubmittedIndices] = useState<Set<number>>(new Set());
  const [responseType, setResponseType] = useState<"text" | "audio">("text");
  const [textValue, setTextValue] = useState("");

  const hasRequestedRef = useRef(false);
  useEffect(() => {
    if (hasRequestedRef.current) return;
    hasRequestedRef.current = true;
    // Fires exactly once per mount — regenerating on every render would burn the
    // per-user daily generation budget (§9.4) for no reason.
    questionsMutation.mutate({ jobMatchId });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobMatchId]);

  if (questionsMutation.isPending || questionsMutation.isIdle) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 rounded-lg border p-10">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <p className="text-sm text-muted-foreground">Generating your practice questions...</p>
      </div>
    );
  }

  if (questionsMutation.isError) {
    const error = questionsMutation.error;
    const isRateLimit = error instanceof ApiError && error.code === "RATE_LIMIT_EXCEEDED";
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          {isRateLimit ? RATE_LIMIT_MESSAGE : GENERIC_ERROR_MESSAGE}
        </AlertDescription>
      </Alert>
    );
  }

  const result = questionsMutation.data;
  const questions = result?.questions ?? [];
  const practiceSessionId = result?.practiceSessionId;
  const currentQuestion = questions[currentIndex];
  const hasSubmittedCurrent = submittedIndices.has(currentIndex);
  const isLastQuestion = currentIndex >= questions.length - 1;
  const submissionError = addAttemptMutation.error ?? audioUploadMutation.error;
  const nextButtonLabel = isLastQuestion ? "Finish" : "Next question";

  if (!currentQuestion) {
    return (
      <EmptyState
        title="Practice complete"
        description="Nice work! You've gone through every tailored question for this job."
      />
    );
  }

  async function handleTextSubmit() {
    if (!textValue.trim() || !practiceSessionId) return;
    await addAttemptMutation.mutateAsync({
      sessionId: practiceSessionId,
      responseType: "text",
      textResponse: textValue.trim(),
    });
    setSubmittedIndices((prev) => new Set(prev).add(currentIndex));
  }

  async function handleAudioComplete(blob: Blob) {
    if (!practiceSessionId) return;
    const upload = await audioUploadMutation.mutateAsync({
      practiceSessionId,
      audioFormat: blob.type || "audio/webm",
      file: blob,
      filename: "recording.webm",
    });
    await addAttemptMutation.mutateAsync({
      sessionId: practiceSessionId,
      responseType: "audio",
      audioRecordingId: upload.id,
    });
    setSubmittedIndices((prev) => new Set(prev).add(currentIndex));
  }

  function handleNext() {
    setTextValue("");
    setCurrentIndex((prev) => prev + 1);
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">JD-tailored practice</h1>
        <p className="text-sm text-muted-foreground">
          Question {currentIndex + 1} of {questions.length}
        </p>
      </div>

      {submissionError ? (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>Couldn&apos;t submit your answer, please try again.</AlertDescription>
        </Alert>
      ) : null}

      <div className="rounded-lg border p-4">
        <p className="text-base font-medium">{currentQuestion.questionText}</p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Badge variant="outline">{currentQuestion.category}</Badge>
          <Badge variant="outline">{currentQuestion.difficulty}</Badge>
        </div>
      </div>

      {!hasSubmittedCurrent ? (
        <>
          <Tabs
            value={responseType}
            onValueChange={(value) => setResponseType(value as "text" | "audio")}
          >
            <TabsList>
              <TabsTrigger value="text">Text</TabsTrigger>
              <TabsTrigger value="audio">Audio</TabsTrigger>
            </TabsList>
          </Tabs>

          {responseType === "text" ? (
            <div className="space-y-2">
              <Textarea
                value={textValue}
                onChange={(e) => setTextValue(e.target.value)}
                placeholder="Type your answer..."
                rows={6}
              />
              <Button
                onClick={handleTextSubmit}
                disabled={addAttemptMutation.isPending || !textValue.trim()}
              >
                {addAttemptMutation.isPending ? "Submitting..." : "Submit answer"}
              </Button>
            </div>
          ) : (
            <AudioRecorder onRecordingComplete={handleAudioComplete} />
          )}
        </>
      ) : (
        <div className="space-y-3 rounded-lg border border-green-200 bg-green-50 p-4">
          <p className="text-sm font-medium text-green-900">Sample answer</p>
          <p className="text-sm text-green-900">{currentQuestion.sampleAnswer}</p>
          <Button size="sm" onClick={handleNext}>
            {nextButtonLabel}
          </Button>
        </div>
      )}
    </div>
  );
}
