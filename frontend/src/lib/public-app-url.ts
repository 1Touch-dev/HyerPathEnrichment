/**
 * Resolve the browser-facing application origin for server-side redirects.
 *
 * Behind Caddy, Next is bound to 127.0.0.1:3000 (HOSTNAME=127.0.0.1), so
 * `request.nextUrl.origin` becomes https://localhost:3000. OAuth and other
 * redirects must use an explicitly configured public origin instead.
 */
export function getPublicAppOrigin(request?: { nextUrl: { origin: string } }): string {
  const configured = process.env.APP_PUBLIC_URL?.trim() || process.env.NEXT_PUBLIC_APP_URL?.trim();

  if (configured) {
    let parsed: URL;
    try {
      parsed = new URL(configured);
    } catch {
      throw new Error("APP_PUBLIC_URL is not a valid absolute URL");
    }
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      throw new Error("APP_PUBLIC_URL must use http or https");
    }
    if (!parsed.hostname || parsed.hostname === "localhost" || parsed.hostname === "127.0.0.1") {
      if (process.env.NODE_ENV === "production") {
        throw new Error("APP_PUBLIC_URL must not point at localhost in production");
      }
    }
    return parsed.origin;
  }

  if (process.env.NODE_ENV !== "production") {
    return request?.nextUrl.origin ?? "http://localhost:3000";
  }

  throw new Error("APP_PUBLIC_URL must be set in production");
}

export function publicAppUrl(path: string, request?: { nextUrl: { origin: string } }): URL {
  const origin = getPublicAppOrigin(request);
  return new URL(path, origin);
}
