/**
 * `/app` is the Candidate product root (see PRODUCT_ROOTS). Do not call
 * `redirect()` from next/navigation here: this segment's layout is a Client
 * Component, and a render-time redirect races Next.js App Router's
 * `useActionQueue` (`use(thenable)` vs plain state) and throws
 * "Rendered more hooks than during the previous render".
 *
 * HTTP alias lives in `next.config.js` (`/app` → `/app/matches`). This page
 * is the render fallback for any request that still lands on `/app`.
 */
export { default } from "./matches/page";
