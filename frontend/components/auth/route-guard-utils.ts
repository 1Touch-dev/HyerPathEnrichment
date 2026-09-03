export function redirectAfterDomContentLoaded(redirect: () => void): () => void {
  const navigationTiming = performance.getEntriesByType?.("navigation")[0] as
    PerformanceNavigationTiming | undefined;
  const domContentLoaded =
    document.readyState === "complete" || (navigationTiming?.domContentLoadedEventEnd ?? 0) > 0;

  if (domContentLoaded) {
    redirect();
    return () => undefined;
  }

  document.addEventListener("DOMContentLoaded", redirect, { once: true });
  return () => document.removeEventListener("DOMContentLoaded", redirect);
}
