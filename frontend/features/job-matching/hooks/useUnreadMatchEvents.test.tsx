import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useUnreadMatchEvents } from "./useUnreadMatchEvents";

/**
 * No existing test in this repo mocks EventSource (useJobEvents and
 * enrich-events.ts have no co-located tests today), so this is a minimal fake
 * that records the most recently created instance for the test to drive
 * `.onmessage`/`.onerror` manually.
 */
class FakeEventSource {
  static instances: FakeEventSource[] = [];
  url: string;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  closed = false;

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  close() {
    this.closed = true;
  }
}

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

describe("useUnreadMatchEvents", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("opens an EventSource against the job-matching events BFF route", () => {
    renderHook(() => useUnreadMatchEvents(), { wrapper });
    expect(FakeEventSource.instances).toHaveLength(1);
    expect(FakeEventSource.instances[0].url).toBe("/api/job-matching/events");
  });

  it("parses unread_count messages and updates state", async () => {
    const { result } = renderHook(() => useUnreadMatchEvents(), { wrapper });
    const instance = FakeEventSource.instances[0];

    act(() => {
      instance.onmessage?.({ data: JSON.stringify({ unread_count: 3 }) } as MessageEvent<string>);
    });

    await waitFor(() => expect(result.current.unreadCount).toBe(3));
  });

  it("closes the EventSource on unmount", () => {
    const { unmount } = renderHook(() => useUnreadMatchEvents(), { wrapper });
    const instance = FakeEventSource.instances[0];
    unmount();
    expect(instance.closed).toBe(true);
  });

  it("reconnects after an error by opening a new EventSource", async () => {
    vi.useFakeTimers();
    renderHook(() => useUnreadMatchEvents(), { wrapper });
    const instance = FakeEventSource.instances[0];

    act(() => {
      instance.onerror?.(new Event("error"));
    });
    expect(instance.closed).toBe(true);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    expect(FakeEventSource.instances.length).toBeGreaterThan(1);
    vi.useRealTimers();
  });

  it("does not open a connection when disabled", () => {
    renderHook(() => useUnreadMatchEvents(false), { wrapper });
    expect(FakeEventSource.instances).toHaveLength(0);
  });
});
