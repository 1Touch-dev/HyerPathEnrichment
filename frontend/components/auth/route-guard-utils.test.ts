import { afterEach, describe, expect, it, vi } from "vitest";
import { redirectAfterDomContentLoaded } from "./route-guard-utils";

const originalReadyState = document.readyState;

function setReadyState(readyState: DocumentReadyState) {
  Object.defineProperty(document, "readyState", {
    configurable: true,
    get: () => readyState,
  });
}

afterEach(() => {
  Object.defineProperty(document, "readyState", {
    configurable: true,
    get: () => originalReadyState,
  });
});

describe("redirectAfterDomContentLoaded", () => {
  it("redirects immediately once the document is already interactive", () => {
    setReadyState("interactive");
    const redirect = vi.fn();

    const cleanup = redirectAfterDomContentLoaded(redirect);

    expect(redirect).toHaveBeenCalledTimes(1);
    cleanup();
  });

  it("waits for DOMContentLoaded while the document is still loading", () => {
    setReadyState("loading");
    const redirect = vi.fn();

    redirectAfterDomContentLoaded(redirect);
    expect(redirect).not.toHaveBeenCalled();

    document.dispatchEvent(new Event("DOMContentLoaded"));
    expect(redirect).toHaveBeenCalledTimes(1);
  });
});
