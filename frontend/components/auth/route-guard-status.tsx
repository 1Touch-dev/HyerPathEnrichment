import { Loader2 } from "lucide-react";

export function RouteGuardStatus({ message }: { message: string }) {
  return (
    <div
      role="status"
      aria-label={message}
      aria-live="polite"
      className="flex h-screen items-center justify-center"
    >
      <div className="text-center">
        <Loader2 className="mx-auto mb-4 h-8 w-8 animate-spin text-primary" aria-hidden="true" />
        <p className="text-sm text-muted-foreground">{message}</p>
      </div>
    </div>
  );
}
