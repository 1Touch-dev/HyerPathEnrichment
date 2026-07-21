import "server-only";

const DEFAULT_TIMEOUT_MS = 30_000;

export function getBackendConfig(): { baseUrl: string; token: string } {
  return {
    baseUrl: process.env.BACKEND_API_URL ?? "http://localhost:8000",
    token: process.env.BACKEND_API_TOKEN ?? "change-me",
  };
}

export async function backendFetch(path: string, init?: RequestInit): Promise<Response> {
  const { baseUrl, token } = getBackendConfig();
  const timeoutMs = Number(process.env.BACKEND_FETCH_TIMEOUT_MS ?? DEFAULT_TIMEOUT_MS);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    return await fetch(`${baseUrl}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        ...(init?.headers ?? {}),
        Authorization: `Bearer ${token}`,
      },
    });
  } finally {
    clearTimeout(timeout);
  }
}
