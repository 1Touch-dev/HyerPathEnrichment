"use client";

import Link from "next/link";
import { EmptyState } from "@/components/console/EmptyState";
import {
  ShellPageHeader,
  ShellPageHeaderActions,
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
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
    <div className="app-surface-muted space-y-3 rounded-[1.25rem] p-5">
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
      <ShellPageHeader>
        <ShellPageHeaderContent>
          <ShellPageHeaderEyebrow>Candidate workspace</ShellPageHeaderEyebrow>
          <ShellPageHeaderTitle>Feedback report</ShellPageHeaderTitle>
          <ShellPageHeaderDescription>
            Review your answers, the scoring feedback tied to each one, and any audio coaching that
            finished processing.
          </ShellPageHeaderDescription>
        </ShellPageHeaderContent>
        <ShellPageHeaderActions className="items-start sm:items-center">
          <Badge variant={session.overallScore === null ? "outline" : "success"}>
            Overall score: {session.overallScore === null ? "Pending..." : session.overallScore}
          </Badge>
          <Link href="/app/practice" className="text-sm font-medium underline">
            Practice again
          </Link>
        </ShellPageHeaderActions>
      </ShellPageHeader>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <p className="text-sm text-muted-foreground">Attempts</p>
            <CardTitle className="text-3xl text-primary">{session.attempts.length}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Submitted answers in this session.
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <p className="text-sm text-muted-foreground">Audio answers</p>
            <CardTitle className="text-3xl text-primary">
              {session.attempts.filter((attempt) => attempt.responseType === "audio").length}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Responses that can include delivery coaching.
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <p className="text-sm text-muted-foreground">Text answers</p>
            <CardTitle className="text-3xl text-primary">
              {session.attempts.filter((attempt) => attempt.responseType === "text").length}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Responses focused on content and structure.
          </CardContent>
        </Card>
      </div>

      {session.attempts.length === 0 ? (
        <EmptyState
          title="No attempts yet"
          description="Answer some questions to see feedback here."
        />
      ) : (
        <ShellSection>
          <ShellSectionHeader>
            <ShellSectionHeaderContent>
              <ShellSectionHeaderTitle>Question-by-question review</ShellSectionHeaderTitle>
              <ShellSectionHeaderDescription>
                Keep this open while you revise answers or record another practice run.
              </ShellSectionHeaderDescription>
            </ShellSectionHeaderContent>
          </ShellSectionHeader>
          <div className="space-y-4">
            {session.attempts.map((attempt, index) => (
              <AttemptReportRow key={attempt.id} attempt={attempt} index={index} />
            ))}
          </div>
        </ShellSection>
      )}
    </div>
  );
}
