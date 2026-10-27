// Browser push subscription helper (VAPID).

function urlBase64ToUint8Array(base64) {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(b64);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

export async function registerAndSubscribe() {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return { enabled: false };
  const reg = await navigator.serviceWorker.register("/sw.js");
  const keyResp = await fetch("/api/notifications/vapid-public-key", { credentials: "include" });
  const { public_key, enabled } = await keyResp.json();
  if (!enabled || !public_key) return { enabled: false };

  const existing = await reg.pushManager.getSubscription();
  if (existing) return { enabled: true, subscription: existing };

  const subscription = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(public_key),
  });

  await fetch("/api/notifications/push-subscribe", {
    method: "POST",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      endpoint: subscription.endpoint,
      keys: subscription.toJSON().keys,
    }),
  });
  return { enabled: true, subscription };
}

export async function unsubscribe() {
  if (!("serviceWorker" in navigator)) return;
  const reg = await navigator.serviceWorker.ready;
  const sub = await reg.pushManager.getSubscription();
  if (sub) {
    await fetch("/api/notifications/push-unsubscribe", {
      method: "POST",
      credentials: "include",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ endpoint: sub.endpoint, keys: sub.toJSON().keys }),
    });
    await sub.unsubscribe();
  }
}
