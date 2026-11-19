"use client";

import { useEffect, useRef, useState } from "react";
import { WS_BASE_URL } from "@/lib/api";
import type { LiveWsEvent } from "@/types/api";

export type WsStatus = "connecting" | "connected" | "disconnected";

export function useResultWebSocket(
  accessToken: string | null,
  onEvent?: (event: LiveWsEvent) => void
) {
  const [status, setStatus] = useState<WsStatus>("disconnected");
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    if (!accessToken) {
      setStatus("disconnected");
      return;
    }

    let ws: WebSocket | null = null;
    let heartbeatTimer: ReturnType<typeof setInterval> | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let unmounted = false;

    const connect = () => {
      if (unmounted) return;
      setStatus("connecting");
      const url = `${WS_BASE_URL}/results?token=${encodeURIComponent(accessToken)}`;
      ws = new WebSocket(url);

      ws.onopen = () => {
        if (unmounted) return;
        setStatus("connected");
        heartbeatTimer = setInterval(() => {
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send("ping");
          }
        }, 25000);
      };

      ws.onmessage = (msg) => {
        try {
          const parsed = JSON.parse(msg.data) as LiveWsEvent;
          onEventRef.current?.(parsed);
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = () => {
        if (heartbeatTimer) clearInterval(heartbeatTimer);
        if (unmounted) return;
        setStatus("disconnected");
        reconnectTimer = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws?.close();
      };
    };

    connect();

    return () => {
      unmounted = true;
      if (heartbeatTimer) clearInterval(heartbeatTimer);
      if (reconnectTimer) clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [accessToken]);

  return { status };
}
