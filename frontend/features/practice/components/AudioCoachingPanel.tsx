import { AudioRecordingStatus } from "@/src/lib/types";

interface AudioCoachingPanelProps {
  status: AudioRecordingStatus;
}

/**
 * `voiceToneSignals` renders only when non-null, and only as plain descriptive text —
 * never a numeric score/badge/progress-bar — per phase2_module3.md §3 Decision 4
 * (a firm product requirement, not a suggestion).
 */
export function AudioCoachingPanel({ status }: AudioCoachingPanelProps) {
  const analysis = status.analysisData;
  const toneEntries = status.voiceToneSignals ? Object.entries(status.voiceToneSignals) : null;

  return (
    <div className="rounded-lg border p-4 space-y-3">
      <h3 className="text-sm font-semibold">Audio coaching</h3>

      {analysis && (
        <div className="grid grid-cols-3 gap-3 text-sm">
          {analysis.fillerWordCount !== undefined && (
            <div>
              <p className="text-muted-foreground">Filler words</p>
              <p className="font-medium">{analysis.fillerWordCount}</p>
            </div>
          )}
          {analysis.wordsPerMinute !== undefined && (
            <div>
              <p className="text-muted-foreground">Words per minute</p>
              <p className="font-medium">{analysis.wordsPerMinute}</p>
            </div>
          )}
          {analysis.clarityScore !== undefined && (
            <div>
              <p className="text-muted-foreground">Clarity</p>
              <p className="font-medium">{analysis.clarityScore}</p>
            </div>
          )}
        </div>
      )}

      {toneEntries && toneEntries.length > 0 && (
        <div className="space-y-1 text-sm">
          {toneEntries.map(([key, value]) => (
            <p key={key} className="text-muted-foreground">
              {key.replace(/_/g, " ")}: {String(value)}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
