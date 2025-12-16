"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { API_CONFIG, LogEntry } from "@/lib/api";

interface UseLogsOptions {
  missionId: string;
  live?: boolean;
  maxLogs?: number;
}

interface LogsState {
  logs: LogEntry[];
  loading: boolean;
  error: string | null;
  connected: boolean;
}

export function useLogs({ missionId, live = true, maxLogs = 500 }: UseLogsOptions) {
  const [state, setState] = useState<LogsState>({
    logs: [],
    loading: true,
    error: null,
    connected: false,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Add a log entry
  const addLog = useCallback(
    (log: LogEntry) => {
      setState((prev) => {
        const newLogs = [...prev.logs, log];
        // Keep only the last maxLogs entries
        if (newLogs.length > maxLogs) {
          newLogs.splice(0, newLogs.length - maxLogs);
        }
        return { ...prev, logs: newLogs };
      });
    },
    [maxLogs]
  );

  // Clear logs
  const clearLogs = useCallback(() => {
    setState((prev) => ({ ...prev, logs: [] }));
  }, []);

  // Connect to WebSocket for real-time logs
  const connectWebSocket = useCallback(() => {
    if (!missionId || !live) return;

    const wsUrl = `${API_CONFIG.ORCHESTRATOR_WS}/ws/logs/${missionId}`;

    try {
      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        console.log("[LogsWS] Connected to", wsUrl);
        setState((prev) => ({ ...prev, connected: true, loading: false }));
      };

      wsRef.current.onmessage = (event) => {
        try {
          const log = JSON.parse(event.data) as LogEntry;

          // Skip keepalive messages
          if ((log as unknown as { type?: string }).type === "keepalive") {
            return;
          }

          addLog(log);
        } catch (err) {
          console.error("[LogsWS] Parse error:", err);
        }
      };

      wsRef.current.onerror = (err) => {
        console.error("[LogsWS] Error:", err);
        setState((prev) => ({ ...prev, error: "WebSocket error" }));
      };

      wsRef.current.onclose = () => {
        console.log("[LogsWS] Disconnected");
        setState((prev) => ({ ...prev, connected: false }));

        // Reconnect after 3 seconds
        reconnectTimeoutRef.current = setTimeout(() => {
          connectWebSocket();
        }, 3000);
      };
    } catch (err) {
      console.error("[LogsWS] Connection failed:", err);
      setState((prev) => ({ ...prev, loading: false, error: "Connection failed" }));
    }
  }, [missionId, live, addLog]);

  // Alternative: Use SSE instead of WebSocket
  const connectSSE = useCallback(() => {
    if (!missionId || !live) return;

    const sseUrl = `${API_CONFIG.ORCHESTRATOR_WS.replace("ws://", "http://").replace("wss://", "https://")}/api/v1/sse/logs/${missionId}`;

    const eventSource = new EventSource(sseUrl);

    eventSource.onopen = () => {
      console.log("[LogsSSE] Connected to", sseUrl);
      setState((prev) => ({ ...prev, connected: true, loading: false }));
    };

    eventSource.onmessage = (event) => {
      try {
        const log = JSON.parse(event.data) as LogEntry;

        // Skip keepalive messages
        if ((log as unknown as { type?: string }).type === "keepalive") {
          return;
        }

        addLog(log);
      } catch (err) {
        console.error("[LogsSSE] Parse error:", err);
      }
    };

    eventSource.onerror = () => {
      console.error("[LogsSSE] Error");
      setState((prev) => ({ ...prev, connected: false }));
      eventSource.close();

      // Reconnect after 3 seconds
      reconnectTimeoutRef.current = setTimeout(() => {
        connectSSE();
      }, 3000);
    };

    return () => {
      eventSource.close();
    };
  }, [missionId, live, addLog]);

  // Initialize
  useEffect(() => {
    if (live) {
      connectWebSocket();
    } else {
      setState((prev) => ({ ...prev, loading: false }));
    }

    return () => {
      wsRef.current?.close();
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [connectWebSocket, live]);

  return {
    logs: state.logs,
    loading: state.loading,
    error: state.error,
    connected: state.connected,
    clearLogs,
  };
}

// Helper to format log level for UI
export function getLogLevelStyle(level: LogEntry["level"]) {
  const styles: Record<string, { color: string; prefix: string; bgColor: string }> = {
    DEBUG: { color: "text-purple-400", prefix: "[~]", bgColor: "bg-purple-500/10" },
    INFO: { color: "text-cyan-400", prefix: "[*]", bgColor: "bg-cyan-500/10" },
    WARNING: { color: "text-orange-400", prefix: "[!]", bgColor: "bg-orange-500/10" },
    ERROR: { color: "text-red-400", prefix: "[X]", bgColor: "bg-red-500/10" },
  };
  return styles[level] || styles.INFO;
}

export default useLogs;
