export class JobPendingError extends Error {
  constructor() {
    super("JOB_PENDING");
    this.name = "JobPendingError";
  }
}

export function isJobPendingError(error: unknown): boolean {
  return (
    error instanceof JobPendingError || (error instanceof Error && error.message === "JOB_PENDING")
  );
}
