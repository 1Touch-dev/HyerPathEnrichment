export function createIdempotencyKey(scope: string): string {
  const uuid =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${scope}:${uuid}`;
}

export function withIdempotencyHeaders(
  scope: string,
  headers: Record<string, string> = {},
): Record<string, string> {
  return {
    ...headers,
    "Idempotency-Key": createIdempotencyKey(scope),
  };
}

export function forwardIdempotencyHeader(
  request: Request | { headers: Headers },
  headers: Record<string, string> = {},
): Record<string, string> {
  const key = request.headers.get("Idempotency-Key")?.trim();
  if (!key) {
    return headers;
  }
  return {
    ...headers,
    "Idempotency-Key": key,
  };
}
