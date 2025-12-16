/**
 * API Configuration and utilities for Gotham UI
 */

// Environment-based URLs
export const API_CONFIG = {
  GRAPH_SERVICE_WS: process.env.NEXT_PUBLIC_GRAPH_WS_URL || "ws://localhost:8001",
  ORCHESTRATOR_WS: process.env.NEXT_PUBLIC_ORCHESTRATOR_WS_URL || "ws://localhost:8000",
  BFF_GATEWAY: process.env.NEXT_PUBLIC_BFF_URL || "http://localhost:8080",
  GRAPHQL_ENDPOINT: process.env.NEXT_PUBLIC_GRAPHQL_URL || "http://localhost:8080/graphql",
  GRAPHQL_WS: process.env.NEXT_PUBLIC_GRAPHQL_WS_URL || "ws://localhost:8080/graphql",
};

// GraphQL queries
export const QUERIES = {
  GET_MISSION: `
    query GetMission($id: String!) {
      mission(id: $id) {
        id
        targetDomain
        mode
        status
        currentPhase
        createdAt
        progress
      }
    }
  `,

  GET_NODES: `
    query GetNodes($missionId: String!, $limit: Int) {
      nodes(missionId: $missionId, limit: $limit) {
        id
        type
        properties
      }
    }
  `,

  GET_EDGES: `
    query GetEdges($missionId: String!) {
      edges(missionId: $missionId) {
        fromNode
        toNode
        relation
      }
    }
  `,

  GET_STATS: `
    query GetStats($missionId: String!) {
      graphStats(missionId: $missionId) {
        missionId
        totalNodes
        totalEdges
        nodesByType
      }
    }
  `,

  GET_ATTACK_PATHS: `
    query GetAttackPaths($missionId: String!, $top: Int) {
      attackPaths(missionId: $missionId, top: $top) {
        target
        score
        actions
        reasons
      }
    }
  `,
};

// GraphQL mutations
export const MUTATIONS = {
  START_MISSION: `
    mutation StartMission($input: MissionInput!) {
      startMission(input: $input) {
        id
        targetDomain
        mode
        status
        createdAt
      }
    }
  `,

  CANCEL_MISSION: `
    mutation CancelMission($id: String!) {
      cancelMission(id: $id)
    }
  `,

  DELETE_MISSION: `
    mutation DeleteMission($missionId: String!) {
      deleteMission(missionId: $missionId)
    }
  `,

  DELETE_MISSION_HISTORY: `
    mutation DeleteMissionHistory($missionId: String!) {
      deleteMissionHistory(missionId: $missionId)
    }
  `,

  CLEAR_ALL_DATA: `
    mutation ClearAllData($confirm: String!) {
      clearAllData(confirm: $confirm)
    }
  `,
};

// GraphQL subscriptions
export const SUBSCRIPTIONS = {
  GRAPH_EVENTS: `
    subscription GraphEvents($runId: String!) {
      graphEvents(runId: $runId) {
        runId
        eventType
        source
        payload
        timestamp
      }
    }
  `,

  LOGS: `
    subscription Logs($runId: String!) {
      logs(runId: $runId) {
        runId
        level
        phase
        message
        timestamp
        metadata
      }
    }
  `,
};

// GraphQL fetch helper
export async function graphqlFetch<T>(
  query: string,
  variables?: Record<string, unknown>
): Promise<T> {
  const response = await fetch(API_CONFIG.GRAPHQL_ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ query, variables }),
  });

  const json = await response.json();

  if (json.errors) {
    throw new Error(json.errors[0]?.message || "GraphQL error");
  }

  return json.data;
}

// Types
export interface GraphNode {
  id: string;
  type: string;
  properties: Record<string, unknown>;
}

export interface GraphEdge {
  fromNode: string;
  toNode: string;
  relation: string;
}

export interface GraphEvent {
  runId: string;
  eventType: "node_added" | "node_updated" | "node_deleted" | "edge_added" | "edge_deleted";
  source: string;
  payload: {
    node?: GraphNode;
    nodes?: GraphNode[];
    edge?: GraphEdge;
    edges?: GraphEdge[];
    count?: number;
  };
  timestamp: string;
}

export interface LogEntry {
  runId: string;
  level: "DEBUG" | "INFO" | "WARNING" | "ERROR";
  phase: string;
  message: string;
  timestamp: string;
  metadata: Record<string, unknown>;
}

export interface Mission {
  id: string;
  targetDomain: string;
  mode: "stealth" | "aggressive" | "balanced";
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  currentPhase?: string;
  createdAt: string;
  progress: Record<string, unknown>;
}
