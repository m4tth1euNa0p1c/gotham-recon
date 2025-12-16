"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { API_CONFIG, GraphNode, GraphEdge, GraphEvent, graphqlFetch, QUERIES } from "@/lib/api";

interface UseGraphEventsOptions {
  missionId: string;
  live?: boolean;
  onNodeAdded?: (node: GraphNode) => void;
  onEdgeAdded?: (edge: GraphEdge) => void;
}

interface GraphState {
  nodes: Map<string, GraphNode>;
  edges: GraphEdge[];
  loading: boolean;
  error: string | null;
  connected: boolean;
}

export function useGraphEvents({ missionId, live = true, onNodeAdded, onEdgeAdded }: UseGraphEventsOptions) {
  const [state, setState] = useState<GraphState>({
    nodes: new Map(),
    edges: [],
    loading: true,
    error: null,
    connected: false,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Fetch initial snapshot
  const fetchSnapshot = useCallback(async () => {
    if (!missionId) return;

    setState((prev) => ({ ...prev, loading: true, error: null }));

    try {
      const [nodesData, edgesData] = await Promise.all([
        graphqlFetch<{ nodes: GraphNode[] }>(QUERIES.GET_NODES, { missionId, limit: 500 }),
        graphqlFetch<{ edges: GraphEdge[] }>(QUERIES.GET_EDGES, { missionId }),
      ]);

      const nodesMap = new Map<string, GraphNode>();
      nodesData.nodes.forEach((node) => nodesMap.set(node.id, node));

      setState((prev) => ({
        ...prev,
        nodes: nodesMap,
        edges: edgesData.edges,
        loading: false,
      }));
    } catch (err) {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : "Failed to fetch graph",
      }));
    }
  }, [missionId]);

  // Handle incoming WebSocket events
  const handleEvent = useCallback(
    (event: GraphEvent) => {
      setState((prev) => {
        const newNodes = new Map(prev.nodes);
        let newEdges = [...prev.edges];

        switch (event.eventType) {
          case "node_added":
            if (event.payload.node) {
              newNodes.set(event.payload.node.id, event.payload.node);
              onNodeAdded?.(event.payload.node);
            }
            if (event.payload.nodes) {
              event.payload.nodes.forEach((node) => {
                newNodes.set(node.id, node);
                onNodeAdded?.(node);
              });
            }
            break;

          case "node_updated":
            if (event.payload.node) {
              newNodes.set(event.payload.node.id, event.payload.node);
            }
            break;

          case "node_deleted":
            if (event.payload.node) {
              newNodes.delete(event.payload.node.id);
            }
            break;

          case "edge_added":
            if (event.payload.edge) {
              newEdges.push(event.payload.edge);
              onEdgeAdded?.(event.payload.edge);
            }
            if (event.payload.edges) {
              newEdges = [...newEdges, ...event.payload.edges];
              event.payload.edges.forEach((edge) => onEdgeAdded?.(edge));
            }
            break;

          case "edge_deleted":
            // Handle edge deletion if needed
            break;
        }

        return { ...prev, nodes: newNodes, edges: newEdges };
      });
    },
    [onNodeAdded, onEdgeAdded]
  );

  // Connect to WebSocket for real-time updates
  const connectWebSocket = useCallback(() => {
    if (!missionId || !live) return;

    const wsUrl = `${API_CONFIG.GRAPH_SERVICE_WS}/ws/graph/${missionId}`;

    try {
      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        console.log("[GraphWS] Connected to", wsUrl);
        setState((prev) => ({ ...prev, connected: true }));
      };

      wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // Handle snapshot
          if (data.type === "snapshot") {
            const nodesMap = new Map<string, GraphNode>();
            data.data.nodes?.forEach((node: GraphNode) => nodesMap.set(node.id, node));
            setState((prev) => ({
              ...prev,
              nodes: nodesMap,
              edges: data.data.edges || [],
              loading: false,
            }));
          } else {
            // Handle events
            handleEvent(data as GraphEvent);
          }
        } catch (err) {
          console.error("[GraphWS] Parse error:", err);
        }
      };

      wsRef.current.onerror = (err) => {
        console.error("[GraphWS] Error:", err);
        setState((prev) => ({ ...prev, error: "WebSocket error" }));
      };

      wsRef.current.onclose = () => {
        console.log("[GraphWS] Disconnected");
        setState((prev) => ({ ...prev, connected: false }));

        // Reconnect after 3 seconds
        reconnectTimeoutRef.current = setTimeout(() => {
          connectWebSocket();
        }, 3000);
      };
    } catch (err) {
      console.error("[GraphWS] Connection failed:", err);
    }
  }, [missionId, live, handleEvent]);

  // Initialize
  useEffect(() => {
    fetchSnapshot();

    if (live) {
      connectWebSocket();
    }

    return () => {
      wsRef.current?.close();
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [fetchSnapshot, connectWebSocket, live]);

  // Convert nodes Map to array for rendering
  const nodesArray = Array.from(state.nodes.values());

  return {
    nodes: nodesArray,
    edges: state.edges,
    loading: state.loading,
    error: state.error,
    connected: state.connected,
    refetch: fetchSnapshot,
  };
}

export default useGraphEvents;
