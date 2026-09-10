const dateTimeFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

function parseDateLike(value: string | number | Date | null | undefined): Date | null {
  if (value === null || value === undefined || value === "") return null;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatConsoleTimestamp(value: string | number | Date | null | undefined): string {
  const date = parseDateLike(value);
  return date ? dateTimeFormatter.format(date) : "—";
}

export function formatRelativeTime(value: string | number | Date | null | undefined): string {
  const date = parseDateLike(value);
  if (!date) return "Unknown";

  const diffMs = date.getTime() - Date.now();
  const absDiffMs = Math.abs(diffMs);
  const direction = diffMs < 0 ? "ago" : "from now";

  if (absDiffMs < 15_000) {
    return diffMs < 0 ? "Just now" : "In a few seconds";
  }

  const minutes = Math.round(absDiffMs / 60_000);
  if (minutes < 60) {
    return `${minutes}m ${direction}`;
  }

  const hours = Math.round(absDiffMs / 3_600_000);
  if (hours < 24) {
    return `${hours}h ${direction}`;
  }

  const days = Math.round(absDiffMs / 86_400_000);
  return `${days}d ${direction}`;
}

export function formatFileSize(bytes: number | null | undefined): string {
  if (typeof bytes !== "number" || !Number.isFinite(bytes) || bytes < 0) return "—";
  if (bytes < 1024) return `${bytes} B`;

  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unitIndex = 0;

  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }

  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[unitIndex]}`;
}
