"use client";

import { useEffect, useRef, useState } from "react";
import { getStoredAccessToken, WS_BASE_URL } from "@/lib/api";
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
    let retryDelayMs = 3000;

    const connect = () => {
      if (unmounted) return;
      // Always read the latest token from storage on reconnect (P1-8 fix)
      const liveToken = getStoredAccessToken() || accessToken;
      if (!liveToken) {
        setStatus("disconnected");
        return;
      }

      setStatus("connecting");
      const url = `${WS_BASE_URL}/results?token=${encodeURIComponent(liveToken)}`;
      ws = new WebSocket(url);

      ws.onopen = () => {
        if (unmounted) return;
        retryDelayMs = 3000;
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

      ws.onclose = (ev) => {
        if (heartbeatTimer) clearInterval(heartbeatTimer);
        if (unmounted) return;
        setStatus("disconnected");
        // Stop tight retry loop if server rejected token with 1008 until token refreshes
        if (ev.code === 1008) {
          retryDelayMs = Math.min(retryDelayMs * 2, 30000);
        }
        reconnectTimer = setTimeout(connect, retryDelayMs);
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
