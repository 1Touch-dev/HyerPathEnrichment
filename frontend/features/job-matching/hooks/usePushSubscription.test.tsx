import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { usePushSubscription } from "./usePushSubscription";
import * as client from "../api/client";

const ORIGINAL_ENV = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY;

/**
 * No existing test in this repo mocks the Push API / service worker (there's
 * no precedent in this codebase for it), so these are minimal fakes covering
 * only what usePushSubscription touches: Notification.requestPermission,
 * navigator.serviceWorker.register/getRegistration, and
 * registration.pushManager.subscribe/getSubscription.
 */
function makeFakeSubscription(overrides: Partial<PushSubscriptionJSON> = {}) {
  return {
    endpoint: "https://push.example.com/abc",
    toJSON: () => ({
      endpoint: "https://push.example.com/abc",
      keys: { p256dh: "p256dh-key", auth: "auth-key" },
      ...overrides,
    }),
    unsubscribe: vi.fn().mockResolvedValue(true),
  };
}

function installPushSupport() {
  const fakeSubscription = makeFakeSubscription();
  const subscribe = vi.fn().mockResolvedValue(fakeSubscription);
  const getSubscription = vi.fn().mockResolvedValue(fakeSubscription);
  const registration = {
    pushManager: { subscribe, getSubscription },
  };
  const register = vi.fn().mockResolvedValue(registration);
  const getRegistration = vi.fn().mockResolvedValue(registration);
  const requestPermission = vi.fn().mockResolvedValue("granted");

  vi.stubGlobal("Notification", { requestPermission });
  vi.stubGlobal("PushManager", class {});
  Object.defineProperty(window.navigator, "serviceWorker", {
    value: { register, getRegistration },
    configurable: true,
  });

  return {
    fakeSubscription,
    subscribe,
    getSubscription,
    register,
    getRegistration,
    requestPermission,
  };
}

beforeEach(() => {
  process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY = "dGVzdC12YXBpZC1rZXk"; // base64url, no padding needed
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY = ORIGINAL_ENV;
});

describe("usePushSubscription", () => {
  it("reports unsupported when Notification/serviceWorker/PushManager are missing", () => {
    vi.stubGlobal("Notification", undefined);
    vi.stubGlobal("PushManager", undefined);

    const { result } = renderHook(() => usePushSubscription());

    expect(result.current.isSupported).toBe(false);
  });

  it("subscribes successfully and posts the subscription to the BFF", async () => {
    const mocks = installPushSupport();
    const subscribeSpy = vi.spyOn(client, "subscribeToPush").mockResolvedValue(undefined);

    const { result } = renderHook(() => usePushSubscription());
    expect(result.current.isSupported).toBe(true);

    await act(async () => {
      await result.current.subscribe();
    });

    expect(mocks.requestPermission).toHaveBeenCalled();
    expect(mocks.register).toHaveBeenCalledWith("/sw.js");
    expect(mocks.subscribe).toHaveBeenCalledWith(
      expect.objectContaining({
        userVisibleOnly: true,
        applicationServerKey: expect.any(Uint8Array),
      }),
    );
    expect(subscribeSpy).toHaveBeenCalledWith({
      endpoint: "https://push.example.com/abc",
      p256dh: "p256dh-key",
      auth: "auth-key",
    });

    await waitFor(() => expect(result.current.isSubscribed).toBe(true));
    expect(result.current.error).toBeNull();
  });

  it("surfaces an error and does not call the BFF when permission is denied", async () => {
    const mocks = installPushSupport();
    mocks.requestPermission.mockResolvedValue("denied");
    const subscribeSpy = vi.spyOn(client, "subscribeToPush").mockResolvedValue(undefined);

    const { result } = renderHook(() => usePushSubscription());

    await act(async () => {
      await expect(result.current.subscribe()).rejects.toThrow();
    });

    expect(subscribeSpy).not.toHaveBeenCalled();
    await waitFor(() => expect(result.current.error).toBe("Notification permission was denied."));
    expect(result.current.isSubscribed).toBe(false);
  });

  it("unsubscribes and calls the BFF DELETE with the existing endpoint", async () => {
    const mocks = installPushSupport();
    vi.spyOn(client, "subscribeToPush").mockResolvedValue(undefined);
    const unsubscribeSpy = vi.spyOn(client, "unsubscribeFromPush").mockResolvedValue(undefined);

    const { result } = renderHook(() => usePushSubscription());

    await act(async () => {
      await result.current.subscribe();
    });
    await waitFor(() => expect(result.current.isSubscribed).toBe(true));

    await act(async () => {
      await result.current.unsubscribe();
    });

    expect(mocks.getRegistration).toHaveBeenCalledWith("/sw.js");
    expect(mocks.getSubscription).toHaveBeenCalled();
    expect(unsubscribeSpy).toHaveBeenCalledWith("https://push.example.com/abc");
    await waitFor(() => expect(result.current.isSubscribed).toBe(false));
  });
});
