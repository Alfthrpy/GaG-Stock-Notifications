import { useEffect, useRef, useState } from "react";
import type { ServerPrediction, ServersPayload } from "../types";

interface Snapshot {
  servers: ServerPrediction[];
  status: ServersPayload["status"];
  receivedAt: number;
}

const RECONNECT_DELAY_MS = 3000;

export function useServerFeed(wsUrl: string) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;

    function connect() {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);

      ws.onclose = () => {
        setConnected(false);
        if (!cancelled) {
          reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS);
        }
      };

      ws.onerror = () => {
        ws.close();
      };

      ws.onmessage = (event) => {
        const payload = JSON.parse(event.data) as ServersPayload;
        setSnapshot({ servers: payload.servers, status: payload.status, receivedAt: Date.now() });
      };
    }

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      wsRef.current?.close();
    };
  }, [wsUrl]);

  return { snapshot, connected };
}
