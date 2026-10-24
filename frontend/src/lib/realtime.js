// Realtime WebSocket helper.

let socket = null;
let socketPromise = null;
const listeners = new Set();

async function getTicket() {
  const res = await fetch("/api/auth/ws-ticket", { method: "POST", credentials: "include" });
  if (!res.ok) throw new Error("no ticket");
  return (await res.json()).ticket;
}

export async function connectRealtime() {
  if (socket && socket.readyState === WebSocket.OPEN) return socket;
  if (socketPromise) return socketPromise;

  socketPromise = (async () => {
    const ticket = await getTicket();
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${proto}//${window.location.host}/api/ws?token=${ticket}`;
    socket = new WebSocket(url);
    await new Promise((resolve, reject) => {
      socket.onopen = resolve;
      socket.onerror = reject;
    });
    socket.onmessage = (e) => {
      let data;
      try {
        data = JSON.parse(e.data);
      } catch {
        return;
      }
      listeners.forEach((fn) => fn(data));
    };
    socket.onclose = () => {
      socket = null;
      socketPromise = null;
    };
    return socket;
  })();

  socketPromise.finally(() => {
    socketPromise = null;
  });
  return socketPromise;
}

export function subscribeRoom(room) {
  socket?.send(JSON.stringify({ type: "subscribe", rooms: [room] }));
}

export function sendEvent(room, event) {
  socket?.send(JSON.stringify({ type: "event", room, event }));
}

export function onEvent(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
