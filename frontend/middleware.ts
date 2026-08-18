import { NextResponse, type NextRequest } from "next/server";
import { resolveSubdomainRewrite } from "@/src/lib/subdomain";

/**
 * Code-only portfolio subdomain routing (no real DNS/wildcard TLS provisioned yet).
 * A no-op by default: `PORTFOLIO_SUBDOMAINS_ENABLED` is unset/false until ops
 * provisions the wildcard cert and someone flips it on.
 */
export default function middleware(request: NextRequest) {
  const host = request.headers.get("host") ?? "";
  const enabled = process.env.PORTFOLIO_SUBDOMAINS_ENABLED === "true";
  const rootDomain = process.env.PORTFOLIO_SUBDOMAIN_ROOT ?? "";

  const rewritePath = resolveSubdomainRewrite(host, enabled, rootDomain);

  if (rewritePath) {
    return NextResponse.rewrite(new URL(rewritePath, request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next/|api/|.*\\.(?:ico|png|jpg|jpeg|svg|gif|webp|css|js|map|txt|xml|woff|woff2)$).*)",
  ],
};
