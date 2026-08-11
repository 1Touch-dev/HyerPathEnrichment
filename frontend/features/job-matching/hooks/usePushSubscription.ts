"use client";

import { useCallback, useState } from "react";
import { subscribeToPush, unsubscribeFromPush } from "../api/client";

/**
 * Push API's `applicationServerKey` requires a raw `Uint8Array`, but VAPID
 * public keys are distributed as base64url strings — this is the standard
 * conversion (see MDN's push notification guides).
 */
function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(new ArrayBuffer(rawData.length));
  for (let i = 0; i < rawData.length; i++) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

function isPushSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    "Notification" in window &&
    "serviceWorker" in navigator &&
    "PushManager" in window
  );
}

/**
 * Manages the browser push subscription lifecycle (permission → service
 * worker registration → PushManager subscription → BFF sync). This is an
 * imperative browser-API flow, not a data fetch, so it's plain state rather
 * than a React Query hook — mirrors `useUnreadMatchEvents`'s approach to
 * browser-API-backed hooks in this feature.
 */
export function usePushSubscription() {
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isSupported = isPushSupported();

  const subscribe = useCallback(async () => {
    setError(null);

    if (!isPushSupported()) {
      const message = "Push notifications are not supported in this browser.";
      setError(message);
      throw new Error(message);
    }

    try {
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        throw new Error("Notification permission was denied.");
      }

      const vapidPublicKey = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY;
      if (!vapidPublicKey) {
        throw new Error("Push notifications are not configured.");
      }

      const registration = await navigator.serviceWorker.register("/sw.js");
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
      });

      const json = subscription.toJSON();
      if (!json.endpoint || !json.keys?.p256dh || !json.keys?.auth) {
        throw new Error("Push subscription is missing required fields.");
      }

      await subscribeToPush({
        endpoint: json.endpoint,
        p256dh: json.keys.p256dh,
        auth: json.keys.auth,
      });
      setIsSubscribed(true);
    } catch (err) {
      setIsSubscribed(false);
      const message =
        err instanceof Error ? err.message : "Failed to subscribe to push notifications.";
      setError(message);
      throw err instanceof Error ? err : new Error(message);
    }
  }, []);

  const unsubscribe = useCallback(async () => {
    setError(null);

    if (!isPushSupported()) {
      setIsSubscribed(false);
      return;
    }

    try {
      const registration = await navigator.serviceWorker.getRegistration("/sw.js");
      const subscription = await registration?.pushManager.getSubscription();

      if (subscription) {
        const endpoint = subscription.endpoint;
        await subscription.unsubscribe();
        await unsubscribeFromPush(endpoint);
      }
      setIsSubscribed(false);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to unsubscribe from push notifications.";
      setError(message);
      throw err instanceof Error ? err : new Error(message);
    }
  }, []);

  return { isSupported, isSubscribed, subscribe, unsubscribe, error };
}
