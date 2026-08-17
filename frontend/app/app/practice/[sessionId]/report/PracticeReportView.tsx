"use client";

import Link from "next/link";
import { EmptyState } from "@/components/console/EmptyState";
import {
  AudioCoachingPanel,
  FeedbackPanel,
  useAudioStatus,
  usePracticeSession,
} from "@/features/practice";
import { PracticeAttempt } from "@/src/lib/types";
import { formatApiErrorMessage } from "@/src/lib/format-api-error";

interface PracticeReportViewProps {
  sessionId: string;
}

function AttemptReportRow({ attempt, index }: { attempt: PracticeAttempt; index: number }) {
  // `PracticeAttempt` itself doesn't carry `analysisData`/`voiceToneSignals` — those
  // live on the audio recording resource, so audio-based attempts fetch it separately.
  const { data: audioStatus } = useAudioStatus(
    attempt.responseType === "audio" ? (attempt.audioRecordingId ?? undefined) : undefined,
  );

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Question {index + 1}
        </p>
        <p className="mt-1 text-base font-medium">
          {attempt.questionText ?? "Question text unavailable"}
        </p>
      </div>

      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Your answer
        </p>
        {attempt.responseType === "text" ? (
          <p className="mt-1 whitespace-pre-wrap text-sm">
            {attempt.textResponse || "No answer provided"}
          </p>
        ) : (
          <p className="mt-1 text-sm text-muted-foreground">
            {audioStatus?.transcription
              ? audioStatus.transcription
              : "Audio response (transcription pending)"}
          </p>
        )}
      </div>

      <FeedbackPanel attempt={attempt} />
      {audioStatus && <AudioCoachingPanel status={audioStatus} />}
    </div>
  );
}

export function PracticeReportView({ sessionId }: PracticeReportViewProps) {
  const { data: session, isLoading, error } = usePracticeSession(sessionId);

  if (isLoading) return <div className="animate-pulse h-96 rounded-lg bg-muted" />;

  if (error || !session) {
    return (
      <EmptyState
        title="Report not found"
        description={error ? formatApiErrorMessage(error) : `No session with id ${sessionId}`}
      />
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Feedback report</h1>
        <p className="text-sm text-muted-foreground">
          Overall score: {session.overallScore === null ? "Pending..." : session.overallScore}
        </p>
      </div>

      {session.attempts.length === 0 ? (
        <EmptyState
          title="No attempts yet"
          description="Answer some questions to see feedback here."
        />
      ) : (
        <div className="space-y-4">
          {session.attempts.map((attempt, index) => (
            <AttemptReportRow key={attempt.id} attempt={attempt} index={index} />
          ))}
        </div>
      )}

      <Link href="/app/practice" className="text-sm font-medium underline">
        Practice again
      </Link>
    </div>
  );
}
