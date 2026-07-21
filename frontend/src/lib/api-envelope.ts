/** Shared success/error response envelopes matching backend/app/core/responses.py */

export type SuccessEnvelope<T> = {
  success: true;
  data: T;
  message?: string | null;
  meta?: Record<string, unknown> | null;
};

export type ErrorBody = {
  code: string;
  message: string;
  details?: unknown;
  status_code: number;
};

export type ErrorEnvelope = {
  success: false;
  error: ErrorBody;
  meta?: Record<string, unknown> | null;
};

export class ApiError extends Error {
  readonly code: string;
  readonly statusCode: number;
  readonly details?: unknown;
  readonly meta?: Record<string, unknown> | null;

  constructor(
    message: string,
    {
      code,
      statusCode,
      details,
      meta,
    }: {
      code: string;
      statusCode: number;
      details?: unknown;
      meta?: Record<string, unknown> | null;
    },
  ) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.statusCode = statusCode;
    this.details = details;
    this.meta = meta;
  }
}

export function isSuccessEnvelope(value: unknown): value is SuccessEnvelope<unknown> {
  return (
    !!value &&
    typeof value === "object" &&
    "success" in value &&
    (value as { success: unknown }).success === true &&
    "data" in value
  );
}

export function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  return (
    !!value &&
    typeof value === "object" &&
    "success" in value &&
    (value as { success: unknown }).success === false &&
    "error" in value &&
    typeof (value as { error: unknown }).error === "object" &&
    (value as { error: { message?: unknown } }).error !== null &&
    typeof (value as { error: { message?: unknown } }).error.message === "string"
  );
}

export function successEnvelope<T>(
  data: T,
  message: string | null = null,
  meta: Record<string, unknown> | null = null,
): SuccessEnvelope<T> {
  return { success: true, data, message, meta };
}

export function errorEnvelope(
  code: string,
  message: string,
  statusCode: number,
  details: unknown = null,
  meta: Record<string, unknown> | null = null,
): ErrorEnvelope {
  return {
    success: false,
    error: {
      code,
      message,
      details,
      status_code: statusCode,
    },
    meta,
  };
}

/** Extract `data` from an enveloped payload (legacy bare payloads still accepted). */
export function unwrapEnvelopeData<T>(payload: unknown): T {
  if (isSuccessEnvelope(payload)) {
    return payload.data as T;
  }
  return payload as T;
}

function httpStatusToCode(statusCode: number): string {
  const mapping: Record<number, string> = {
    400: "VALIDATION_ERROR",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMIT_EXCEEDED",
    502: "SERVICE_UNAVAILABLE",
    503: "SERVICE_UNAVAILABLE",
  };
  if (mapping[statusCode]) {
    return mapping[statusCode];
  }
  return statusCode >= 500 ? "INTERNAL_ERROR" : "VALIDATION_ERROR";
}

function detailMessage(detail: unknown): string {
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (item && typeof item === "object" && "msg" in item && typeof item.msg === "string") {
          return item.msg;
        }
        return String(item);
      })
      .filter(Boolean);
    return parts.length ? parts.join(", ") : "request failed";
  }
  return detail != null ? String(detail) : "request failed";
}

/** Build ApiError from an error envelope or legacy FastAPI / BFF shapes. */
export function parseEnvelopeError(body: unknown, httpStatus: number): ApiError {
  if (isErrorEnvelope(body)) {
    return new ApiError(body.error.message, {
      code: body.error.code,
      statusCode: body.error.status_code ?? httpStatus,
      details: body.error.details,
      meta: body.meta ?? null,
    });
  }

  if (body && typeof body === "object") {
    const parsed = body as {
      detail?: unknown;
      message?: string;
      error?: { code?: string; message?: string; details?: unknown; status_code?: number };
      meta?: Record<string, unknown> | null;
    };

    if (parsed.error && typeof parsed.error.message === "string") {
      return new ApiError(parsed.error.message, {
        code: parsed.error.code ?? httpStatusToCode(httpStatus),
        statusCode: parsed.error.status_code ?? httpStatus,
        details: parsed.error.details,
        meta: parsed.meta ?? null,
      });
    }

    if (typeof parsed.message === "string") {
      return new ApiError(parsed.message, {
        code: httpStatusToCode(httpStatus),
        statusCode: httpStatus,
        details: null,
        meta: parsed.meta ?? null,
      });
    }

    if (parsed.detail !== undefined) {
      return new ApiError(detailMessage(parsed.detail), {
        code: httpStatusToCode(httpStatus),
        statusCode: httpStatus,
        details: parsed.detail,
        meta: parsed.meta ?? null,
      });
    }
  }

  if (typeof body === "string" && body.trim()) {
    return new ApiError(body, {
      code: httpStatusToCode(httpStatus),
      statusCode: httpStatus,
    });
  }

  return new ApiError("Request failed", {
    code: httpStatusToCode(httpStatus),
    statusCode: httpStatus,
  });
}

export async function parseResponseEnvelopeError(response: Response): Promise<ApiError> {
  const text = await response.text();
  if (!text) {
    return parseEnvelopeError(null, response.status);
  }
  try {
    return parseEnvelopeError(JSON.parse(text), response.status);
  } catch {
    return parseEnvelopeError(text, response.status);
  }
}
