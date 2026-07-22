# 0008. Tier 1 Multilogin co-located with worker via `network_mode: host` on Linux

- **Status:** Accepted
- **Date:** 2026-07-22

## Context

Tier 1 (LinkedIn photo scrape) requires a Selenium WebDriver session attached to a browser
profile launched by the Multilogin desktop/daemon process.

Multilogin binds the per-profile Selenium debug port to `127.0.0.1` only — it is a loopback-only
socket.  This means the port is only reachable from within the same OS network namespace as
Multilogin itself.

On **Windows + WSL2 + Docker Engine**, Multilogin runs on the Windows host.  WSL2 is a Linux VM
with its own network namespace; even with correct host IP routing (`MULTILOGIN_HOST_IP`) a
WSL2 container cannot reach a socket that Windows has bound exclusively to its own loopback.
The result is `ConnectTimeoutError` on every Tier 1 attempt despite the launcher API (port 45001)
being reachable fine.

On **bare Linux** (EC2, VPS, dedicated server), Docker supports `network_mode: host`, which
makes a container share the host's full network stack including its loopback interface.  Two
containers both running with `network_mode: host` therefore see the same `127.0.0.1`.

## Decision

We chose **containerised Multilogin with `network_mode: host` on Linux** over the alternatives:

- **WSL2/Windows path** — rejected as a production target because the loopback isolation
  is OS-level and cannot be bridged regardless of hostname mapping or port-proxy tricks.
- **TCP proxy on Windows** — rejected because the Selenium debug port is dynamically assigned
  per profile start; proxying it would require intercepting the port number out of the
  `start_profile` response and setting up a forward before `connect_selenium` is called —
  fragile and operationally unmaintainable.
- **Host-native Windows worker** — viable for local dev (Architecture B from the investigation),
  but not production because it requires an uncontainerised Python process with manual
  dependency management outside of Compose.

`network_mode: host` on Linux is deterministic, requires zero application code changes, is
the same approach used in production by the SMA project in this organisation
(`1Touch-dev/Social_Media_Automations`), and the `Dockerfile.multilogin` already existed there
as a proven reference.

## Tradeoffs

- `network_mode: host` disables Docker's inter-service DNS for affected containers.
  Services must communicate via `localhost` / `127.0.0.1` rather than container names.
  Only `multilogin` and `worker` use host mode; all other services stay on the default bridge.
- Tier 1 is now **Linux-only** in production.  Running the full stack on Windows/macOS with
  Docker Desktop will not produce a working Tier 1 — the `docker-compose.tier1.yml` comments
  document this limitation for local development.
- The Multilogin `.deb` is pulled from an S3 bucket at image build time using
  `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` build args.  These credentials are baked into
  the build cache but not into the final image layers (they are only used in the `aws s3 cp`
  `RUN` layer).  Rotate them if the bucket is re-keyed.
- `shm_size: 2gb` and `cap_add: SYS_ADMIN` are required for Chrome to function inside the
  container.  `seccomp:unconfined` is required by the Chromium sandbox.

## Consequences

- New files:
  - `backend/docker/Dockerfile.multilogin` — Ubuntu 24.04, installs mlxapp, non-root user,
    Xvfb + x11vnc + mlxapp watchdog startup script.
  - `backend/docker/docker-compose.multilogin.yml` — Linux overlay: `multilogin` service +
    `worker` override (`network_mode: host`, `MULTILOGIN_SELENIUM_HOST=http://127.0.0.1`,
    `MULTILOGIN_LAUNCHER_URL=https://127.0.0.1:45001/api/v2`).
- `backend/scripts/start_production.sh` gains `--with-linux-mlx` / `ENABLE_LINUX_MLX=true`
  to load the overlay; the WSL2 host-IP auto-detect block is skipped when this flag is active.
- No application code changes — `connect_selenium` in
  `backend/app/integrations/linkedin/login.py` already reads `settings.multilogin_selenium_host`
  whose default is `http://127.0.0.1`, and `MultiloginClient._launcher_client` already uses
  `verify=False` for the self-signed launcher cert.
- `MULTILOGIN_SELENIUM_HOST` must not be set to anything other than `http://127.0.0.1` when
  running with this overlay (the `docker-compose.multilogin.yml` override enforces this).
- Production deployment command:
  ```bash
  bash backend/scripts/start_production.sh --with-tier1 --with-linux-mlx
  ```
