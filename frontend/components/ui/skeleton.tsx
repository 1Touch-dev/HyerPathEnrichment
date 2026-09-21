import { cn } from "@/src/lib/utils";

function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-md bg-gradient-to-r from-muted via-surface-muted to-muted",
        className,
      )}
      {...props}
    />
  );
}

export { Skeleton };
