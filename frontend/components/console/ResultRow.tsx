'use client';

import { cn } from '@/src/lib/utils';
import { formatPercent } from '@/src/lib/utils';

type ResultRowProps = {
  title: string;
  subtitle?: string;
  confidence?: number;
  selected?: boolean;
  onClick?: () => void;
};

export function ResultRow({ title, subtitle, confidence, selected, onClick }: ResultRowProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'w-full rounded-lg border px-4 py-3 text-left transition-colors hover:bg-muted',
        selected ? 'border-primary bg-secondary/60' : 'border-border',
      )}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium">{title}</div>
          {subtitle ? <div className="mt-1 truncate font-mono text-xs text-muted-foreground">{subtitle}</div> : null}
        </div>
        {confidence !== undefined ? (
          <div className={cn('shrink-0 text-xs font-medium', selected ? 'text-primary' : 'text-muted-foreground')}>
            {formatPercent(confidence)}
          </div>
        ) : null}
      </div>
    </button>
  );
}

