"use client";

import Link from "next/link";
import { useState } from "react";
import { AlertCircle } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/console/EmptyState";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  AudioRecorder,
  FeedbackPanel,
  QuestionCard,
  loadStoredQuestions,
  useAddAttempt,
  useAudioUpload,
  usePracticeSession,
  useQuestions,
} from "@/features/practice";
import { formatApiErrorMessage } from "@/src/lib/format-api-error";

interface PracticeSessionViewProps {
  sessionId: string;
}

export function PracticeSessionView({ sessionId }: PracticeSessionViewProps) {
  const { data: session, isLoading, error: sessionError } = usePracticeSession(sessionId);
  const [questions, setQuestions] = useState(() => loadStoredQuestions(sessionId));
  const [responseType, setResponseType] = useState<"text" | "audio">("text");
  const [textValue, setTextValue] = useState("");

  const questionsMutation = useQuestions();
  const audioUploadMutation = useAudioUpload();
  const addAttemptMutation = useAddAttempt();

  if (isLoading) return <div className="animate-pulse h-96 rounded-lg bg-muted" />;

  if (sessionError || !session) {
    return (
      <EmptyState
        title="Session not found"
        description={
          sessionError ? formatApiErrorMessage(sessionError) : `No session with id ${sessionId}`
        }
      />
    );
  }

  const answeredQuestionIds = new Set(
    session.attempts.map((attempt) => attempt.questionId).filter((id): id is string => Boolean(id)),
  );
  const currentQuestion = questions.find((question) => !answeredQuestionIds.has(question.id));
  const currentAttempt = currentQuestion
    ? session.attempts.find((attempt) => attempt.questionId === currentQuestion.id)
    : undefined;

  const mutationError =
    questionsMutation.error ?? audioUploadMutation.error ?? addAttemptMutation.error;

  async function handleGenerateQuestions() {
    const result = await questionsMutation.mutateAsync({ jobRole: "software_engineer" });
    setQuestions(result.questions);
  }

  async function handleTextSubmit() {
    if (!currentQuestion || !textValue.trim()) return;
    await addAttemptMutation.mutateAsync({
      sessionId,
      questionId: currentQuestion.id,
      responseType: "text",
      textResponse: textValue.trim(),
    });
    setTextValue("");
  }

  async function handleAudioComplete(blob: Blob) {
    if (!currentQuestion) return;
    const upload = await audioUploadMutation.mutateAsync({
      practiceSessionId: sessionId,
      audioFormat: blob.type || "audio/webm",
      file: blob,
      filename: "recording.webm",
    });
    await addAttemptMutation.mutateAsync({
      sessionId,
      questionId: currentQuestion.id,
      responseType: "audio",
      audioRecordingId: upload.id,
    });
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Practice session</h1>
          <p className="text-sm text-muted-foreground">
            {session.attempts.length} of {questions.length || session.attempts.length} answered
          </p>
        </div>
        <Button variant="outline" asChild>
          <Link href={`/app/practice/${sessionId}/report`}>View report</Link>
        </Button>
      </div>

      {mutationError ? (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{formatApiErrorMessage(mutationError)}</AlertDescription>
        </Alert>
      ) : null}

      {!currentQuestion ? (
        questions.length === 0 ? (
          <EmptyState
            title="No attempts yet"
            description="Generate a fresh set of questions to keep practicing."
            action={
              <Button onClick={handleGenerateQuestions} disabled={questionsMutation.isPending}>
                {questionsMutation.isPending ? "Generating..." : "Generate questions"}
              </Button>
            }
          />
        ) : (
          <EmptyState
            title="All questions answered"
            description="Nice work! View your feedback report or start a new session."
            action={
              <Button asChild>
                <Link href={`/app/practice/${sessionId}/report`}>View report</Link>
              </Button>
            }
          />
        )
      ) : (
        <>
          <QuestionCard question={currentQuestion} />

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

          {currentAttempt && <FeedbackPanel attempt={currentAttempt} />}
        </>
      )}
    </div>
  );
}
