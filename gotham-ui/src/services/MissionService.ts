/**
 * Mission Service
 * Handles all mission-related operations with proper data transformation
 */

import { graphqlClient, GQL_QUERIES, GQL_MUTATIONS, transformMission } from './api/GraphQLClient';
import { wsManager, WebSocketConnection, ConnectionStatus } from './websocket/WebSocketManager';
import { ServiceConfig } from './config';

// Types
export type MissionMode = 'STEALTH' | 'BALANCED' | 'AGGRESSIVE';
export type MissionStatus = 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';

export interface MissionProgress {
  phase: string;
  percent: number;
  message: string;
}

export interface MissionStats {
  totalNodes: number;
  totalEdges: number;
  nodesByType: Record<string, number>;
  criticalFindings?: number;
  highFindings?: number;
  mediumFindings?: number;
  lowFindings?: number;
}

export interface Mission {
  id: string;
  targetDomain: string;
  mode: MissionMode;
  status: MissionStatus;
  currentPhase?: string;
  progress?: MissionProgress;
  stats?: MissionStats;
  createdAt: string;
  updatedAt?: string;
}

export interface LogEntry {
  id?: string;
  missionId: string;
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR';
  phase?: string;
  message: string;
  metadata?: Record<string, unknown>;
  timestamp: string;
}

export interface StartMissionInput {
  targetDomain: string;
  mode?: MissionMode;
  seedSubdomains?: string[];
  options?: Record<string, unknown>;
}

// Event types
export type MissionEventHandler = (mission: Mission) => void;
export type LogEventHandler = (log: LogEntry) => void;
export type StatusChangeHandler = (status: ConnectionStatus) => void;

class MissionServiceClass {
  private logsConnection: WebSocketConnection | null = null;
  private logHandlers: Set<LogEventHandler> = new Set();
  private statusHandlers: Set<StatusChangeHandler> = new Set();
  private currentMissionId: string | null = null;

  /**
   * Start a new mission
   */
  async startMission(input: StartMissionInput): Promise<Mission | null> {
    // Transform input to backend format - Strawberry expects snake_case in input
    const backendInput = {
      targetDomain: input.targetDomain,
      mode: (input.mode?.toUpperCase() || 'AGGRESSIVE'),
      seedSubdomains: input.seedSubdomains,
    };

    const response = await graphqlClient.mutate<{ startMission: Record<string, unknown> }>(
      GQL_MUTATIONS.START_MISSION,
      { input: backendInput }
    );

    if (response.success && response.data?.startMission) {
      const mission = transformMission(response.data.startMission) as unknown as Mission;
      this.subscribeToLogs(mission.id);
      return mission;
    }

    console.error('Failed to start mission:', response.error);
    return null;
  }

  /**
   * Cancel a running mission
   */
  async cancelMission(missionId: string): Promise<boolean> {
    const response = await graphqlClient.mutate<{ cancelMission: boolean }>(
      GQL_MUTATIONS.CANCEL_MISSION,
      { id: missionId }
    );

    if (response.success) {
      this.unsubscribeFromLogs();
      return true;
    }

    console.error('Failed to cancel mission:', response.error);
    return false;
  }

  /**
   * Delete a mission and all its associated data
   */
  async deleteMission(missionId: string): Promise<{ success: boolean; result?: Record<string, unknown> }> {
    const response = await graphqlClient.mutate<{ deleteMission: Record<string, unknown> }>(
      GQL_MUTATIONS.DELETE_MISSION,
      { missionId }
    );

    if (response.success && response.data?.deleteMission) {
      this.unsubscribeFromLogs();
      return { success: true, result: response.data.deleteMission };
    }

    console.error('Failed to delete mission:', response.error);
    return { success: false };
  }

  /**
   * Delete only mission history (keeps nodes and edges)
   */
  async deleteMissionHistory(missionId: string): Promise<{ success: boolean; result?: Record<string, unknown> }> {
    const response = await graphqlClient.mutate<{ deleteMissionHistory: Record<string, unknown> }>(
      GQL_MUTATIONS.DELETE_MISSION_HISTORY,
      { missionId }
    );

    if (response.success && response.data?.deleteMissionHistory) {
      return { success: true, result: response.data.deleteMissionHistory };
    }

    console.error('Failed to delete mission history:', response.error);
    return { success: false };
  }

  /**
   * Clear all data from the system (requires confirmation)
   */
  async clearAllData(): Promise<{ success: boolean; result?: Record<string, unknown> }> {
    const response = await graphqlClient.mutate<{ clearAllData: Record<string, unknown> }>(
      GQL_MUTATIONS.CLEAR_ALL_DATA,
      { confirm: 'YES' }
    );

    if (response.success && response.data?.clearAllData) {
      this.unsubscribeFromLogs();
      return { success: true, result: response.data.clearAllData };
    }

    console.error('Failed to clear all data:', response.error);
    return { success: false };
  }

  /**
   * Pause a running mission
   */
  async pauseMission(missionId: string): Promise<boolean> {
    // Note: pause_mission might not be implemented in the backend
    console.warn('pauseMission not implemented in backend');
    return false;
  }

  /**
   * Resume a paused mission
   */
  async resumeMission(missionId: string): Promise<boolean> {
    // Note: resume_mission might not be implemented in the backend
    console.warn('resumeMission not implemented in backend');
    return false;
  }

  /**
   * Get mission by ID
   */
  async getMission(missionId: string): Promise<Mission | null> {
    const response = await graphqlClient.query<{ mission: Record<string, unknown> }>(
      GQL_QUERIES.GET_MISSION,
      { id: missionId }
    );

    if (response.success && response.data?.mission) {
      return transformMission(response.data.mission) as unknown as Mission;
    }
    return null;
  }

  /**
   * Get list of missions
   */
  async getMissions(limit: number = 20, offset: number = 0): Promise<{ items: Mission[]; total: number }> {
    const response = await graphqlClient.query<{
      missions: { items: Record<string, unknown>[]; total: number }
    }>(
      GQL_QUERIES.GET_MISSIONS,
      { limit, offset }
    );

    if (response.success && response.data?.missions) {
      const items = response.data.missions.items.map(m => transformMission(m) as unknown as Mission);
      return { items, total: response.data.missions.total };
    }
    return { items: [], total: 0 };
  }

  /**
   * Get mission statistics
   */
  async getStats(missionId: string): Promise<MissionStats | null> {
    const response = await graphqlClient.query<{
      graphStats: {
        totalNodes: number;
        totalEdges: number;
        nodesByType: Record<string, number>;
      }
    }>(
      GQL_QUERIES.GET_STATS,
      { missionId: missionId }
    );

    if (response.success && response.data?.graphStats) {
      const stats = response.data.graphStats;
      return {
        totalNodes: stats.totalNodes,
        totalEdges: stats.totalEdges,
        nodesByType: stats.nodesByType,
      };
    }
    return null;
  }

  /**
   * Subscribe to mission logs via WebSocket
   */
  subscribeToLogs(missionId: string): void {
    if (this.currentMissionId === missionId && this.logsConnection?.isConnected()) {
      return;
    }

    this.unsubscribeFromLogs();
    this.currentMissionId = missionId;

    // Use SSE endpoint for logs - always use BFF Gateway
    const url = `${ServiceConfig.BFF_GATEWAY}/api/v1/sse/events/${missionId}`;

    // Create EventSource for SSE
    try {
      const eventSource = new EventSource(url);

      eventSource.onopen = () => {
        console.log('[SSE] Connected to logs:', missionId);
        this.statusHandlers.forEach(handler => handler('connected'));
      };

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // Handle keepalive
          if (data.type === 'keepalive') return;

          // Parse as log entry
          const log = this.parseLogMessage(data, missionId);
          this.logHandlers.forEach(handler => handler(log));
        } catch (err) {
          console.error('[SSE] Parse error:', err);
        }
      };

      eventSource.onerror = (err) => {
        console.error('[SSE] Error:', err);
        this.statusHandlers.forEach(handler => handler('error'));

        // Reconnect after delay
        setTimeout(() => {
          if (this.currentMissionId === missionId) {
            this.subscribeToLogs(missionId);
          }
        }, ServiceConfig.WS_RECONNECT_INTERVAL);
      };

      // Store reference for cleanup (using any to avoid type issues)
      (this as any)._eventSource = eventSource;
    } catch (err) {
      console.error('[SSE] Failed to connect:', err);

      // Fallback to WebSocket
      this.subscribeToLogsWebSocket(missionId);
    }
  }

  /**
   * Fallback WebSocket subscription
   */
  private subscribeToLogsWebSocket(missionId: string): void {
    const url = `${ServiceConfig.WS_ORCHESTRATOR}/ws/logs/${missionId}`;

    this.logsConnection = wsManager.createConnection(`logs-${missionId}`, url, {
      reconnect: true,
      onStatusChange: (status) => {
        this.statusHandlers.forEach(handler => handler(status));
      },
      onMessage: (message) => {
        // Parse log message
        if (message.type === 'log' || message.type === 'mission_log') {
          const log = this.parseLogMessage(message.payload as Record<string, unknown>, missionId);
          this.logHandlers.forEach(handler => handler(log));
        } else if (typeof message.payload === 'object') {
          // Direct log object
          const log = this.parseLogMessage(message.payload as Record<string, unknown>, missionId);
          this.logHandlers.forEach(handler => handler(log));
        }
      },
    });

    this.logsConnection.connect();
  }

  /**
   * Unsubscribe from mission logs
   */
  unsubscribeFromLogs(): void {
    // Close SSE connection
    if ((this as any)._eventSource) {
      (this as any)._eventSource.close();
      (this as any)._eventSource = null;
    }

    // Close WebSocket connection
    if (this.currentMissionId) {
      wsManager.disconnect(`logs-${this.currentMissionId}`);
      this.logsConnection = null;
      this.currentMissionId = null;
    }
  }

  /**
   * Add log event handler
   */
  onLog(handler: LogEventHandler): () => void {
    this.logHandlers.add(handler);
    return () => this.logHandlers.delete(handler);
  }

  /**
   * Add status change handler
   */
  onStatusChange(handler: StatusChangeHandler): () => void {
    this.statusHandlers.add(handler);
    return () => this.statusHandlers.delete(handler);
  }

  /**
   * Get current connection status
   */
  getConnectionStatus(): ConnectionStatus {
    return this.logsConnection?.getStatus() || 'disconnected';
  }

  /**
   * Parse raw log message to LogEntry
   */
  private parseLogMessage(raw: Record<string, unknown>, missionId: string): LogEntry {
    return {
      missionId,
      level: this.normalizeLogLevel(raw.level as string),
      phase: raw.phase as string,
      message: raw.message as string || raw.msg as string || JSON.stringify(raw),
      metadata: raw.metadata as Record<string, unknown>,
      timestamp: raw.timestamp as string || new Date().toISOString(),
    };
  }

  /**
   * Normalize log level string
   */
  private normalizeLogLevel(level: string): LogEntry['level'] {
    const normalized = (level || 'INFO').toUpperCase();
    if (['DEBUG', 'INFO', 'WARNING', 'ERROR'].includes(normalized)) {
      return normalized as LogEntry['level'];
    }
    if (normalized === 'WARN') return 'WARNING';
    return 'INFO';
  }

  /**
   * Cleanup all connections
   */
  cleanup(): void {
    this.unsubscribeFromLogs();
    this.logHandlers.clear();
    this.statusHandlers.clear();
  }
}

// Singleton instance
export const MissionService = new MissionServiceClass();
