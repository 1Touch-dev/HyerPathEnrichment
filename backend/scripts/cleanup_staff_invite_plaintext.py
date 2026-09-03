#!/usr/bin/env python3
"""Clear transitional plaintext staff-invite tokens after API maintenance.

Required deployment order:
1. Stop every old API instance, pausing invite create/lookup/redemption.
2. Verify no old API process serves traffic.
3. Apply revisions 065–066.
4. Start only digest-first/new-redemption code.
5. Pass health and invite-security smoke checks.
6. Run this command with both required acknowledgement flags. Default cleanup
   removes accepted/expired/revoked plaintext; add ``--include-active`` only
   with ``--schema-recovery-window-closed`` after recovery closes.

This command is not evidence that the drain or smoke happened. The flags bind
the operator's recorded INT-RELEASE handoff to the destructive cleanup step.
No flag permits deploying a pre-hardening API binary.
"""

from __future__ import annotations

import argparse
import asyncio

from app.database.session import SessionLocal, init_db
from app.modules.staff_invites.repository import clear_legacy_plaintext_tokens


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--include-active",
        action="store_true",
        help="clear active restored-schema recovery plaintext",
    )
    parser.add_argument(
        "--api-drain-acknowledged",
        action="store_true",
        help="confirm every old API instance stopped before revisions 065-066",
    )
    parser.add_argument(
        "--new-code-smoke-passed",
        action="store_true",
        help="confirm only new code started and health/security smoke passed",
    )
    parser.add_argument(
        "--schema-recovery-window-closed",
        action="store_true",
        help="required with --include-active after hardened recovery closes",
    )
    args = parser.parse_args()
    missing = []
    if not args.api_drain_acknowledged:
        missing.append("--api-drain-acknowledged")
    if not args.new_code_smoke_passed:
        missing.append("--new-code-smoke-passed")
    if args.include_active and not args.schema_recovery_window_closed:
        missing.append("--schema-recovery-window-closed")
    if missing:
        parser.error(f"cleanup requires {' and '.join(missing)}")
    return args


async def _run(*, include_active: bool) -> int:
    await init_db()
    async with SessionLocal() as session:
        return await clear_legacy_plaintext_tokens(
            session,
            include_active=include_active,
        )


def main() -> None:
    args = _parse_args()
    cleared = asyncio.run(_run(include_active=args.include_active))
    print(f"cleared {cleared} plaintext staff-invite token(s)")


if __name__ == "__main__":
    main()
