# CTR-DESIGN-STATES — Desk shell design states

Approved contract for shared Desk (and related staff-door) UI states. Keep implementations thin: reuse existing primitives; do not invent a parallel design system.

## Primitives (use these)

| Need | Primitive | Notes |
|------|-----------|--------|
| Auth / route gate status | `RouteGuardStatus` (`frontend/components/auth/route-guard-status.tsx`) | Full-viewport spinner + polite status text; may redirect. |
| Empty / error content | `EmptyState` (`frontend/components/console/EmptyState.tsx`) | Prefer wrapping error in `role="alert"` (see Feature Flags). |
| Frozen / disabled admin surface | Feature Flags panel pattern | Read-only switches; disabled Create; Alert explaining no consumer. |

## State matrix

| State | Desk expectation | Current approved pattern |
|-------|------------------|--------------------------|
| **Loading** | Announce progress; do not show success empty copy. | Short `role="status"` text (e.g. “Loading roles…”) or `RouteGuardStatus` (“Loading account”) while auth resolves. |
| **Empty** | Honest empty only after a successful load. | `EmptyState` with product-accurate copy (e.g. “No roles configured”). Never use empty copy for failed fetches. |
| **Error** | Distinct from empty; explain load/access failure. | `EmptyState` (or destructive text) under `role="alert"`; include permission/network failure language when relevant (roles page). Feature Flags: “records unavailable”. |
| **Permission-denied** | User must understand access is denied; redirect still allowed. | `RouteGuardStatus` with **“You don't have access to this page”** while `AdminGuard` / `StaffGuard` / Desk home redirect to an authorized home (or login). Do not show children. |
| **Disabled** | Controls that cannot act stay visible but inert. | Native `disabled` + explanatory Alert/description (Feature Flags Create + switches). |
| **Destructive** | Confirm before privileged mutate. | Prefer existing `Dialog` when already in the flow (e.g. brand deactivate). Otherwise `window.confirm` matching Users/MFA/moderation (roles permission detach; queue job retry). |
| **Focus** | Keyboard users see focus on interactive chrome. | `focus-visible` rings on Desk nav (`AppNavRail` / `AppSidebar` / `AppBottomNav`) and destructive controls; icon-only links need accessible names. |
| **Responsive** | Same states on mobile/desktop; shell chrome adapts. | Shared AppShell breakpoints; status/empty/error blocks remain readable without relying on hover-only affordances. |

## Must / must-not

- **Must** distinguish error from empty for list fetches (403/401/network → error/alert, not “No … configured”).
- **Must** announce denied/loading via `RouteGuardStatus` (or equivalent status) before/while redirecting.
- **Must not** treat Feature Flags as a mutable product surface until a consumer exists (frozen pattern stays).
- **Must not** hide Brands from recruiters with `brands:read` (nav/list remain; mutate gates are separate).
