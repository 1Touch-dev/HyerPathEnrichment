/**
 * Portfolio subdomain rewrite logic (frontend/middleware.ts).
 *
 * Pure and framework-agnostic on purpose: it takes primitive inputs so it can be
 * unit-tested without spinning up a real `NextRequest`/Edge runtime. Behavior is a
 * strict no-op unless `enabled` is explicitly `true` — until real DNS + wildcard TLS
 * is provisioned and `PORTFOLIO_SUBDOMAINS_ENABLED` is flipped on, this always returns
 * `null` (no rewrite) for every caller.
 */

const SUBDOMAIN_HOST_PATTERN = "^([a-z0-9-]+)\\.";

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Given a request's `Host` header, decide whether it's a portfolio subdomain that
 * should be rewritten to `/p/{slug}`.
 *
 * - Returns `null` when `enabled` is false, when `host` doesn't match
 *   `^([a-z0-9-]+)\.{rootDomain}$` (case-insensitively), or when `host` is the bare
 *   root domain itself (no subdomain).
 * - Strips a trailing port (e.g. `jane.hyrepath.dev:3000`) before matching.
 */
export function resolveSubdomainRewrite(
  host: string,
  enabled: boolean,
  rootDomain: string,
): string | null {
  if (!enabled || !host || !rootDomain) {
    return null;
  }

  const hostWithoutPort = host.split(":")[0].toLowerCase();
  const pattern = new RegExp(`${SUBDOMAIN_HOST_PATTERN}${escapeRegExp(rootDomain.toLowerCase())}$`);
  const match = hostWithoutPort.match(pattern);

  if (!match) {
    return null;
  }

  const slug = match[1];
  return `/p/${slug}`;
}
