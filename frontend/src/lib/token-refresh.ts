"use client";

/**
 * Proactive token refresh scheduler.
 *
 * Refreshes access token in the background before it expires (at 80% of lifetime).
 * This prevents users from experiencing 401 errors during normal usage.
 */

// Refresh at 12 minutes (80% of 15-minute access token lifetime)
const REFRESH_INTERVAL_MS = 12 * 60 * 1000; // 12 minutes

let refreshIntervalId: NodeJS.Timeout | null = null;

/**
 * Start proactive token refresh scheduler.
 * Runs every 12 minutes to refresh tokens before they expire.
 */
export function startProactiveRefresh(): void {
  // Clear any existing interval
  if (refreshIntervalId) {
    clearInterval(refreshIntervalId);
  }

  // Set up interval to refresh token proactively
  refreshIntervalId = setInterval(async () => {
    try {
      const response = await fetch("/api/auth/refresh", {
        method: "POST",
        credentials: "include",
      });

      if (!response.ok) {
        // Silent fail - reactive refresh will handle it on next API call
        console.debug("Proactive token refresh failed, will retry on next API call");
      }
    } catch (error) {
      // Silent fail - don't disrupt user experience
      console.debug("Proactive token refresh error:", error);
    }
  }, REFRESH_INTERVAL_MS);

  console.debug(`Proactive token refresh started (interval: ${REFRESH_INTERVAL_MS / 1000}s)`);
}

/**
 * Stop proactive token refresh scheduler.
 * Call this on logout or when user navigates away from authenticated area.
 */
export function stopProactiveRefresh(): void {
  if (refreshIntervalId) {
    clearInterval(refreshIntervalId);
    refreshIntervalId = null;
    console.debug("Proactive token refresh stopped");
  }
}

/**
 * Check if proactive refresh is currently running.
 */
export function isProactiveRefreshActive(): boolean {
  return refreshIntervalId !== null;
}
