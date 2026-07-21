import { ApiError } from "@/src/lib/api-envelope";

export type FormattedApiError = {
  message: string;
  code?: string;
  meta?: Record<string, unknown> | null;
};

export function formatApiError(error: unknown): FormattedApiError {
  if (error instanceof ApiError) {
    return {
      message: error.message,
      code: error.code,
      meta: error.meta ?? null,
    };
  }

  if (error instanceof Error) {
    return { message: error.message };
  }

  return { message: "Request failed" };
}

export function formatApiErrorMessage(error: unknown): string {
  return formatApiError(error).message;
}
