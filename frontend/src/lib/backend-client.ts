import "server-only";
import { cookies } from "next/headers";

const DEFAULT_TIMEOUT_MS = 30_000;

export function getBackendConfig(): { baseUrl: string } {
  return {
    baseUrl: process.env.BACKEND_API_URL ?? "http://localhost:8000",
  };
}

/**
 * Server-side fetch to backend with cookie-based authentication.
 * Automatically forwards auth_token cookie from the request.
 * Use this for authenticated API routes that need to proxy to the backend.
 */
export async function backendFetch(
  path: string,
  init?: RequestInit,
  timeoutOverrideMs?: number,
): Promise<Response> {
  const { baseUrl } = getBackendConfig();
  const timeoutMs =
    timeoutOverrideMs ?? Number(process.env.BACKEND_FETCH_TIMEOUT_MS ?? DEFAULT_TIMEOUT_MS);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    // Get auth token from cookies
    const cookieStore = await cookies();
    const authToken = cookieStore.get("access_token");

    const headers: Record<string, string> = {
      ...((init?.headers as Record<string, string>) ?? {}),
    };

    // Forward cookie to backend if available
    if (authToken) {
      headers.Cookie = `access_token=${authToken.value}`;
    }

    return await fetch(`${baseUrl}${path}`, {
      ...init,
      cache: "no-store",
      signal: controller.signal,
      headers,
    });
  } finally {
    clearTimeout(timeout);
  }
}

/**
 * Server-side fetch to backend without authentication.
 * Use this for public endpoints (health, opt-out).
 */
export async function backendFetchPublic(
  path: string,
  init?: RequestInit,
  timeoutOverrideMs?: number,
): Promise<Response> {
  const { baseUrl } = getBackendConfig();
  const timeoutMs =
    timeoutOverrideMs ?? Number(process.env.BACKEND_FETCH_TIMEOUT_MS ?? DEFAULT_TIMEOUT_MS);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await fetch(`${baseUrl}${path}`, {
      ...init,
      cache: "no-store",
      signal: controller.signal,
      headers: {
        ...(init?.headers ?? {}),
      },
    });
  } finally {
    clearTimeout(timeout);
  }
}
