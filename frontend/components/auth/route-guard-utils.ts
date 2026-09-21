export function redirectAfterDomContentLoaded(redirect: () => void): () => void {
  if (document.readyState !== "loading") {
    redirect();
    return () => undefined;
  }

  document.addEventListener("DOMContentLoaded", redirect, { once: true });
  return () => document.removeEventListener("DOMContentLoaded", redirect);
}
