/**
 * Graph Service
 * Handles all graph-related operations (nodes, edges, real-time updates)
 */

import { graphqlClient, GQL_QUERIES, transformNode, transformEdge } from './api/GraphQLClient';
import { wsManager, WebSocketConnection, ConnectionStatus } from './websocket/WebSocketManager';
import { ServiceConfig } from './config';
import { NodeType } from './types';

export interface GraphNode {
  id: string;
  type: NodeType;
  missionId?: string;
  properties: Record<string, unknown>;
  createdAt?: string;
  updatedAt?: string;
}

export interface GraphEdge {
  id?: string;
  fromNode: string;
  toNode: string;
  relation: string;
  properties?: Record<string, unknown>;
}

export interface GraphEvent {
  type: 'node_added' | 'node_updated' | 'node_deleted' | 'edge_added' | 'edge_deleted';
  data: GraphNode | GraphEdge;
  timestamp?: string;
}

export interface AttackPath {
  id: string;
  nodes: string[];
  edges: string[];
  riskScore: number;
  description: string;
}

// Event handlers
export type NodeEventHandler = (node: GraphNode) => void;
export type EdgeEventHandler = (edge: GraphEdge) => void;
export type GraphEventHandler = (event: GraphEvent) => void;
export type StatusChangeHandler = (status: ConnectionStatus) => void;

class GraphServiceClass {
  private connection: WebSocketConnection | null = null;
  private eventSource: EventSource | null = null;
  private currentMissionId: string | null = null;

  private nodeAddedHandlers: Set<NodeEventHandler> = new Set();
  private nodeUpdatedHandlers: Set<NodeEventHandler> = new Set();
  private nodeDeletedHandlers: Set<NodeEventHandler> = new Set();
  private edgeAddedHandlers: Set<EdgeEventHandler> = new Set();
  private edgeDeletedHandlers: Set<EdgeEventHandler> = new Set();
  private graphEventHandlers: Set<GraphEventHandler> = new Set();
  private statusHandlers: Set<StatusChangeHandler> = new Set();

  /**
   * Get nodes for a mission
   */
  async getNodes(
    missionId: string,
    types?: NodeType[],
    limit: number = 1000,
    offset: number = 0
  ): Promise<{ items: GraphNode[]; total: number }> {
    const filter = types ? { types } : undefined;

    const response = await graphqlClient.query<{ nodes: Record<string, unknown>[] }>(
      GQL_QUERIES.GET_NODES,
      { missionId, filter, limit }
    );

    if (response.success && response.data?.nodes) {
      const items = response.data.nodes.map(n => transformNode(n) as unknown as GraphNode);
      return { items, total: items.length };
    }
    return { items: [], total: 0 };
  }

  /**
   * Get edges for a mission
   */
  async getEdges(missionId: string): Promise<GraphEdge[]> {
    const response = await graphqlClient.query<{ edges: Record<string, unknown>[] }>(
      GQL_QUERIES.GET_EDGES,
      { missionId }
    );

    if (response.success && response.data?.edges) {
      return response.data.edges.map(e => transformEdge(e) as unknown as GraphEdge);
    }
    return [];
  }

  /**
   * Get attack paths for a mission
   */
  async getAttackPaths(missionId: string): Promise<AttackPath[]> {
    const response = await graphqlClient.query<{
      attackPaths: Array<{
        target: string;
        score: number;
        actions: string[];
        reasons: string[];
      }>
    }>(
      GQL_QUERIES.GET_ATTACK_PATHS,
      { missionId, top: 10 }
    );

    if (response.success && response.data?.attackPaths) {
      return response.data.attackPaths.map((path, idx) => ({
        id: `path-${idx}`,
        nodes: [],
        edges: [],
        riskScore: path.score,
        description: path.target,
      }));
    }
    return [];
  }

  /**
   * Fetch initial graph snapshot (nodes + edges)
   */
  async getGraphSnapshot(missionId: string): Promise<{ nodes: GraphNode[]; edges: GraphEdge[] }> {
    const [nodesResult, edgesResult] = await Promise.all([
      this.getNodes(missionId),
      this.getEdges(missionId),
    ]);

    return {
      nodes: nodesResult.items,
      edges: edgesResult,
    };
  }

  /**
   * Subscribe to real-time graph updates via SSE
   */
  subscribe(missionId: string): void {
    if (this.currentMissionId === missionId && this.eventSource) {
      return;
    }

    this.unsubscribe();
    this.currentMissionId = missionId;

    // Use SSE endpoint for real-time updates - always use BFF Gateway
    const url = `${ServiceConfig.BFF_GATEWAY}/api/v1/sse/events/${missionId}`;

    try {
      this.eventSource = new EventSource(url);

      this.eventSource.onopen = () => {
        console.log('[Graph SSE] Connected:', missionId);
        this.statusHandlers.forEach(handler => handler('connected'));
      };

      this.eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // Handle keepalive
          if (data.type === 'keepalive') return;

          // Handle graph events
          this.handleGraphEvent(data.event_type || data.type, data.payload || data);
        } catch (err) {
          console.error('[Graph SSE] Parse error:', err);
        }
      };

      this.eventSource.onerror = (err) => {
        console.error('[Graph SSE] Error:', err);
        this.statusHandlers.forEach(handler => handler('error'));

        // Reconnect after delay
        setTimeout(() => {
          if (this.currentMissionId === missionId) {
            this.subscribe(missionId);
          }
        }, ServiceConfig.WS_RECONNECT_INTERVAL);
      };
    } catch (err) {
      console.error('[Graph SSE] Failed to connect:', err);
      // Fallback to WebSocket
      this.subscribeWebSocket(missionId);
    }
  }

  /**
   * Fallback WebSocket subscription
   */
  private subscribeWebSocket(missionId: string): void {
    const url = `${ServiceConfig.WS_GRAPH}/ws/graph/${missionId}`;

    this.connection = wsManager.createConnection(`graph-${missionId}`, url, {
      reconnect: true,
      onStatusChange: (status) => {
        this.statusHandlers.forEach(handler => handler(status));
      },
      onMessage: (message) => {
        this.handleGraphEvent(message.type, message.payload);
      },
    });

    this.connection.connect();
  }

  /**
   * Unsubscribe from graph updates
   */
  unsubscribe(): void {
    // Close SSE connection
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }

    // Close WebSocket connection
    if (this.currentMissionId) {
      wsManager.disconnect(`graph-${this.currentMissionId}`);
      this.connection = null;
      this.currentMissionId = null;
    }

    this.statusHandlers.forEach(handler => handler('disconnected'));
  }

  /**
   * Handle incoming graph event
   */
  private handleGraphEvent(type: string, payload: unknown): void {
    if (!payload) return;

    const eventType = type?.toLowerCase().replace(/_/g, '_') as GraphEvent['type'];

    // Transform payload based on event type
    let data: GraphNode | GraphEdge;

    if (type?.includes('node')) {
      data = transformNode(payload as Record<string, unknown>) as unknown as GraphNode;
    } else if (type?.includes('edge')) {
      data = transformEdge(payload as Record<string, unknown>) as unknown as GraphEdge;
    } else {
      return;
    }

    const event: GraphEvent = {
      type: eventType,
      data,
      timestamp: new Date().toISOString(),
    };

    // Notify generic handlers
    this.graphEventHandlers.forEach(handler => handler(event));

    // Notify specific handlers
    switch (type?.toLowerCase()) {
      case 'node_added':
        this.nodeAddedHandlers.forEach(handler => handler(data as GraphNode));
        break;
      case 'node_updated':
        this.nodeUpdatedHandlers.forEach(handler => handler(data as GraphNode));
        break;
      case 'node_deleted':
        this.nodeDeletedHandlers.forEach(handler => handler(data as GraphNode));
        break;
      case 'edge_added':
        this.edgeAddedHandlers.forEach(handler => handler(data as GraphEdge));
        break;
      case 'edge_deleted':
        this.edgeDeletedHandlers.forEach(handler => handler(data as GraphEdge));
        break;
    }
  }

  // Event subscription methods
  onNodeAdded(handler: NodeEventHandler): () => void {
    this.nodeAddedHandlers.add(handler);
    return () => this.nodeAddedHandlers.delete(handler);
  }

  onNodeUpdated(handler: NodeEventHandler): () => void {
    this.nodeUpdatedHandlers.add(handler);
    return () => this.nodeUpdatedHandlers.delete(handler);
  }

  onNodeDeleted(handler: NodeEventHandler): () => void {
    this.nodeDeletedHandlers.add(handler);
    return () => this.nodeDeletedHandlers.delete(handler);
  }

  onEdgeAdded(handler: EdgeEventHandler): () => void {
    this.edgeAddedHandlers.add(handler);
    return () => this.edgeAddedHandlers.delete(handler);
  }

  onEdgeDeleted(handler: EdgeEventHandler): () => void {
    this.edgeDeletedHandlers.add(handler);
    return () => this.edgeDeletedHandlers.delete(handler);
  }

  onGraphEvent(handler: GraphEventHandler): () => void {
    this.graphEventHandlers.add(handler);
    return () => this.graphEventHandlers.delete(handler);
  }

  onStatusChange(handler: StatusChangeHandler): () => void {
    this.statusHandlers.add(handler);
    return () => this.statusHandlers.delete(handler);
  }

  /**
   * Get current connection status
   */
  getConnectionStatus(): ConnectionStatus {
    if (this.eventSource?.readyState === EventSource.OPEN) {
      return 'connected';
    }
    return this.connection?.getStatus() || 'disconnected';
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.eventSource?.readyState === EventSource.OPEN || this.connection?.isConnected() || false;
  }

  /**
   * Cleanup all connections and handlers
   */
  cleanup(): void {
    this.unsubscribe();
    this.nodeAddedHandlers.clear();
    this.nodeUpdatedHandlers.clear();
    this.nodeDeletedHandlers.clear();
    this.edgeAddedHandlers.clear();
    this.edgeDeletedHandlers.clear();
    this.graphEventHandlers.clear();
    this.statusHandlers.clear();
  }
}

// Singleton instance
export const GraphService = new GraphServiceClass();
