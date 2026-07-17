from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


async def run_command(
    args: list[str],
    timeout: float,
    env: dict[str, str] | None = None,
    cwd: str | None = None,
) -> tuple[int, str, str]:
    """Run an external CLI and capture output without ever raising.

    Shared by every subprocess-backed enricher (gitrecon, theHarvester,
    CrossLinked, email-sleuth, sherlock, maigret). A missing binary or a
    timeout degrades to a non-zero return code and empty output so the caller
    can emit an empty fragment instead of crashing the pipeline.

    Returns ``(returncode, stdout, stderr)``.
    """
    try:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=cwd,
        )
    except (FileNotFoundError, OSError):
        logger.warning("command not available: %s", args[0] if args else "<empty>")
        return 127, "", ""

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        process.kill()
        stdout, stderr = await process.communicate()
        logger.warning("command timed out after %ss: %s", timeout, args[0] if args else "")
        return (
            124,
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
        )

    return (
        process.returncode or 0,
        stdout.decode("utf-8", errors="replace"),
        stderr.decode("utf-8", errors="replace"),
    )
