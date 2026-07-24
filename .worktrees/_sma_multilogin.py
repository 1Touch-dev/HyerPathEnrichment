#!/usr/bin/env python3
"""
🌐 MULTILOGIN INTEGRATION MODULE
===============================
Centralized Multilogin management for all Instagram automation scripts.
Handles authentication, profile lifecycle, and WebDriver setup with 100% consistency.

This module extracts and centralizes all Multilogin-related functionality from:
- comment.py, complete_instagram.py, follow.py, like.py, post.py
- report_profile.py, targeted_automation.py, topic_based_interaction.py, unfollow.py
"""

import os
import asyncio
from random import gauss
import time
import socket
import hashlib
import traceback
import logging
import threading
from typing import Optional, Dict, Any, Tuple
from contextlib import contextmanager
import requests
import ssl
import urllib3
from selenium import webdriver
from selenium.webdriver.chromium.options import ChromiumOptions
from selenium.common.exceptions import WebDriverException

# ---------------------------------------------------------------------------
# PROFILE STARTUP LOCK
# Multilogin launcher throws "Direct Connection IP error" when multiple
# profiles attempt to start simultaneously. This process-level lock enforces
# a 15-second gap between successive profile starts.
# In a multi-process Celery setup each worker process has its own lock, but
# because each worker only runs one campaign at a time that is sufficient —
# the 15-second delay per process prevents the launcher from being hammered.
# ---------------------------------------------------------------------------
_PROFILE_START_LOCK = threading.Lock()
_PROFILE_START_DELAY_SEC = 15  # seconds between successive profile starts

# CPU-optimized Chrome options (50-70% CPU reduction per browser)
from plugins.shared.core.chrome_options import get_campaign_chrome_options
from plugins.shared.core.selenium_remote_timeouts import (
    apply_remote_http_read_timeout,
    default_page_load_timeout_seconds,
    default_remote_http_timeout_seconds,
)

# Circuit breaker for Multilogin API protection
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from core.unified_circuit_breaker import (
    get_multilogin_breaker,
    CircuitBreakerError,
    loud_error
)

# Note: Settings import removed - no longer needed for standalone script execution
# from app.config import get_settings
# settings = get_settings()


# Environment loading now handled by utilities.EnvironmentManager

# Disable SSL warnings for development (Multilogin often has cert issues)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# GLOBAL SSL BYPASS FOR MULTILOGIN LAUNCHER
# The Multilogin launcher uses a self-signed/expired SSL certificate.
# Monkey-patch urllib3 at module-load time to always skip verification for
# connections to launcher.mlx.yt:45001 and 127.0.0.1:45001.
# This works in all Python/urllib3 versions and survives prefork.
# ---------------------------------------------------------------------------
import urllib3.connectionpool as _cp
_orig_connect = _cp.HTTPSConnectionPool._new_conn if hasattr(_cp.HTTPSConnectionPool, '_new_conn') else None

def _disable_ssl_for_mlx_launcher():
    """Globally disable SSL cert verification for Multilogin launcher connections."""
    try:
        import ssl as _ssl
        import urllib3.util.ssl_ as _ssl_util
        _orig_create_ctx = _ssl_util.create_urllib3_context

        def _patched_create_urllib3_context(*args, **kwargs):
            ctx = _orig_create_ctx(*args, **kwargs)
            ctx.check_hostname = False
            ctx.verify_mode = _ssl.CERT_NONE
            return ctx

        _ssl_util.create_urllib3_context = _patched_create_urllib3_context
    except Exception:
        pass

_disable_ssl_for_mlx_launcher()

# ==============================================================================
# MULTILOGIN CONSTANTS & CONFIGURATION
# ==============================================================================

# Multilogin API endpoints - configurable for different network modes
# MULTILOGIN_API_URL environment variable allows switching between:
#   - Docker (Mac/Win):    https://host.docker.internal:45001 (access host Multilogin from container)
#   - Linux (host mode):   https://127.0.0.1:45001
#   - Default (localhost): https://launcher.mlx.yt:45001
MULTILOGIN_BASE_URL = os.environ.get("MULTILOGIN_API_URL", "https://launcher.mlx.yt:45001")

# Cloud auth API only — never point this at the local launcher (e.g. :35000 / :45001);
# POST /user/signin to the launcher returns Python http.server 501 Unsupported method ('POST').
MLX_BASE = os.environ.get("MULTILOGIN_API_BASE", "https://api.multilogin.com").rstrip("/")
MLX_LAUNCHER = f"{MULTILOGIN_BASE_URL}/api/v1"
MLX_LAUNCHER_V1 = f"{MULTILOGIN_BASE_URL}/api/v1"
MLX_LAUNCHER_V2 = f"{MULTILOGIN_BASE_URL}/api/v2"

# WebDriver connection host - configurable for Docker environments
# In Kubernetes with headless service: set SELENIUM_HOST=service-name (resolves to pod IP)
# In Docker: set SELENIUM_HOST=multilogin (container name)
# Locally: defaults to 127.0.0.1
SELENIUM_HOST = os.environ.get("SELENIUM_HOST", "127.0.0.1")
LOCALHOST = f"http://{SELENIUM_HOST}"
print(f"🌐 Selenium host configured: {SELENIUM_HOST}")


class MultiloginChromeDriverAttachError(Exception):
    """ChromeDriver port was returned by Multilogin but Selenium could not attach."""

    def __init__(self, message: str, profile_id: str = "", port: int | None = None):
        super().__init__(message)
        self.profile_id = profile_id
        self.port = port

HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}

# Default timeouts and retry settings
DEFAULT_REQUEST_TIMEOUT = 120  # Increased for Kubernetes (profile start can be slow)
DEFAULT_PROFILE_START_TIMEOUT = 120
DEFAULT_PAGE_LOAD_TIMEOUT = 60
DEFAULT_IMPLICIT_WAIT = 10
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY = 5

# ---------------------------------------------------------------------------
# PROXY BYPASS FOR MULTILOGIN API
# HTTP(S)_PROXY environment variables can route requests to local proxies that
# don't support POST (e.g., Python http.server), causing 501 errors.
# We explicitly bypass proxies for Multilogin API calls.
# ---------------------------------------------------------------------------
NO_PROXY_FOR_MULTILOGIN = {"http": None, "https": None}

# ---------------------------------------------------------------------------
# REDIS TOKEN CACHE
# Multilogin API rate-limits signin requests aggressively (returns 501 when
# exceeded).  Instead of every campaign hitting /user/signin independently,
# we cache the token+refresh_token pair in Redis so all Celery workers share
# one set of credentials.
# ---------------------------------------------------------------------------
_TOKEN_CACHE_KEY = "multilogin:auth_token_cache"
_TOKEN_CACHE_LOCK_KEY = "multilogin:auth_token_lock"
_TOKEN_CACHE_TTL = 1200  # 20 minutes — Multilogin JWTs are valid for ~30 min


def _get_redis_for_token_cache():
    """Return a sync Redis client for token caching, or None."""
    try:
        import redis as _redis
        from app.config import get_settings
        settings = get_settings()
        client = _redis.Redis.from_url(
            settings.redis.url,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
        )
        client.ping()
        return client
    except Exception:
        return None


def _get_cached_multilogin_token(username: str):
    """Return (token, refresh_token) from Redis, or (None, None)."""
    try:
        r = _get_redis_for_token_cache()
        if not r:
            return None, None
        import json
        raw = r.get(f"{_TOKEN_CACHE_KEY}:{username}")
        if not raw:
            return None, None
        data = json.loads(raw)
        return data.get("token"), data.get("refresh_token")
    except Exception:
        return None, None


def _cache_multilogin_token(username: str, token: str, refresh_token: str | None):
    """Store token in Redis with TTL."""
    try:
        r = _get_redis_for_token_cache()
        if not r:
            return
        import json
        r.setex(
            f"{_TOKEN_CACHE_KEY}:{username}",
            _TOKEN_CACHE_TTL,
            json.dumps({"token": token, "refresh_token": refresh_token or ""}),
        )
    except Exception:
        pass


def _acquire_signin_lock(username: str, timeout: int = 30) -> bool:
    """Try to acquire a short-lived lock for signin. Returns True if acquired."""
    try:
        r = _get_redis_for_token_cache()
        if not r:
            return True  # No Redis = proceed without locking
        import time as _time
        lock_key = f"{_TOKEN_CACHE_LOCK_KEY}:{username}"
        deadline = _time.monotonic() + timeout
        while _time.monotonic() < deadline:
            if r.set(lock_key, "1", nx=True, ex=30):
                return True
            _time.sleep(0.5)
            cached_tok, _ = _get_cached_multilogin_token(username)
            if cached_tok:
                return False  # Another worker already signed in
        return True  # Timeout — proceed anyway
    except Exception:
        return True


def _release_signin_lock(username: str):
    try:
        r = _get_redis_for_token_cache()
        if r:
            r.delete(f"{_TOKEN_CACHE_LOCK_KEY}:{username}")
    except Exception:
        pass

def create_no_proxy_session():
    """
    Create a requests session that COMPLETELY ignores proxy environment variables.
    This is the most aggressive proxy bypass - use for Multilogin API calls.
    """
    session = requests.Session()
    session.trust_env = False  # Completely ignore HTTP_PROXY, HTTPS_PROXY, etc.
    session.proxies = {"http": None, "https": None}
    return session

# SSL Configuration for Multilogin connections
def create_ssl_session(bypass_proxy: bool = True):
    """
    Create requests session with SSL configuration for Multilogin.

    Args:
        bypass_proxy: If True, explicitly bypass HTTP(S)_PROXY for this session.
                      This prevents 501 errors when proxies don't support POST.
    """
    session = requests.Session()

    # Configure SSL adapter with more lenient settings
    from requests.adapters import HTTPAdapter
    from urllib3.util.ssl_ import create_urllib3_context

    # Create custom SSL context that fully disables ALL cert validation
    ctx = create_urllib3_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.maximum_version = ssl.TLSVersion.TLSv1_3

    # CustomHTTPSAdapter: overrides both poolmanager AND send() to force verify=False
    # This handles expired certs, IP mismatch, self-signed certs in all Python/urllib3 versions
    class CustomHTTPSAdapter(HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            kwargs['ssl_context'] = ctx
            return super().init_poolmanager(*args, **kwargs)

        def send(self, request, **kwargs):
            kwargs['verify'] = False
            return super().send(request, **kwargs)

    session.mount('https://', CustomHTTPSAdapter())
    session.verify = False

    # Bypass proxy if requested (prevents 501 errors from simple proxy servers)
    if bypass_proxy:
        session.trust_env = False
        session.proxies = NO_PROXY_FOR_MULTILOGIN

    return session


def _build_remote_safe_chromium_options(options: ChromiumOptions) -> ChromiumOptions:
    """
    Build a ChromiumOptions payload that is safe for Multilogin's remote driver
    parser. We preserve performance-critical command-line args and drop
    problematic experimental options (prefs/excludeSwitches) that can trigger
    `cannot parse capability: goog:chromeOptions` on some launcher versions.
    """
    safe_options = ChromiumOptions()

    # Preserve command line arguments (where our CPU optimizations live).
    for arg in getattr(options, "arguments", []) or []:
        safe_options.add_argument(arg)

    # Preserve optional binary location when configured.
    binary_location = getattr(options, "binary_location", None)
    if binary_location:
        safe_options.binary_location = binary_location

    # Preserve page load strategy.
    page_load_strategy = getattr(options, "page_load_strategy", None) or "normal"
    safe_options.page_load_strategy = page_load_strategy

    # Keep debuggerAddress only if explicitly provided.
    experimental_options = getattr(options, "experimental_options", {}) or {}
    debugger_address = experimental_options.get("debuggerAddress")
    if debugger_address:
        safe_options.add_experimental_option("debuggerAddress", debugger_address)

    return safe_options


def _create_remote_driver_with_options_fallback(
    command_executor: str,
    options: ChromiumOptions,
    timeout: Optional[int] = None,
) -> webdriver.Remote:
    """
    Build a Remote WebDriver with Multilogin-safe options and retry with minimal
    options only if capability payloads are still rejected by the remote driver.

    Args:
        timeout: urllib3 read timeout (seconds) for every Selenium HTTP command.
                 Must be >= page_load_timeout or slow navigations raise ReadTimeoutError.
                 Default: SELENIUM_REMOTE_HTTP_TIMEOUT or 150s.
    """
    from selenium.webdriver.remote.client_config import ClientConfig

    if timeout is None:
        timeout = default_remote_http_timeout_seconds()

    remote_safe_options = _build_remote_safe_chromium_options(options)

    # Create a ClientConfig with timeout to prevent indefinite hangs
    # This is the proper way to set timeout in Selenium 4.x
    client_config = ClientConfig(remote_server_addr=command_executor, timeout=timeout)

    try:
        return webdriver.Remote(command_executor=command_executor, options=remote_safe_options, client_config=client_config)
    except WebDriverException as e:
        error_msg = str(e)
        if "cannot parse capability: goog:chromeOptions" not in error_msg:
            raise

        print("⚠️ Remote driver rejected Chromium options payload; retrying with minimal ChromiumOptions...")
        fallback_options = ChromiumOptions()
        fallback_options.page_load_strategy = "normal"
        return webdriver.Remote(
            command_executor=command_executor,
            options=fallback_options,
            client_config=client_config,
        )

# Set up logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# ==============================================================================
# MULTILOGIN MANAGER CLASS
# ==============================================================================

class MultiloginManager:
    """
    Centralized Multilogin integration manager.

    Handles all Multilogin operations:
    - Authentication with MD5 hashed credentials
    - Profile lifecycle management (start/stop)
    - WebDriver setup with ChromiumOptions
    - Error handling and retries
    """

    def __init__(self,
            load_env_paths: Optional[list] = None,
            request_timeout: int = DEFAULT_REQUEST_TIMEOUT,
            max_retry_attempts: int = MAX_RETRY_ATTEMPTS,
            retry_delay: int = RETRY_DELAY,
            enable_logging: bool = True):
        """
        Initialize MultiloginManager with environment variable loading.

        Args:
            load_env_paths: List of paths to .env files to load (in order of preference)
            request_timeout: Timeout for HTTP requests to Multilogin API
            max_retry_attempts: Maximum retry attempts for failed operations
            retry_delay: Delay between retry attempts in seconds
            enable_logging: Whether to enable detailed logging
        """
        self.token = None
        self.refresh_token = None
        self.driver = None
        self.profile_active = False
        self._active_profile_lock = None
        self.request_timeout = request_timeout
        self.max_retry_attempts = max_retry_attempts
        self.retry_delay = retry_delay
        self.session_stats = {
            'signin_attempts': 0,
            'profile_start_attempts': 0,
            'errors': []
        }

        # Configure logging
        if not enable_logging:
            logger.setLevel(logging.WARNING)

        # Load environment variables
        self._load_environment_variables(load_env_paths)

        # Get credentials from environment
        self.username = os.getenv("MULTILOGIN_USERNAME")
        self.password = os.getenv("MULTILOGIN_PASSWORD")
        self.profile_id = os.getenv("MULTILOGIN_PROFILE_ID")
        self.workspace_id = os.getenv("MULTILOGIN_WORKSPACE_ID")
        self.folder_id = os.getenv("MULTILOGIN_FOLDER_ID")

        # Validate required credentials
        self._validate_credentials()

        logger.info(f"MultiloginManager initialized for profile {self.profile_id}")

    def _load_environment_variables(self, custom_paths: Optional[list] = None):
        """
        Load environment variables using EnvironmentManager from utilities.
        """
        # Use EnvironmentManager for comprehensive environment handling
        try:
            from .utilities import EnvironmentManager
        except ImportError:
            from .utilities import EnvironmentManager

        env_manager = EnvironmentManager(custom_env_paths=custom_paths)
        self.env_manager = env_manager  # Store for potential later use

        # Print summary for backward compatibility
        if env_manager.loaded_files:
            print(f"✅ Loaded environment from: {', '.join(env_manager.loaded_files)}")
        else:
            print("⚠️ Warning: No .env file found in expected locations")

    def _validate_credentials(self):
        """
        Validate that all required Multilogin credentials are present.
        """
        required_vars = {
            'MULTILOGIN_USERNAME': self.username,
            'MULTILOGIN_PASSWORD': self.password,
            'MULTILOGIN_PROFILE_ID': self.profile_id,
            'MULTILOGIN_FOLDER_ID': self.folder_id,
            'MULTILOGIN_WORKSPACE_ID': self.workspace_id
        }

        missing_vars = [var for var, value in required_vars.items() if not value]
        if missing_vars:
            raise ValueError(
                f"❌ Missing required environment variables: {', '.join(missing_vars)}\n"
                f"Please check your .env file contains these Multilogin credentials."
            )

    def _check_multilogin_status(self):
        """No-op kept for backward compatibility. Callers across plugin files
        invoke this method; making it a fast no-op at the source avoids
        needing to patch every caller."""
        logger.debug("_check_multilogin_status called (no-op)")

    def _print_ssl_troubleshooting(self):
        """Print detailed SSL troubleshooting information"""
        print("\n🔧 SSL TROUBLESHOOTING GUIDE:")
        print("=" * 50)
        print("This SSL error typically indicates one of these issues:")
        print("")
        print("1. 🏢 MULTILOGIN APP STATUS:")
        print("   • Ensure Multilogin app is running")
        print("   • Check that your subscription is active")
        print("   • Verify launcher is enabled in settings")
        print("")
        print("2. 🌐 NETWORK & FIREWALL:")
        print("   • Disable VPN/proxy temporarily")
        print("   • Check firewall isn't blocking port 45001")
        print("   • Try different network if possible")
        print("")
        print("3. 🔐 SSL/TLS CONFIGURATION:")
        print("   • Multilogin may have updated their SSL certificates")
        print("   • Try restarting Multilogin app")
        print("   • Check for app updates")
        print("")
        print("4. 🖥️ SYSTEM SPECIFIC:")
        print("   • On macOS: Check System Integrity Protection")
        print("   • On Windows: Check Windows Defender settings")
        print("   • Try running as administrator/sudo")
        print("")
        print("5. 🔄 QUICK FIXES TO TRY:")
        print("   • Restart Multilogin app completely")
        print("   • Clear Multilogin cache/data")
        print("   • Update to latest Multilogin version")
        print("   • Check Multilogin status page for known issues")
        print("")
        print("If issues persist, contact Multilogin support with this error.")
        print("=" * 50)

    def test_ssl_connection(self) -> bool:
        """Test SSL connection to Multilogin services - useful for diagnostics"""
        try:
            print("🧪 Testing SSL connection to Multilogin...")

            # Test connection to main API
            session = create_ssl_session()
            response = session.get(f"{MLX_BASE}/user/info", timeout=10)
            print(f"✅ Main API connection test: {response.status_code}")

            # Test connection to launcher
            response = session.get(f"{MLX_LAUNCHER_V2}/status", timeout=10)
            print(f"✅ Launcher API connection test: {response.status_code}")

            print("✅ SSL connection test passed!")
            return True

        except Exception as e:
            print(f"❌ SSL connection test failed: {str(e)}")
            self._print_ssl_troubleshooting()
            return False

    def signin_multilogin(self) -> str:
        """Sign in to Multilogin with Redis-cached token to avoid rate limits."""

        # ---- 1. Try Redis token cache first ----
        cached_token, cached_refresh = _get_cached_multilogin_token(self.username)
        if cached_token:
            # Quick validation: check TTL remaining — if < 120s, force refresh to avoid mid-run expiry
            try:
                _redis = _get_redis_for_token_cache()
                if _redis:
                    ttl = _redis.ttl(f"{_TOKEN_CACHE_KEY}:{self.username}")
                    if ttl < 120:  # less than 2 min left — force re-auth
                        print(f"⚠️ Cached token expiring soon (TTL={ttl}s) — forcing fresh auth")
                        _redis.delete(f"{_TOKEN_CACHE_KEY}:{self.username}")
                        cached_token = None
            except Exception:
                pass

        if cached_token:
            self.token = cached_token
            self.refresh_token = cached_refresh or None
            print("🔑 Using cached Multilogin token from Redis")
            return self.token

        # ---- 2. Acquire signin lock so only one worker hits the API ----
        got_lock = _acquire_signin_lock(self.username, timeout=30)
        if not got_lock:
            cached_token, cached_refresh = _get_cached_multilogin_token(self.username)
            if cached_token:
                self.token = cached_token
                self.refresh_token = cached_refresh or None
                print("🔑 Using cached Multilogin token (another worker signed in)")
                return self.token

        try:
            # Wrap signin with circuit breaker protection
            breaker = get_multilogin_breaker()
            try:
                return breaker.call_sync(self._do_signin_multilogin)
            except CircuitBreakerError as e:
                loud_error(
                    "MULTILOGIN API CIRCUIT BREAKER IS OPEN - Cannot authenticate",
                    exception=e
                )
                raise Exception(f"Multilogin authentication unavailable: {str(e)}")
        finally:
            _release_signin_lock(self.username)

    async def signin_multilogin_async(self) -> str:
        """Async wrapper for signin_multilogin() using a worker thread."""
        return await asyncio.to_thread(self.signin_multilogin)

    def _do_signin_multilogin(self) -> str:
        """Actual signin logic — called only when no cached token is available."""
        payload = {
            "email": self.username,
            "password": hashlib.md5(self.password.encode()).hexdigest(),
        }

        print("🔐 Signing in to Multilogin...")
        print(f"📡 Target API: {MLX_BASE}")

        request_methods = [
            lambda: create_no_proxy_session().post(
                f"{MLX_BASE}/user/signin", json=payload, timeout=DEFAULT_REQUEST_TIMEOUT
            ),
            lambda: create_ssl_session(bypass_proxy=True).post(
                f"{MLX_BASE}/user/signin", json=payload, timeout=DEFAULT_REQUEST_TIMEOUT
            ),
            lambda: (lambda s: (setattr(s, 'trust_env', False), s.post(
                f"{MLX_BASE}/user/signin", json=payload, timeout=DEFAULT_REQUEST_TIMEOUT,
                verify=False, proxies=NO_PROXY_FOR_MULTILOGIN
            ))[1])(requests.Session())
        ]

        last_exc = None
        rate_limit_retry_delays = [5, 10, 20, 40]  # Exponential backoff for rate limits

        for attempt, request_method in enumerate(request_methods, 1):
            try:
                print(f"🔄 Signin attempt {attempt}/{len(request_methods)}")

                r = request_method()

                # Improved rate limit handling with exponential backoff
                if r.status_code == 501:
                    loud_error(
                        f"MULTILOGIN RATE LIMIT (501) on attempt {attempt}",
                        exception=None
                    )

                    # Try multiple retries with exponential backoff
                    for retry_idx, delay in enumerate(rate_limit_retry_delays):
                        print(f"⚠️ Rate limit retry {retry_idx + 1}/{len(rate_limit_retry_delays)}, waiting {delay}s...")
                        time.sleep(delay)
                        r = request_method()

                        if r.status_code != 501:
                            print(f"✅ Rate limit retry succeeded after {delay}s wait")
                            break

                        if retry_idx == len(rate_limit_retry_delays) - 1:
                            loud_error(
                                f"MULTILOGIN RATE LIMIT persists after {len(rate_limit_retry_delays)} retries",
                                exception=Exception(f"Status code: {r.status_code}, Response: {r.text[:200]}")
                            )

                if r.status_code != 200:
                    error_msg = f"\nError during login (HTTP {r.status_code}): {r.text[:200]}\n"
                    print(error_msg)
                    if attempt == len(request_methods):
                        raise Exception("Failed to login to Multilogin")
                    continue

                response = r.json()["data"]
                base_token = response.get("token")
                refresh_token = response.get("refresh_token")

                if not base_token:
                    raise Exception("Login response did not contain 'token'")

                self.token = base_token
                self.refresh_token = refresh_token
                print("✅ Successfully signed in to Multilogin (base token)")

                if self.refresh_token and self.workspace_id:
                    self._exchange_refresh_token()

                # Cache the final token in Redis for other workers
                _cache_multilogin_token(self.username, self.token, self.refresh_token)

                print("🔑 Active Multilogin token acquired and cached (ready for launcher)")
                return self.token

            except (requests.exceptions.SSLError, ssl.SSLError) as ssl_error:
                last_exc = ssl_error
                print(f"⚠️ SSL error on attempt {attempt}: {str(ssl_error)[:100]}")
                if attempt < len(request_methods):
                    continue
                self._print_ssl_troubleshooting()
                raise Exception(f"SSL connection failed: {str(ssl_error)}")

            except Exception as e:
                last_exc = e
                print(f"⚠️ General error on attempt {attempt}: {str(e)}")
                if attempt < len(request_methods):
                    continue
                print(f"❌ Signin failed after {len(request_methods)} attempts")
                raise

    def _exchange_refresh_token(self):
        """Exchange refresh token for workspace-scoped token with circuit breaker protection."""
        breaker = get_multilogin_breaker()

        def _do_exchange():
            refresh_payload = {
                "workspace_id": self.workspace_id,
                "email": self.username,
                "refresh_token": self.refresh_token,
            }
            print("🔄 Exchanging refresh token for workspace-scoped token...")
            refresh_resp = None
            retry_delays = [0.5, 1.5, 3.0]  # Extended retry delays
            for refresh_attempt in range(len(retry_delays) + 1):
                refresh_resp = create_no_proxy_session().post(
                    f"{MLX_BASE}/user/refresh_token",
                    json=refresh_payload,
                    timeout=DEFAULT_REQUEST_TIMEOUT,
                )
                if refresh_resp.status_code == 200:
                    break
                body = (refresh_resp.text or "")[:300].lower()
                retryable = (
                    refresh_resp.status_code >= 500
                    or "internal_db_error" in body
                    or "timeout" in body
                    or "pool" in body
                )
                if retryable and refresh_attempt < len(retry_delays):
                    wait_s = retry_delays[refresh_attempt]
                    print(f"⚠️ /user/refresh_token transient error {refresh_resp.status_code}; retrying in {wait_s}s")
                    time.sleep(wait_s)
                    continue
                break

            if refresh_resp is not None and refresh_resp.status_code == 200:
                refresh_data = refresh_resp.json().get("data") or {}
                refreshed_token = refresh_data.get("token")
                if refreshed_token:
                    self.token = refreshed_token
                    print("✅ Obtained refreshed workspace token from /user/refresh_token")
                    return refreshed_token
                else:
                    loud_error(
                        "MULTILOGIN refresh_token response missing 'token' field",
                        exception=None
                    )
                    print("⚠️ /user/refresh_token response missing 'token' field, using base token")
                    return None
            elif refresh_resp is not None:
                error_msg = f"/user/refresh_token failed with status {refresh_resp.status_code}: {refresh_resp.text[:200]}"
                loud_error(f"MULTILOGIN REFRESH TOKEN FAILED: {error_msg}", exception=None)
                raise Exception(error_msg)

        try:
            # Call with circuit breaker protection
            breaker.call_sync(_do_exchange)
        except CircuitBreakerError as e:
            loud_error(
                "MULTILOGIN REFRESH TOKEN - Circuit breaker is OPEN",
                exception=e
            )
            print(f"⚠️ Circuit breaker OPEN for refresh token, using base token")
        except Exception as refresh_error:
            loud_error(
                "MULTILOGIN REFRESH TOKEN ERROR",
                exception=refresh_error
            )
            print(f"⚠️ Error while calling /user/refresh_token: {str(refresh_error)[:200]}")

    def start_profile(self, selenium_options: Optional[dict] = None) -> webdriver.Remote:
        """
        Start the Multilogin browser profile and return Selenium WebDriver with SSL error handling.
        Implements the exact pattern used across all Instagram scripts.

        QUEUE IMPLEMENTATION:
        Uses Redis distributed lock to serialize profile starts across all workers.
        When 50 campaigns start simultaneously, this prevents Multilogin from being
        overwhelmed (which causes DIRECT_IP_CONNECTION_ERROR).

        Flow:
        1. Acquire per-profile active lock (one automation per profile)
        2. Acquire Redis start lock (wait if another profile is starting)
        3. Start the Multilogin profile and attach ChromeDriver
        4. Wait 15 seconds (configurable) to let daemon stabilize
        5. Release start lock (active lock held until cleanup())

        Config via env vars:
        - MULTILOGIN_PROFILE_START_DELAY_SECONDS=15
        - MULTILOGIN_PROFILE_START_LOCK_ENABLED=true (set false to disable)
        - MULTILOGIN_PROFILE_ACTIVE_WAIT_SECONDS=60
        - MULTILOGIN_CHROMEDRIVER_ATTACH_ATTEMPTS=15

        Args:
            selenium_options: Additional options for ChromiumOptions

        Returns:
            Selenium WebDriver instance connected to Multilogin profile

        Raises:
            MultiloginProfileInUseError: Profile already held by another campaign
            MultiloginChromeDriverAttachError: Profile started but ChromeDriver attach failed
            Exception: If profile startup fails after retries
        """
        from core.multilogin_lock import (
            MultiloginActiveProfileLock,
            MultiloginProfileInUseError,
            MultiloginProfileLock,
        )

        print(f"🚀 Starting profile {self.profile_id}...")

        self._active_profile_lock = MultiloginActiveProfileLock(
            profile_id=str(self.profile_id),
            owner_id=str(self.profile_id),
        )
        try:
            self._active_profile_lock.acquire()
        except MultiloginProfileInUseError:
            self._active_profile_lock = None
            raise

        lock = MultiloginProfileLock(owner_id=str(self.profile_id))
        try:
            with lock:
                print(f"✅ Redis lock acquired — starting profile {self.profile_id}")

                breaker = get_multilogin_breaker()
                try:
                    return breaker.call_sync(self._do_start_profile, selenium_options)
                except CircuitBreakerError as e:
                    loud_error(
                        f"MULTILOGIN PROFILE START - Circuit breaker is OPEN for profile {self.profile_id}",
                        exception=e,
                    )
                    self._release_active_profile_lock()
                    raise Exception(f"Multilogin profile start unavailable: {str(e)}")
        except Exception:
            if self.driver is None:
                self._release_active_profile_lock()
            raise

    async def start_profile_async(
        self, selenium_options: Optional[dict] = None
    ) -> webdriver.Remote:
        """Async wrapper for start_profile() using a worker thread."""
        return await asyncio.to_thread(self.start_profile, selenium_options)

    def _release_active_profile_lock(self) -> None:
        if self._active_profile_lock is not None:
            try:
                self._active_profile_lock.release()
            except Exception as e:
                print(f"⚠️ Active profile lock release failed: {e}")
            finally:
                self._active_profile_lock = None

    def _prepare_profile_start_attempt(self) -> None:
        """Stop stale browser state before a profile start or circuit-breaker retry."""
        print(
            f"🔄 Preparing profile start attempt profile_id={self.profile_id} "
            f"name={getattr(self, 'profile_name', 'n/a')}"
        )
        if self.driver:
            try:
                self.quit_driver()
            except Exception as e:
                print(f"⚠️ Pre-start driver quit (non-fatal): {e}")
        try:
            self.force_stop_profile()
        except Exception as e:
            print(f"⚠️ Pre-start force stop (non-fatal): {e}")
        time.sleep(2)

    def _cleanup_failed_profile_start(self, selenium_port: int | None = None) -> None:
        """Stop profile and reset driver after ChromeDriver attach failure."""
        print(
            f"🧹 Cleaning up failed profile start profile_id={self.profile_id} "
            f"port={selenium_port}"
        )
        if self.driver:
            try:
                self.quit_driver()
            except Exception as e:
                print(f"⚠️ Cleanup driver quit failed: {e}")
        try:
            self.force_stop_profile()
        except Exception as e:
            print(f"⚠️ Cleanup force stop failed: {e}")
        self.profile_active = False
        time.sleep(3)

    def _attach_chromedriver(
        self, selenium_port: int, options: ChromiumOptions
    ) -> webdriver.Remote:
        """Verify ChromeDriver port is reachable and attach Selenium WebDriver."""
        max_retries = int(os.environ.get("MULTILOGIN_CHROMEDRIVER_ATTACH_ATTEMPTS", "15"))
        retry_delay = 0.5
        driver = None
        last_connect_code = None
        last_error = ""

        print(
            f"⏳ profile_id={self.profile_id} — waiting for ChromeDriver on "
            f"{SELENIUM_HOST}:{selenium_port} (max {max_retries} attach attempts)..."
        )

        for attempt in range(1, max_retries + 1):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                last_connect_code = sock.connect_ex((SELENIUM_HOST, selenium_port))
                sock.close()

                if last_connect_code != 0:
                    err_label = (
                        "connection refused"
                        if last_connect_code == 111
                        else f"connect error {last_connect_code}"
                    )
                    last_error = err_label
                    print(
                        f"🔄 profile_id={self.profile_id} port={selenium_port} "
                        f"attach {attempt}/{max_retries}: port not ready ({err_label})"
                    )
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 1.5, 5)
                    continue

                print(
                    f"🔌 profile_id={self.profile_id} port={selenium_port} "
                    f"attach {attempt}/{max_retries}: port reachable, connecting Selenium..."
                )
                driver = _create_remote_driver_with_options_fallback(
                    command_executor=f"{LOCALHOST}:{selenium_port}",
                    options=options,
                )
                print(
                    f"✅ profile_id={self.profile_id} connected to ChromeDriver "
                    f"on {SELENIUM_HOST}:{selenium_port}"
                )
                return driver

            except Exception as e:
                last_error = str(e).split("Stacktrace")[0].strip()
                if (
                    "Connection refused" in last_error
                    or "Failed to establish" in last_error
                    or "111" in last_error
                ):
                    print(
                        f"🔄 profile_id={self.profile_id} port={selenium_port} "
                        f"attach {attempt}/{max_retries}: ChromeDriver not ready "
                        f"({last_error[:120]})"
                    )
                    if attempt < max_retries:
                        time.sleep(retry_delay)
                        retry_delay = min(retry_delay * 1.5, 5)
                    continue
                raise

        if last_connect_code == 111:
            detail = f"connection refused on {SELENIUM_HOST}:{selenium_port}"
        elif last_connect_code is not None:
            detail = f"connect error {last_connect_code} on {SELENIUM_HOST}:{selenium_port}"
        else:
            detail = last_error or f"timeout on {SELENIUM_HOST}:{selenium_port}"

        raise MultiloginChromeDriverAttachError(
            f"Multilogin setup failed: ChromeDriver {detail} after {max_retries} attempts",
            profile_id=str(self.profile_id),
            port=selenium_port,
        )

    def _do_start_profile(self, selenium_options=None):
        """Internal: actual profile start logic, called under the startup lock."""
        self._prepare_profile_start_attempt()
        try:
            # Prepare headers with authorization
            auth_headers = HEADERS.copy()
            if self.token:
                auth_headers.update({"Authorization": f"Bearer {self.token}"})

            # Profile start URL - Use v2 API (v1 returns GET_PROXY_CONNECTION_IP_ERROR for proxy-assigned profiles)
            profile_start_url = f"{MLX_LAUNCHER_V2}/profile/f/{self.folder_id}/p/{self.profile_id}/start?automation_type=selenium"
            print(f"🔍 Profile start URL: {profile_start_url}")

            # Try with different request methods for SSL compatibility
            # CRITICAL: Use SSL session with custom context FIRST - this properly disables both
            # certificate verification AND hostname checking (verify=False alone doesn't disable hostname checks in Python 3.11+)
            request_methods = [
                # Method 1: SSL session with custom context (properly disables ALL SSL verification including hostname check)
                lambda: create_ssl_session().get(profile_start_url, headers=auth_headers, timeout=DEFAULT_REQUEST_TIMEOUT),
                # Method 2: Regular requests with verify=False (may still fail on hostname check in Python 3.11+)
                lambda: requests.get(profile_start_url, headers=auth_headers, timeout=DEFAULT_REQUEST_TIMEOUT, verify=False),
                # Method 3: Regular requests (SSL verification enabled) - Last resort (rarely needed)
                lambda: requests.get(profile_start_url, headers=auth_headers, timeout=DEFAULT_REQUEST_TIMEOUT),
            ]

            response = None
            for attempt, request_method in enumerate(request_methods, 1):
                try:
                    print(f"🔄 Profile start attempt {attempt}/{len(request_methods)}")

                    r = request_method()

                    if r.status_code != 200:
                        error_msg = f"\nError while starting profile: {r.text}\n"
                        print(error_msg)

                        # Token expired — clear cache and re-auth, then rebuild request_methods
                        if "UNAUTHORIZED_REQUEST" in r.text or r.status_code == 401:
                            print(
                                "⚠️ Multilogin token expired or unauthorized (401) — "
                                "clearing cached token and starting re-auth..."
                            )
                            try:
                                _redis = _get_redis_for_token_cache()
                                if _redis:
                                    _redis.delete(f"{_TOKEN_CACHE_KEY}:{self.username}")
                                self.token = None
                                self.refresh_token = None
                                print("🔄 Multilogin re-auth attempt started...")
                                self._do_signin_multilogin()
                                if self.token:
                                    print("✅ Multilogin re-auth succeeded")
                                    # Rebuild auth headers with fresh token
                                    auth_headers = HEADERS.copy()
                                    auth_headers.update({"Authorization": f"Bearer {self.token}"})
                                    # Rebuild request_methods with refreshed headers
                                    request_methods = [
                                        lambda: create_ssl_session().get(profile_start_url, headers=auth_headers, timeout=DEFAULT_REQUEST_TIMEOUT),
                                        lambda: requests.get(profile_start_url, headers=auth_headers, timeout=DEFAULT_REQUEST_TIMEOUT, verify=False),
                                    ]
                                    print("🔄 Retrying profile start with fresh token...")
                                    r2 = request_methods[0]()
                                    if r2.status_code == 200:
                                        response = r2.json()
                                        print(f"✅ Profile {self.profile_id} started successfully after re-auth")
                                        break
                                    else:
                                        print(f"⚠️ Still failing after re-auth: {r2.text[:100]}")
                                else:
                                    print("❌ Multilogin re-auth failed: no token returned")
                            except Exception as reauth_err:
                                print(f"❌ Multilogin re-auth failed: {reauth_err}")

                        # Check if profile is already running
                        if "PROFILE_ALREADY_RUNNING" in r.text:
                            print("⚠️ Profile is already running - attempting to force stop and retry...")
                            try:
                                self.force_stop_profile()
                                print("🔄 Retrying profile start after force stop...")
                                r = request_method()
                                if r.status_code == 200:
                                    response = r.json()
                                    print(f"✅ Profile {self.profile_id} started successfully after force stop")
                                    break
                            except Exception as force_stop_error:
                                print(f"❌ Force stop failed: {force_stop_error}")

                        if attempt == len(request_methods):
                            raise Exception("Failed to start Multilogin profile")
                        continue

                    response = r.json()
                    print(f"✅ Profile {self.profile_id} started successfully")
                    break

                except (requests.exceptions.SSLError, ssl.SSLError) as ssl_error:
                    print(f"⚠️ SSL error on profile start attempt {attempt}: {str(ssl_error)[:100]}")
                    if attempt < len(request_methods):
                        print(f"🔄 Trying alternative SSL method for profile start...")
                        continue
                    else:
                        print("❌ All SSL methods failed for profile start")
                        self._print_ssl_troubleshooting()
                        raise Exception(f"Profile start SSL connection failed after {len(request_methods)} attempts: {str(ssl_error)}")

                except Exception as e:
                    print(f"⚠️ General error on profile start attempt {attempt}: {str(e)}")
                    if attempt < len(request_methods):
                        continue
                    else:
                        print(f"❌ Profile start failed after {len(request_methods)} attempts")
                        raise

            if not response:
                raise Exception("Failed to get valid response from profile start")

            # Handle different response structures
            print(f"🔍 Debug: Profile start response keys: {response.keys()}")
            print(f"🔍 Debug: Full response: {response}")

            # Try to extract port from different possible response structures
            selenium_port = None

            # Format 1: {"data": {"port": 12345}} - API may return port as int or str
            if "data" in response and isinstance(response["data"], dict) and "port" in response["data"]:
                raw = response["data"]["port"]
                selenium_port = int(raw) if not isinstance(raw, int) else raw
                print(f"✅ Extracted port from response['data']['port']: {selenium_port}")

            # Format 2: {"port": 12345}
            elif "port" in response:
                raw = response["port"]
                selenium_port = int(raw) if not isinstance(raw, int) else raw
                print(f"✅ Extracted port from response['port']: {selenium_port}")

            # Format 3: {"status": {"message": "12345"}} - Port is in status.message as string
            elif "status" in response and isinstance(response["status"], dict):
                if "message" in response["status"] and response["status"]["message"]:
                    try:
                        # Port is returned as a string in status.message
                        selenium_port = int(response["status"]["message"])
                        print(f"✅ Extracted port from response['status']['message']: {selenium_port}")
                    except (ValueError, TypeError) as e:
                        print(f"❌ Failed to parse port from status.message: {response['status']['message']}")
                        raise Exception(f"Port in status.message is not a valid integer: {response['status']['message']}")

            # No valid port found
            if selenium_port is None:
                print(f"❌ Error: Could not extract port from response: {response}")
                raise Exception(f"Profile started but port not found in any known response format. Response: {str(response)[:300]}")

            # Set up ChromiumOptions with CPU optimizations (50-70% CPU savings)
            options = get_campaign_chrome_options()
            options.page_load_strategy = 'normal'

            # Apply additional options if provided (merge with optimizations)
            if selenium_options:
                for key, value in selenium_options.items():
                    if hasattr(options, key):
                        setattr(options, key, value)
                    else:
                        print(f"⚠️ Warning: Unknown ChromiumOption: {key}")

            # Wait for ChromeDriver to be ready with exponential backoff
            try:
                driver = self._attach_chromedriver(selenium_port, options)
            except MultiloginChromeDriverAttachError:
                self._cleanup_failed_profile_start(selenium_port)
                raise

            # Match Selenium HTTP read timeout to slow navigations (proxy / heavy SPAs).
            pl = default_page_load_timeout_seconds()
            driver.set_page_load_timeout(pl)
            driver.implicitly_wait(10)
            apply_remote_http_read_timeout(driver)

            self.driver = driver
            self.profile_active = True

            # NOTE: The 15-second stabilization delay is applied by
            # MultiloginProfileLock.release(apply_delay=True) in start_profile().
            # Do NOT sleep here — that would double the delay.

            return driver

        except MultiloginChromeDriverAttachError:
            raise
        except Exception as e:
            self._cleanup_failed_profile_start(
                locals().get("selenium_port") if "selenium_port" in locals() else None
            )
            raise

    def stop_profile(self) -> None:
        """
        Stop the Multilogin browser profile.
        Implements the exact cleanup pattern from all scripts.
        """
        try:
            print(f"🔄 Stopping profile {self.profile_id}...")

            # Prepare headers with authorization
            auth_headers = HEADERS.copy()
            if self.token:
                auth_headers.update({"Authorization": f"Bearer {self.token}"})

            # Use SSL-disabled session to avoid certificate verification errors
            session = create_ssl_session()
            r = session.get(f"{MLX_LAUNCHER_V1}/profile/stop/p/{self.profile_id}", headers=auth_headers, timeout=self.request_timeout)

            if r.status_code != 200:
                print(f"⚠️ Error while stopping profile: {r.text}")
            else:
                print(f"✅ Profile {self.profile_id} stopped successfully")

            self.profile_active = False

        except Exception as e:
            print(f"❌ Error stopping profile: {str(e)}")

    def force_stop_profile(self) -> None:
        """
        Force stop the Multilogin browser profile if it's running.
        Used by some scripts for cleanup scenarios.
        """
        try:
            print(f"🔥 Force stopping profile {self.profile_id}...")

            # Prepare headers with authorization if available
            auth_headers = HEADERS.copy()
            if self.token:
                auth_headers.update({"Authorization": f"Bearer {self.token}"})

            # Use SSL-disabled session to avoid certificate verification errors
            session = create_ssl_session()
            r = session.get(f"{MLX_LAUNCHER_V1}/profile/stop/p/{self.profile_id}", headers=auth_headers, timeout=self.request_timeout)

            if r.status_code != 200:
                print(f"Profile stop response: {r.text}")
            else:
                print(f"✅ Profile {self.profile_id} force stopped successfully")

            # Wait for profile to fully stop
            time.sleep(3)
            self.profile_active = False

        except Exception as e:
            print(f"❌ Error force stopping profile: {str(e)}")

    def quit_driver(self) -> None:
        """
        Safely quit the WebDriver instance.
        """
        if self.driver:
            try:
                print("🔄 Closing WebDriver...")
                self.driver.quit()
                print("✅ WebDriver closed successfully")
            except Exception as e:
                print(f"⚠️ Error closing WebDriver: {str(e)}")
            finally:
                self.driver = None

    def cleanup(self) -> None:
        """
        Complete cleanup - quit driver and stop profile.
        Should be called in finally blocks.
        """
        print("🧹 Starting Multilogin cleanup...")

        # Quit driver first
        if self.driver:
            self.quit_driver()

        # Stop profile if active
        if self.profile_active:
            self.stop_profile()

        self._release_active_profile_lock()

        print("✅ Multilogin cleanup completed")

    def __enter__(self):
        """
        Context manager entry - signin and start profile.
        """
        self.signin_multilogin()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit - cleanup resources.
        """
        self.cleanup()

        # Don't suppress exceptions
        return False

# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================

def get_multilogin_manager(env_paths: Optional[list] = None) -> MultiloginManager:
    """
    Factory function to create a MultiloginManager instance.

    Args:
        env_paths: Optional list of paths to .env files

    Returns:
        Configured MultiloginManager instance
    """
    return MultiloginManager(load_env_paths=env_paths)

def create_instagram_session(env_paths: Optional[list] = None,
                           selenium_options: Optional[dict] = None,
                           auto_navigate_to_instagram: bool = True,
                           verify_login: bool = True,
                           **manager_kwargs) -> Tuple[MultiloginManager, webdriver.Remote]:
    """
    Create a complete Instagram automation session with Multilogin.
    This is the EASIEST way to get started with Instagram automation.

    Args:
        env_paths: Optional list of paths to .env files
        selenium_options: Additional ChromiumOptions configuration
        auto_navigate_to_instagram: If True, automatically navigates to Instagram.com
        verify_login: If True, checks if user is logged in to Instagram
        **manager_kwargs: Additional arguments passed to MultiloginManager

    Returns:
        tuple: (MultiloginManager instance, WebDriver instance)

    Example:
        # Simple usage - everything automatic
        manager, driver = create_instagram_session()

        # Custom options
        manager, driver = create_instagram_session(
            selenium_options={'page_load_strategy': 'eager'},
            auto_navigate_to_instagram=True,
            verify_login=True
        )

        try:
            # Your Instagram automation code here
            # driver is already on Instagram and ready to use!
            posts = driver.find_elements(By.TAG_NAME, "article")
            # ... automation logic ...
        finally:
            manager.cleanup()
    """
    logger.info("🚀 Creating Instagram automation session...")

    # Create manager with custom options
    manager = MultiloginManager(load_env_paths=env_paths, **manager_kwargs)
    manager.signin_multilogin()
    driver = manager.start_profile(selenium_options=selenium_options)

    if auto_navigate_to_instagram:
        logger.info("📱 Navigating to Instagram...")
        driver.get("https://www.instagram.com/")
        time.sleep(3)  # Allow page to load

        if verify_login:
            logger.info("🔍 Verifying Instagram login status...")
            try:
                # Look for common logged-in indicators
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                from selenium.webdriver.common.by import By

                # Check for navigation elements that appear when logged in
                WebDriverWait(driver, 10).until(
                    lambda d: len(d.find_elements(By.XPATH, "//a[contains(@href, '/direct/inbox/')]")) > 0 or
                             len(d.find_elements(By.XPATH, "//a[contains(@href, '/explore/')]")) > 0 or
                             len(d.find_elements(By.XPATH, "//svg[@aria-label='Home']")) > 0
                )
                logger.info("✅ Instagram login verified - ready for automation!")
            except:
                logger.warning("⚠️ Could not verify Instagram login - you may need to log in manually")

    logger.info("🎯 Instagram session ready!")
    return manager, driver

@contextmanager
def instagram_session(env_paths: Optional[list] = None,
                     selenium_options: Optional[dict] = None,
                     auto_navigate_to_instagram: bool = True,
                     verify_login: bool = True,
                     **manager_kwargs):
    """
    Context manager for Instagram sessions - AUTOMATIC CLEANUP!

    This is the SAFEST way to run Instagram automation - cleanup is guaranteed.

    Args:
        Same as create_instagram_session()

    Yields:
        tuple: (MultiloginManager instance, WebDriver instance)

    Example:
        # Automatic cleanup - no try/finally needed!
        with instagram_session() as (manager, driver):
            # Your automation code here
            driver.get("https://www.instagram.com/explore/")
            # ... do your automation ...
        # Profile is automatically stopped and cleaned up here!
    """
    manager, driver = create_instagram_session(
        env_paths=env_paths,
        selenium_options=selenium_options,
        auto_navigate_to_instagram=auto_navigate_to_instagram,
        verify_login=verify_login,
        **manager_kwargs
    )

    try:
        yield manager, driver
    finally:
        logger.info("🧹 Auto-cleanup: Stopping Instagram session...")
        manager.cleanup()

def quick_instagram_test() -> bool:
    """
    Quick test to verify Multilogin and Instagram setup is working.
    Returns True if everything is working correctly.

    Example:
        if quick_instagram_test():
            print("✅ Ready for Instagram automation!")
        else:
            print("❌ Setup needs fixing")
    """
    try:
        logger.info("🧪 Running quick Instagram setup test...")

        with instagram_session(auto_navigate_to_instagram=True, verify_login=False) as (manager, driver):
            # Test 1: Can we reach Instagram?
            current_url = driver.current_url
            if "instagram.com" not in current_url:
                logger.error(f"❌ Failed to navigate to Instagram. Current URL: {current_url}")
                return False

            # Test 2: Page loaded properly?
            page_title = driver.title
            if "Instagram" not in page_title:
                logger.error(f"❌ Instagram page didn't load properly. Title: {page_title}")
                return False

            logger.info("✅ Instagram setup test passed!")
            return True

    except Exception as e:
        logger.error(f"❌ Instagram setup test failed: {str(e)}")
        return False

def get_session_stats(manager: MultiloginManager) -> Dict[str, Any]:
    """
    Get detailed statistics about the current session.

    Args:
        manager: MultiloginManager instance

    Returns:
        Dictionary with session statistics
    """
    return {
        'profile_id': manager.profile_id,
        'profile_active': manager.profile_active,
        'has_driver': manager.driver is not None,
        'has_token': manager.token is not None,
        'session_stats': manager.session_stats.copy(),
        'driver_status': 'active' if manager.driver else 'inactive'
    }

# ==============================================================================
# LEGACY COMPATIBILITY FUNCTIONS
# ==============================================================================
# These functions maintain compatibility with existing script patterns

def signin_multilogin() -> str:
    """
    Legacy compatibility function.
    Creates a temporary manager instance for signin only.
    """
    manager = MultiloginManager()
    return manager.signin_multilogin()

def _start_profile_legacy(self, selenium_options: Optional[dict] = None) -> webdriver.Remote:
        """
        Legacy standalone start_profile — kept for backward compatibility.
        Uses the same v2 API + startup lock as the class method.
        """
        print(f"🚀 Starting profile {self.profile_id} (legacy path)...")

        # Prepare headers with authorization
        auth_headers = HEADERS.copy()
        if self.token:
            auth_headers.update({"Authorization": f"Bearer {self.token}"})

        # Profile start URL - Use v2 API (v1 returns GET_PROXY_CONNECTION_IP_ERROR for proxy-assigned profiles)
        profile_start_url = f"{MLX_LAUNCHER_V2}/profile/f/{self.folder_id}/p/{self.profile_id}/start?automation_type=selenium"
        print(f"🔍 Profile start URL: {profile_start_url}")
        # Try with different request methods for SSL compatibility
        # CRITICAL: Use SSL session with custom context FIRST - this properly disables both
        # certificate verification AND hostname checking (verify=False alone doesn't disable hostname checks in Python 3.11+)
        request_methods = [
            # Method 1: SSL session with custom context (properly disables ALL SSL verification including hostname check)
            lambda: create_ssl_session().get(profile_start_url, headers=auth_headers, timeout=DEFAULT_REQUEST_TIMEOUT),
            # Method 2: Regular requests with verify=False (may still fail on hostname check in Python 3.11+)
            lambda: requests.get(profile_start_url, headers=auth_headers, timeout=DEFAULT_REQUEST_TIMEOUT, verify=False),
            # Method 3: Regular requests (SSL verification enabled) - Last resort (rarely needed)
            lambda: requests.get(profile_start_url, headers=auth_headers, timeout=DEFAULT_REQUEST_TIMEOUT),
        ]

        response = None
        for attempt, request_method in enumerate(request_methods, 1):
            try:
                print(f"🔄 Profile start attempt {attempt}/{len(request_methods)}")

                r = request_method()

                if r.status_code != 200:
                    error_msg = f"\nError while starting profile: {r.text}\n"
                    print(error_msg)

                    # Check if profile is already running
                    if "PROFILE_ALREADY_RUNNING" in r.text:
                        print("⚠️ Profile is already running - attempting to force stop and retry...")
                        try:
                            self.force_stop_profile()
                            # Retry starting the profile
                            print("🔄 Retrying profile start after force stop...")
                            r = request_method()
                            if r.status_code == 200:
                                response = r.json()
                                print(f"✅ Profile {self.profile_id} started successfully after force stop")
                                break
                        except Exception as force_stop_error:
                            print(f"❌ Force stop failed: {force_stop_error}")

                    if attempt == len(request_methods):
                        raise Exception("Failed to start Multilogin profile")
                    continue

                response = r.json()
                print(f"✅ Profile {self.profile_id} started successfully")
                break

            except (requests.exceptions.SSLError, ssl.SSLError) as ssl_error:
                print(f"⚠️ SSL error on profile start attempt {attempt}: {str(ssl_error)[:100]}")
                if attempt < len(request_methods):
                    print(f"🔄 Trying alternative SSL method for profile start...")
                    continue
                else:
                    print("❌ All SSL methods failed for profile start")
                    self._print_ssl_troubleshooting()
                    raise Exception(f"Profile start SSL connection failed after {len(request_methods)} attempts: {str(ssl_error)}")

            except Exception as e:
                print(f"⚠️ General error on profile start attempt {attempt}: {str(e)}")
                if attempt < len(request_methods):
                    continue
                else:
                    print(f"❌ Profile start failed after {len(request_methods)} attempts")
                    raise

        if not response:
            raise Exception("Failed to get valid response from profile start")

        # Handle different response structures
        print(f"🔍 Debug: Profile start response keys: {response.keys()}")
        print(f"🔍 Debug: Full response: {response}")

        # Try to extract port from different possible response structures
        selenium_port = None

        # Format 1: {"data": {"port": 12345}} - API may return port as int or str
        if "data" in response and isinstance(response["data"], dict) and "port" in response["data"]:
            raw = response["data"]["port"]
            selenium_port = int(raw) if not isinstance(raw, int) else raw
            print(f"✅ Extracted port from response['data']['port']: {selenium_port}")

        # Format 2: {"port": 12345}
        elif "port" in response:
            raw = response["port"]
            selenium_port = int(raw) if not isinstance(raw, int) else raw
            print(f"✅ Extracted port from response['port']: {selenium_port}")

        # Format 3: {"status": {"message": "12345"}} - Port is in status.message as string
        elif "status" in response and isinstance(response["status"], dict):
            if "message" in response["status"] and response["status"]["message"]:
                try:
                    # Port is returned as a string in status.message
                    selenium_port = int(response["status"]["message"])
                    print(f"✅ Extracted port from response['status']['message']: {selenium_port}")
                except (ValueError, TypeError) as e:
                    print(f"❌ Failed to parse port from status.message: {response['status']['message']}")
                    raise Exception(f"Port in status.message is not a valid integer: {response['status']['message']}")

        # No valid port found
        if selenium_port is None:
            print(f"❌ Error: Could not extract port from response: {response}")
            raise Exception(f"Profile started but port not found in any known response format. Response: {str(response)[:300]}")

        # Set up ChromiumOptions with CPU optimizations (50-70% CPU savings)
        options = get_campaign_chrome_options()
        options.page_load_strategy = 'normal'

        # Apply additional options if provided (merge with optimizations)
        if selenium_options:
            for key, value in selenium_options.items():
                if hasattr(options, key):
                    setattr(options, key, value)
                else:
                    print(f"⚠️ Warning: Unknown ChromiumOption: {key}")

        # Create WebDriver instance with retry logic and better error handling
        max_driver_attempts = 3
        driver = None

        for driver_attempt in range(max_driver_attempts):
            try:
                if driver_attempt > 0:
                    print(f"🔄 Retrying WebDriver connection (attempt {driver_attempt + 1}/{max_driver_attempts})...")
                    # Longer wait between retries for browser to stabilize
                    time.sleep(15)

                print(f"🔌 Connecting to WebDriver at {LOCALHOST}:{selenium_port}...")
                driver = _create_remote_driver_with_options_fallback(
                    command_executor=f"{LOCALHOST}:{selenium_port}",
                    options=options,
                )

                # Set timeouts BEFORE testing the driver
                try:
                    pl = default_page_load_timeout_seconds()
                    driver.set_page_load_timeout(pl)
                    driver.implicitly_wait(15)  # Increased from 10 to 15
                    apply_remote_http_read_timeout(driver)
                    print("✅ WebDriver timeouts configured")
                except Exception as timeout_error:
                    print(f"⚠️ Warning: Could not set WebDriver timeouts: {str(timeout_error)}")

                # Give browser extra time to fully initialize before testing
                print("⏳ Waiting for browser to fully initialize...")
                time.sleep(5)  # Wait for browser renderer to be ready

                # Test the driver connection and ensure window is available
                try:
                    print("🧪 Testing driver connection...")

                    # Check if we have any window handles
                    handles = driver.window_handles
                    if not handles or len(handles) == 0:
                        raise Exception("No browser window available - window may have closed")

                    print(f"✅ Driver connection test passed - {len(handles)} window(s) available")

                    # Switch to the first window to ensure we're focused on it
                    driver.switch_to.window(handles[0])
                    print(f"✅ Switched to window: {handles[0][:16]}...")

                    # Additional verification - try to get current_url (should be blank or data:)
                    try:
                        current_url = driver.current_url
                        print(f"✅ Window is active - URL: {current_url[:50]}...")
                    except Exception as url_error:
                        print(f"⚠️ Could not get current URL (may be normal): {str(url_error)[:50]}")

                    break  # Success - exit retry loop

                except Exception as test_error:
                    print(f"❌ Driver connection test failed: {str(test_error)[:100]}")
                    if driver:
                        try:
                            driver.quit()
                        except:
                            pass
                    driver = None
                    if driver_attempt < max_driver_attempts - 1:
                        print(f"🔄 Will retry driver connection...")
                        continue
                    else:
                        raise test_error

            except WebDriverException as wd_error:
                error_msg = str(wd_error)
                if "timeout" in error_msg.lower():
                    print(f"⏱️ WebDriver timeout on attempt {driver_attempt + 1}")
                elif "renderer" in error_msg.lower():
                    print(f"⏱️ Chrome renderer not responding on attempt {driver_attempt + 1}")
                else:
                    print(f"❌ WebDriver error on attempt {driver_attempt + 1}: {error_msg[:100]}")

                if driver_attempt < max_driver_attempts - 1:
                    print("🔄 Retrying after delay...")
                    time.sleep(15)  # Longer delay for renderer issues
                    continue
                else:
                    raise Exception(f"Failed to create WebDriver after {max_driver_attempts} attempts: {error_msg[:200]}")

            except Exception as e:
                print(f"❌ Unexpected error on attempt {driver_attempt + 1}: {str(e)[:100]}")
                if driver_attempt < max_driver_attempts - 1:
                    time.sleep(15)
                    continue
                else:
                    raise

        if not driver:
            raise Exception("Failed to create WebDriver instance after all attempts")

        self.driver = driver
        self.profile_active = True

        print(f"⏱️ Profile started — sleeping {_PROFILE_START_DELAY_SEC}s (startup stagger)")
        time.sleep(_PROFILE_START_DELAY_SEC)

        return driver

def stop_profile() -> None:
    """
    Legacy compatibility function.
    Creates a temporary manager instance for profile stop only.
    """
    manager = MultiloginManager()
    manager.stop_profile()


# quick_instagram_test()
