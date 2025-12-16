/**
 * GraphQL Client
 * Handles all GraphQL operations with proper typing and error handling
 */

import { BaseClient, ApiResponse } from './BaseClient';
import { ServiceConfig } from '../config';

export interface GraphQLError {
  message: string;
  locations?: Array<{ line: number; column: number }>;
  path?: string[];
  extensions?: Record<string, unknown>;
}

export interface GraphQLResponse<T> {
  data?: T;
  errors?: GraphQLError[];
}

export class GraphQLClient extends BaseClient {
  constructor() {
    super(ServiceConfig.GRAPHQL_HTTP);
  }

  async query<T>(
    query: string,
    variables?: Record<string, unknown>,
    operationName?: string
  ): Promise<ApiResponse<T>> {
    const response = await this.post<GraphQLResponse<T>>('', {
      query,
      variables,
      operationName,
    });

    if (!response.success) {
      return response as ApiResponse<T>;
    }

    const gqlResponse = response.data;

    if (gqlResponse?.errors?.length) {
      this.log('error', 'GraphQL errors', gqlResponse.errors);
      return {
        data: null,
        error: {
          code: 'GRAPHQL_ERROR',
          message: gqlResponse.errors[0].message,
          details: gqlResponse.errors,
        },
        success: false,
      };
    }

    return {
      data: gqlResponse?.data || null,
      error: null,
      success: true,
    };
  }

  async mutate<T>(
    mutation: string,
    variables?: Record<string, unknown>,
    operationName?: string
  ): Promise<ApiResponse<T>> {
    return this.query<T>(mutation, variables, operationName);
  }
}

// GraphQL Operations - Strawberry uses camelCase in GraphQL schema
export const GQL_QUERIES = {
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

  GET_MISSIONS: `
    query GetMissions($limit: Int, $offset: Int) {
      missions(limit: $limit, offset: $offset) {
        items {
          id
          targetDomain
          mode
          status
          currentPhase
          createdAt
          progress
        }
        total
      }
    }
  `,

  GET_NODES: `
    query GetNodes($missionId: String!, $filter: NodeFilter, $limit: Int) {
      nodes(missionId: $missionId, filter: $filter, limit: $limit) {
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

export const GQL_MUTATIONS = {
  START_MISSION: `
    mutation StartMission($input: MissionInput!) {
      startMission(input: $input) {
        id
        targetDomain
        mode
        status
        createdAt
        progress
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

// Transform functions - Strawberry already returns camelCase
export function transformMission(raw: Record<string, unknown>) {
  return {
    id: raw.id as string,
    targetDomain: (raw.targetDomain || raw.target_domain) as string,
    mode: (raw.mode as string)?.toUpperCase(),
    status: raw.status as string,
    currentPhase: (raw.currentPhase || raw.current_phase) as string | undefined,
    createdAt: (raw.createdAt || raw.created_at) as string,
    progress: raw.progress as Record<string, unknown>,
  };
}

export function transformNode(raw: Record<string, unknown>) {
  return {
    id: raw.id as string,
    type: raw.type as string,
    properties: raw.properties as Record<string, unknown>,
  };
}

export function transformEdge(raw: Record<string, unknown>) {
  return {
    fromNode: (raw.fromNode || raw.from_node) as string,
    toNode: (raw.toNode || raw.to_node) as string,
    relation: raw.relation as string,
  };
}

// Singleton instance
export const graphqlClient = new GraphQLClient();
