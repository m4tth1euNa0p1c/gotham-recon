/**
 * Services Index
 * Central export for all services
 */

// Configuration
export { ServiceConfig } from './config';
export type { ServiceConfigType } from './config';

// API Clients
export { BaseClient } from './api/BaseClient';
export type { ApiError, ApiResponse, RequestOptions } from './api/BaseClient';

export { GraphQLClient, graphqlClient, GQL_QUERIES, GQL_MUTATIONS } from './api/GraphQLClient';
export type { GraphQLError, GraphQLResponse } from './api/GraphQLClient';

// WebSocket
export { WebSocketConnection, WebSocketManager, wsManager } from './websocket/WebSocketManager';
export type { ConnectionStatus, WebSocketMessage, WebSocketOptions } from './websocket/WebSocketManager';

// Domain Services - Import and re-export to avoid conflicts
// MissionService exports (all except StatusChangeHandler)
export { MissionService } from './MissionService';
export type {
  MissionMode,
  MissionStatus,
  MissionProgress,
  MissionStats,
  Mission,
  LogEntry,
  StartMissionInput,
  MissionEventHandler,
  LogEventHandler,
} from './MissionService';

// GraphService exports (all except StatusChangeHandler)
export { GraphService } from './GraphService';
export type {
  GraphNode,
  GraphEdge,
  GraphEvent,
  AttackPath,
  NodeEventHandler,
  EdgeEventHandler,
  GraphEventHandler,
} from './GraphService';

// WorkflowService exports
export { WorkflowService, WORKFLOW_QUERIES } from './WorkflowService';
export type {
  StatusChangeHandler,
  AgentStartedHandler,
  AgentFinishedHandler,
  ToolCalledHandler,
  ToolFinishedHandler,
  TraceHandler,
} from './WorkflowService';

export * from './ExtensionService';
export * from './LayoutService';

// Common Types
export * from './types';
