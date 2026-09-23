import { PracticeAttempt } from "@/src/lib/types";

interface FeedbackPanelProps {
  attempt: PracticeAttempt;
}

/**
 * `scoreBreakdown` is `Record<string, unknown> | null` on the backend (an untyped JSONB
 * column) — rendered generically here since no fixed schema is guaranteed.
 */
export function FeedbackPanel({ attempt }: FeedbackPanelProps) {
  const breakdownEntries = attempt.scoreBreakdown ? Object.entries(attempt.scoreBreakdown) : [];

  return (
    <div className="space-y-3 border-t border-border/60 pt-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Score</h3>
        {attempt.aiScore === null ? (
          <span className="text-sm text-muted-foreground">Pending...</span>
        ) : (
          <span className="text-lg font-semibold text-primary">{attempt.aiScore}</span>
        )}
      </div>

      {breakdownEntries.length > 0 && (
        <div className="space-y-1 rounded-xl border border-border/70 bg-surface p-3">
          {breakdownEntries.map(([key, value]) => (
            <div key={key} className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">{key}</span>
              <span>{String(value)}</span>
            </div>
          ))}
        </div>
      )}

      {attempt.aiFeedback && <p className="text-sm text-muted-foreground">{attempt.aiFeedback}</p>}
    </div>
  );
}
