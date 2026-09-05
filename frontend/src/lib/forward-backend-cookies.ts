import type { NextResponse } from "next/server";

/**
 * Forward all Set-Cookie headers from a backend Response onto a NextResponse.
 * Uses getSetCookie() when available so multi-cookie login/refresh responses
 * are not collapsed by Headers.get("set-cookie").
 */
export function forwardBackendSetCookies(
  backendResponse: Response,
  nextResponse: NextResponse,
): void {
  const headers = backendResponse.headers as Headers & {
    getSetCookie?: () => string[];
  };
  const cookies =
    typeof headers.getSetCookie === "function"
      ? headers.getSetCookie()
      : (() => {
          const single = backendResponse.headers.get("set-cookie");
          return single ? [single] : [];
        })();

  for (const cookie of cookies) {
    nextResponse.headers.append("set-cookie", cookie);
  }
}
