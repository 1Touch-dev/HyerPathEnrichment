# 0022. Login MFA when TOTP is enrolled

- **Status:** Accepted
- **Date:** 2026-10-20

## Context

Settings showed "2FA is enabled" while password sign-in issued a full session
with no authenticator code. ADR 0021 requires a fresh TOTP code for privileged
operations such as impersonation and staff invites. It does not define login.
The settings copy promised account protection, so an enrolled secret that never
runs at sign-in leaves password and Google login as a complete bypass.

## Decision

We chose **a second sign-in step that withholds session cookies until the
current TOTP code matches** over **leaving login as password-only and renaming
the setting**. Enrollment stays optional. When `mfa_enabled` is true, password
login and Google callback set a short-lived HttpOnly `mfa_login` cookie and
return `mfa_required`. `POST /auth/login/mfa` checks that cookie plus the code,
then issues the normal access and refresh cookies. The challenge token is not
an access token.

ADR 0021 step-up still applies after login. A successful sign-in code does not
replace the code required for impersonation or staff invites.

## Tradeoffs

- An extra sign-in step for enrolled accounts, traded for the setting meaning
  what it says.
- A five-minute challenge cookie can be replayed until it expires or sign-in
  succeeds, traded for not storing another server-side login nonce.
- Google sign-in returns to the login page for the code instead of finishing
  in the callback, traded for keeping the TOTP value out of the redirect URL.

## Consequences

- `app/auth/router.py` owns the challenge and `POST /auth/login/mfa`.
- `get_current_user_from_cookie` rejects any token that carries a `purpose`
  claim, so the challenge cannot be used as a session.
- The login page and Google callback BFF show the code step. Users who never
  enroll are unchanged.
