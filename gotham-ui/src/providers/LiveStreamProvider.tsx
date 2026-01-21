"use client";

/**
 * LiveStreamProvider
 * Manages real-time event streaming with buffered queue for smooth animations.
 * Also supports loading historical data for completed missions.
 * NO MOCK DATA - all events come from the Python backend via SSE or historical API.
 */

import React, {
  createContext,
  useContext,
  useCallback,
  useEffect,
  useRef,
  useState,
  useMemo,
} from "react";
import { useWorkflowStore } from "@/stores/workflowStore";
import { ServiceConfig } from "@/services/config";
import { WorkflowEvent, NodeType, MissionPhase } from "@/services/types";

// Event queue item with metadata
interface QueuedEvent {
  id: string;
  event: WorkflowEvent;
  receivedAt: number;
  processedAt?: number;
}

// Connection status
export type StreamStatus = "disconnected" | "connecting" | "connected" | "error" | "reconnecting" | "historical";

// Context value
interface LiveStreamContextValue {
  // Status
  status: StreamStatus;
  isLive: boolean;
  isPaused: boolean;
  isHistorical: boolean;

  // Queue metrics
  queueLength: number;
  processedCount: number;
  eventsPerSecond: number;

  // Controls
  connect: (missionId: string) => void;
  disconnect: () => void;
  pause: () => void;
  resume: () => void;
  setProcessingDelay: (ms: number) => void;
  loadHistoricalData: (missionId: string) => Promise<void>;

  // Current mission
  missionId: string | null;
}

const LiveStreamContext = createContext<LiveStreamContextValue | null>(null);

// Default processing delay (ms between events for smooth animation)
const DEFAULT_PROCESSING_DELAY = 150;
const MIN_PROCESSING_DELAY = 50;
const MAX_PROCESSING_DELAY = 1000;

interface LiveStreamProviderProps {
  children: React.ReactNode;
  initialDelay?: number;
}

export function LiveStreamProvider({
  children,
  initialDelay = DEFAULT_PROCESSING_DELAY,
}: LiveStreamProviderProps) {
  // State
  const [status, setStatus] = useState<StreamStatus>("disconnected");
  const [isPaused, setIsPaused] = useState(false);
  const [isHistorical, setIsHistorical] = useState(false);
  const [missionId, setMissionId] = useState<string | null>(null);
  const [queueLength, setQueueLength] = useState(0);
  const [processedCount, setProcessedCount] = useState(0);
  const [eventsPerSecond, setEventsPerSecond] = useState(0);

  // Refs for event queue and processing
  const eventQueueRef = useRef<QueuedEvent[]>([]);
  const eventSourceRef = useRef<EventSource | null>(null);
  const processingTimerRef = useRef<NodeJS.Timeout | null>(null);
  const processingDelayRef = useRef(initialDelay);
  const isProcessingRef = useRef(false);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const eventCountRef = useRef<number[]>([]);

  // Store actions
  const handleEvent = useWorkflowStore((state) => state.handleEvent);
  const setConnectionStatus = useWorkflowStore((state) => state.setConnectionStatus);
  const addAgentRun = useWorkflowStore((state) => state.addAgentRun);
  const addToolCall = useWorkflowStore((state) => state.addToolCall);
  const reset = useWorkflowStore((state) => state.reset);
  const forceCompleteAll = useWorkflowStore((state) => state.forceCompleteAll);

  // Calculate events per second
  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now();
      const oneSecondAgo = now - 1000;

      // Remove old timestamps
      eventCountRef.current = eventCountRef.current.filter(t => t > oneSecondAgo);
      setEventsPerSecond(eventCountRef.current.length);
    }, 500);

    return () => clearInterval(interval);
  }, []);

  // Process next event from queue
  const processNextEvent = useCallback(() => {
    if (isPaused || isProcessingRef.current) return;
    if (eventQueueRef.current.length === 0) {
      isProcessingRef.current = false;
      return;
    }

    isProcessingRef.current = true;

    // Get next event
    const queuedEvent = eventQueueRef.current.shift();
    if (!queuedEvent) {
      isProcessingRef.current = false;
      return;
    }

    // Process event
    queuedEvent.processedAt = Date.now();

    try {
      handleEvent(queuedEvent.event);
      setProcessedCount((c) => c + 1);
      eventCountRef.current.push(Date.now());
    } catch (error) {
      console.error("[LiveStream] Error processing event:", error);
    }

    // Update queue length
    setQueueLength(eventQueueRef.current.length);

    // Schedule next processing
    isProcessingRef.current = false;
    if (eventQueueRef.current.length > 0) {
      processingTimerRef.current = setTimeout(
        processNextEvent,
        processingDelayRef.current
      );
    }
  }, [isPaused, handleEvent]);

  // Add event to queue
  const enqueueEvent = useCallback((event: WorkflowEvent) => {
    const queuedEvent: QueuedEvent = {
      id: `${event.type}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      event,
      receivedAt: Date.now(),
    };

    eventQueueRef.current.push(queuedEvent);
    setQueueLength(eventQueueRef.current.length);

    // Start processing if not already
    if (!isProcessingRef.current && !isPaused) {
      processNextEvent();
    }
  }, [isPaused, processNextEvent]);

  // P0.5-FIX: Track last received SSE event ID for reconnection
  const lastEventIdRef = useRef<string | null>(null);

  // Connect to SSE endpoint
  const connect = useCallback((newMissionId: string, isReconnect: boolean = false) => {
    // Disconnect existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    // Clear reconnect timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    // Clear queue (but not lastEventId on reconnect)
    if (!isReconnect) {
      eventQueueRef.current = [];
      setQueueLength(0);
      setProcessedCount(0);
      reconnectAttemptRef.current = 0;
      lastEventIdRef.current = null;  // Reset only on fresh connect
      reset(); // Reset workflow store for fresh connection
    }

    // Reset historical mode when connecting to live stream
    setIsHistorical(false);

    setMissionId(newMissionId);
    setStatus("connecting");
    setConnectionStatus("connecting");

    // P0.5-FIX: Build SSE URL with lastEventId for reconnection
    let sseUrl = `${ServiceConfig.BFF_GATEWAY}/api/v1/sse/events/${newMissionId}`;
    if (isReconnect && lastEventIdRef.current) {
      sseUrl += `?lastEventId=${encodeURIComponent(lastEventIdRef.current)}`;
      console.log("[LiveStream] Reconnecting with lastEventId:", lastEventIdRef.current);
    }
    console.log("[LiveStream] Connecting to:", sseUrl);

    try {
      const eventSource = new EventSource(sseUrl);
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        console.log("[LiveStream] Connected");
        setStatus("connected");
        setConnectionStatus("connected");
        reconnectAttemptRef.current = 0;
      };

      eventSource.onmessage = (messageEvent) => {
        try {
          // P0.5-FIX: Track last event ID for reconnection
          if (messageEvent.lastEventId) {
            lastEventIdRef.current = messageEvent.lastEventId;
          }

          const data = JSON.parse(messageEvent.data);

          // Also check sse_event_id in data
          if (data.sse_event_id) {
            lastEventIdRef.current = data.sse_event_id;
          }

          // Skip keepalive messages
          if (data.type === "keepalive") return;

          // Create workflow event
          const workflowEvent: WorkflowEvent = {
            type: data.event_type || data.type,
            timestamp: data.timestamp || new Date().toISOString(),
            missionId: newMissionId,
            data: data.payload || data,
          };

          // Enqueue for buffered processing
          enqueueEvent(workflowEvent);
        } catch (error) {
          console.error("[LiveStream] Parse error:", error);
        }
      };

      eventSource.onerror = () => {
        console.error("[LiveStream] Connection error");
        setStatus("error");
        setConnectionStatus("error");

        // Close errored connection
        eventSource.close();
        eventSourceRef.current = null;

        // Attempt reconnection with exponential backoff
        reconnectAttemptRef.current += 1;
        const delay = Math.min(
          ServiceConfig.WS_RECONNECT_INTERVAL * Math.pow(1.5, reconnectAttemptRef.current - 1),
          30000
        );

        if (reconnectAttemptRef.current <= ServiceConfig.WS_MAX_RETRIES) {
          console.log(`[LiveStream] Reconnecting in ${delay}ms (attempt ${reconnectAttemptRef.current})`);
          setStatus("reconnecting");

          reconnectTimeoutRef.current = setTimeout(() => {
            connect(newMissionId, true);  // P0.5-FIX: Mark as reconnect
          }, delay);
        } else {
          console.error("[LiveStream] Max retries reached");
        }
      };
    } catch (error) {
      console.error("[LiveStream] Failed to create EventSource:", error);
      setStatus("error");
      setConnectionStatus("error");
    }
  }, [enqueueEvent, setConnectionStatus]);

  // Load historical data for completed missions
  const loadHistoricalData = useCallback(async (newMissionId: string) => {
    // Reset current state
    reset();
    eventQueueRef.current = [];
    setQueueLength(0);
    setProcessedCount(0);

    setMissionId(newMissionId);
    setStatus("connecting");
    setIsHistorical(true);
    setConnectionStatus("connecting");

    console.log("[LiveStream] Loading historical data for mission:", newMissionId);

    try {
      // Fetch workflow nodes from GraphQL - use inline query with enum values (no variables for types)
      // GraphQL enums must be unquoted, so we can't use JSON variables
      const response = await fetch(`${ServiceConfig.BFF_GATEWAY}/graphql`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: `
            query GetWorkflowNodes($missionId: String!) {
              nodes(missionId: $missionId, filter: { types: [AGENT_RUN, TOOL_CALL] }, limit: 1000) {
                id
                type
                properties
              }
            }
          `,
          variables: {
            missionId: newMissionId,
          },
        }),
      });

      const result = await response.json();

      if (result.errors) {
        console.error("[LiveStream] GraphQL errors:", result.errors);
        throw new Error(result.errors[0]?.message || "GraphQL error");
      }

      const nodes = result.data?.nodes || [];

      console.log(`[LiveStream] Loaded ${nodes.length} workflow nodes`);

      // Process nodes - convert to workflow events and add to store
      nodes.forEach((node: any) => {
        const props = node.properties || {};

        // Normalize status: backend may send 'success' instead of 'completed'
        // Also use end_time as fallback indicator
        const normalizeStatus = (status: string | undefined, hasEndTime: boolean): 'running' | 'completed' | 'error' | 'pending' => {
          if (status === 'completed' || status === 'success') return 'completed';
          if (status === 'running') return 'running';
          if (status === 'error') return 'error';
          // Fallback: if has end_time, consider completed
          return hasEndTime ? 'completed' : 'running';
        };

        if (node.type === "AGENT_RUN") {
          const normalizedStatus = normalizeStatus(props.status, !!props.end_time);
          addAgentRun({
            id: node.id,
            label: props.agent_name || "Unknown Agent",
            status: normalizedStatus,
            metadata: {
              timestamp: props.start_time || new Date().toISOString(),
              phase: props.phase,
            },
            data: {
              agentName: props.agent_name || "Unknown",
              phase: (props.phase as MissionPhase) || MissionPhase.OSINT,
              startTime: props.start_time,
              endTime: props.end_time,
              duration: props.duration,
              tokens: props.tokens,
            },
          });
          setProcessedCount((c) => c + 1);
        } else if (node.type === "TOOL_CALL") {
          const normalizedStatus = normalizeStatus(props.status, !!props.end_time);
          addToolCall({
            id: node.id,
            label: props.tool || "Unknown Tool",
            status: normalizedStatus,
            metadata: {
              timestamp: props.start_time || new Date().toISOString(),
              source: props.agent_id,
            },
            data: {
              toolName: props.tool || "Unknown",
              agentId: props.agent_id || "",
              args: JSON.stringify(props.args || {}),
              startTime: props.start_time,
              endTime: props.end_time,
              duration: props.duration,
              result: JSON.stringify(props.result || {}),
              error: props.error,
            },
          });
          setProcessedCount((c) => c + 1);
        }
      });

      // Note: Logs query not available in current schema
      // Historical logs would need a separate endpoint

      // Force complete all items since this is historical data (mission already finished)
      forceCompleteAll();

      setStatus("historical");
      setConnectionStatus("connected");
      console.log("[LiveStream] Historical data loaded successfully");
    } catch (error) {
      console.error("[LiveStream] Failed to load historical data:", error);
      setStatus("error");
      setConnectionStatus("error");
    }
  }, [reset, addAgentRun, addToolCall, setConnectionStatus, forceCompleteAll]);

  // Disconnect from live stream only (preserves historical state)
  const disconnect = useCallback(() => {
    // Close event source if we have a live connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
      console.log("[LiveStream] Live connection closed");
    }

    // Clear reconnect timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    // Clear processing timer
    if (processingTimerRef.current) {
      clearTimeout(processingTimerRef.current);
      processingTimerRef.current = null;
    }

    // Only reset state if we were in live mode (not historical)
    // This prevents losing historical data when component re-renders
    if (!isHistorical) {
      setStatus("disconnected");
      setConnectionStatus("disconnected");
      setMissionId(null);
      eventQueueRef.current = [];
      setQueueLength(0);
      isProcessingRef.current = false;
      reconnectAttemptRef.current = 0;
      console.log("[LiveStream] Live stream disconnected");
    }
  }, [setConnectionStatus, isHistorical]);

  // Pause processing
  const pause = useCallback(() => {
    setIsPaused(true);
    if (processingTimerRef.current) {
      clearTimeout(processingTimerRef.current);
      processingTimerRef.current = null;
    }
    console.log("[LiveStream] Paused");
  }, []);

  // Resume processing
  const resume = useCallback(() => {
    setIsPaused(false);
    // Restart processing if queue has items
    if (eventQueueRef.current.length > 0 && !isProcessingRef.current) {
      processNextEvent();
    }
    console.log("[LiveStream] Resumed");
  }, [processNextEvent]);

  // Set processing delay
  const setProcessingDelay = useCallback((ms: number) => {
    processingDelayRef.current = Math.max(
      MIN_PROCESSING_DELAY,
      Math.min(MAX_PROCESSING_DELAY, ms)
    );
    console.log("[LiveStream] Processing delay set to:", processingDelayRef.current);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  // Context value
  const contextValue = useMemo<LiveStreamContextValue>(
    () => ({
      status,
      isLive: status === "connected",
      isPaused,
      isHistorical,
      queueLength,
      processedCount,
      eventsPerSecond,
      connect,
      disconnect,
      pause,
      resume,
      setProcessingDelay,
      loadHistoricalData,
      missionId,
    }),
    [
      status,
      isPaused,
      isHistorical,
      queueLength,
      processedCount,
      eventsPerSecond,
      connect,
      disconnect,
      pause,
      resume,
      setProcessingDelay,
      loadHistoricalData,
      missionId,
    ]
  );

  return (
    <LiveStreamContext.Provider value={contextValue}>
      {children}
    </LiveStreamContext.Provider>
  );
}

// Hook to use live stream context
export function useLiveStream() {
  const context = useContext(LiveStreamContext);
  if (!context) {
    throw new Error("useLiveStream must be used within a LiveStreamProvider");
  }
  return context;
}

// Optional hook that returns null if not in provider (for optional usage)
export function useLiveStreamOptional() {
  return useContext(LiveStreamContext);
}
