/**
 * Workflow Service
 * Handles workflow event subscriptions and queries
 */

import { graphqlClient, GQL_QUERIES } from './api/GraphQLClient';
import { wsManager, WebSocketConnection, ConnectionStatus } from './websocket/WebSocketManager';
import { ServiceConfig } from './config';
import {
  NodeType,
  WorkflowEvent,
  WorkflowEventType,
  WorkflowNodeStatus
} from './types';
import {
  AgentRunNode,
  ToolCallNode,
} from '@/stores/workflowStore';
import { DomainEdge as WorkflowEdge, TraceEntry } from './types';

// Event handlers
export type AgentStartedHandler = (agent: AgentRunNode) => void;
export type AgentFinishedHandler = (agentId: string, status: WorkflowNodeStatus, latency?: number) => void;
export type ToolCalledHandler = (tool: ToolCallNode) => void;
export type ToolFinishedHandler = (toolId: string, duration: number, outcome: 'success' | 'failure') => void;
export type TraceHandler = (trace: TraceEntry) => void;
export type StatusChangeHandler = (status: ConnectionStatus) => void;

// GraphQL queries for workflow
export const WORKFLOW_QUERIES = {
  GET_WORKFLOW_NODES: `
    query GetWorkflowNodes($missionId: String!, $types: [NodeType!]) {
      workflowNodes(missionId: $missionId, types: $types) {
        id
        type
        properties
      }
    }
  `,

  GET_WORKFLOW_LAYOUT: `
    query GetWorkflowLayout($missionId: String!) {
      workflowLayout(missionId: $missionId)
    }
  `,

  SAVE_WORKFLOW_LAYOUT: `
    mutation SaveWorkflowLayout($missionId: String!, $positions: JSON!, $zoom: Float!, $panX: Float!, $panY: Float!) {
      saveWorkflowLayout(missionId: $missionId, positions: $positions, zoom: $zoom, panX: $panX, panY: $panY)
    }
  `,
};

class WorkflowServiceClass {
  private eventSource: EventSource | null = null;
  private currentMissionId: string | null = null;

  private agentStartedHandlers: Set<AgentStartedHandler> = new Set();
  private agentFinishedHandlers: Set<AgentFinishedHandler> = new Set();
  private toolCalledHandlers: Set<ToolCalledHandler> = new Set();
  private toolFinishedHandlers: Set<ToolFinishedHandler> = new Set();
  private traceHandlers: Set<TraceHandler> = new Set();
  private statusHandlers: Set<StatusChangeHandler> = new Set();

  /**
   * Subscribe to workflow events for a mission
   */
  subscribe(missionId: string): void {
    if (this.currentMissionId === missionId && this.eventSource) {
      return;
    }

    this.unsubscribe();
    this.currentMissionId = missionId;

    // Use SSE endpoint for real-time updates
    const url = `${ServiceConfig.BFF_GATEWAY}/api/v1/sse/events/${missionId}`;

    try {
      this.eventSource = new EventSource(url);

      this.eventSource.onopen = () => {
        console.log('[Workflow SSE] Connected:', missionId);
        this.statusHandlers.forEach(handler => handler('connected'));
      };

      this.eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // Handle keepalive
          if (data.type === 'keepalive') return;

          // Handle workflow events
          this.handleWorkflowEvent(data);
        } catch (err) {
          console.error('[Workflow SSE] Parse error:', err);
        }
      };

      this.eventSource.onerror = () => {
        console.error('[Workflow SSE] Error');
        this.statusHandlers.forEach(handler => handler('error'));

        // Reconnect after delay
        setTimeout(() => {
          if (this.currentMissionId === missionId) {
            this.subscribe(missionId);
          }
        }, ServiceConfig.WS_RECONNECT_INTERVAL);
      };
    } catch (err) {
      console.error('[Workflow SSE] Failed to connect:', err);
    }
  }

  /**
   * Unsubscribe from workflow events
   */
  unsubscribe(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    this.currentMissionId = null;
    this.statusHandlers.forEach(handler => handler('disconnected'));
  }

  /**
   * Handle incoming workflow event
   */
  private handleWorkflowEvent(data: Record<string, unknown>): void {
    const eventType = data.event_type as string || data.type as string;
    const payload = data.payload as Record<string, unknown> || data;
    const timestamp = data.timestamp as string || new Date().toISOString();
    const runId = data.run_id as string || '';

    // Create trace entry for all events
    const trace: TraceEntry = {
      id: `trace-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      timestamp,
      type: eventType as TraceEntry['type'],
      nodeId: payload.id as string || payload.agent_id as string || '',
      message: this.formatTraceMessage(eventType, payload),
      metadata: payload,
    };
    this.traceHandlers.forEach(handler => handler(trace));

    // Handle specific event types
    switch (eventType) {
      case 'agent_started': {
        const agent: AgentRunNode = {
          id: payload.id as string || `agent-${Date.now()}`,
          type: NodeType.AGENT_RUN,
          label: payload.agent_name as string || 'Unknown Agent',
          status: 'running',
          metadata: {
            timestamp,
            phase: payload.phase as string,
            source: 'workflow'
          },
          data: {
            agentName: payload.agent_name as string || 'Unknown',
            phase: (payload.phase as any) || 'OSINT',
            startTime: timestamp,
            model: payload.model as string
          }
        };
        this.agentStartedHandlers.forEach(handler => handler(agent));
        break;
      }

      case 'agent_finished': {
        const agentId = payload.id as string || payload.agent_id as string;
        const status = (payload.status as string) === 'error' ? 'error' : 'completed';
        const latency = payload.latency as number || payload.duration as number;
        this.agentFinishedHandlers.forEach(handler =>
          handler(agentId, status as WorkflowNodeStatus, latency)
        );
        break;
      }

      case 'tool_called': {
        const tool: ToolCallNode = {
          id: payload.id as string || `tool-${Date.now()}`,
          type: NodeType.TOOL_CALL,
          label: payload.tool_name as string || payload.tool as string || 'Unknown Tool',
          status: 'running',
          metadata: {
            timestamp,
            source: payload.agent_id as string
          },
          data: {
            toolName: payload.tool_name as string || payload.tool as string || 'Unknown',
            agentId: payload.agent_id as string || '',
            args: JSON.stringify(payload.args || payload.arguments || {}),
            startTime: timestamp,
            inputHash: payload.input_hash as string
          }
        };
        this.toolCalledHandlers.forEach(handler => handler(tool));
        break;
      }

      case 'tool_finished': {
        const toolId = payload.id as string || payload.tool_id as string;
        const duration = payload.duration as number || 0;
        const outcome = (payload.outcome as string) === 'failure' ? 'failure' : 'success';
        this.toolFinishedHandlers.forEach(handler =>
          handler(toolId, duration, outcome)
        );
        break;
      }

      case 'node_added':
      case 'node_updated': {
        // Handle asset mutations from regular graph events
        const node = payload.node as Record<string, unknown>;
        if (node && ['AGENT_RUN', 'TOOL_CALL', 'LLM_REASONING'].includes(node.type as string)) {
          this.handleWorkflowNodeEvent(node);
        }
        break;
      }
    }
  }

  /**
   * Handle workflow node from graph events
   */
  private handleWorkflowNodeEvent(node: Record<string, unknown>): void {
    const type = node.type as string;
    const props = node.properties as Record<string, unknown> || {};

    switch (type) {
      case 'AGENT_RUN': {
        const agent: AgentRunNode = {
          id: node.id as string,
          type: NodeType.AGENT_RUN,
          label: props.agent_name as string || 'Unknown Agent',
          status: props.status as WorkflowNodeStatus || 'pending',
          metadata: {
            timestamp: props.start_time as string || new Date().toISOString(),
            phase: props.phase as string,
          },
          data: {
            agentName: props.agent_name as string || 'Unknown',
            phase: (props.phase as any) || 'OSINT',
            startTime: props.start_time as string,
            endTime: props.end_time as string,
            duration: props.duration as number,
            tokens: props.tokens as number
          }
        };
        this.agentStartedHandlers.forEach(handler => handler(agent));
        break;
      }

      case 'TOOL_CALL': {
        const tool: ToolCallNode = {
          id: node.id as string,
          type: NodeType.TOOL_CALL,
          label: props.tool as string || 'Unknown Tool',
          status: props.status as WorkflowNodeStatus || 'pending',
          metadata: {
            timestamp: props.start_time as string || new Date().toISOString(),
            source: props.agent_id as string
          },
          data: {
            toolName: props.tool as string || 'Unknown',
            agentId: props.agent_id as string || '',
            args: JSON.stringify(props.args || {}),
            startTime: props.start_time as string,
            endTime: props.end_time as string,
            duration: props.duration as number,
            result: JSON.stringify(props.result || {}),
            error: props.error as string
          }
        };
        this.toolCalledHandlers.forEach(handler => handler(tool));
        break;
      }

      default: {
        // Handle regular Asset nodes (SUBDOMAIN, SERVICE, VULNERABILITY, etc)
        const originId = props.origin_agent_id || props.origin_tool_id || props.parent_id;

        if (originId) {
          const asset = {
            id: node.id as string,
            type: type,
            originId: originId as string,
            properties: props
          };
          this.assetProducedHandlers.forEach(handler => handler(asset));
        }
        break;
      }
    }
  }

  // New handler for asset production
  onAssetProduced(handler: (asset: { id: string, type: string, originId: string, properties: any }) => void): () => void {
    this.assetProducedHandlers.add(handler);
    return () => this.assetProducedHandlers.delete(handler);
  }

  private assetProducedHandlers: Set<(asset: { id: string, type: string, originId: string, properties: any }) => void> = new Set();

  /**
   * Format trace message for display
   */
  private formatTraceMessage(eventType: string, payload: Record<string, unknown>): string {
    switch (eventType) {
      case 'agent_started':
        return `Agent ${payload.agent_name || 'Unknown'} started (phase: ${payload.phase || 'N/A'})`;
      case 'agent_finished':
        return `Agent ${payload.agent_name || payload.agent_id || 'Unknown'} finished (${payload.status || 'completed'})`;
      case 'tool_called':
        return `Tool ${payload.tool_name || payload.tool || 'Unknown'} called`;
      case 'tool_finished':
        return `Tool ${payload.tool_name || payload.tool_id || 'Unknown'} finished (${payload.outcome || 'success'})`;
      case 'asset_mutation':
        return `Asset ${payload.node_id || 'Unknown'} mutated`;
      default:
        return `Event: ${eventType}`;
    }
  }

  /**
   * Get workflow snapshot (nodes and edges)
   */
  async getWorkflowSnapshot(missionId: string): Promise<{
    agents: AgentRunNode[];
    tools: ToolCallNode[];
    edges: WorkflowEdge[];
  }> {
    const response = await graphqlClient.query<{
      workflowNodes: Array<{ id: string; type: string; properties: Record<string, unknown> }>;
    }>(WORKFLOW_QUERIES.GET_WORKFLOW_NODES, { missionId });

    const agents: AgentRunNode[] = [];
    const tools: ToolCallNode[] = [];

    if (response.success && response.data?.workflowNodes) {
      for (const node of response.data.workflowNodes) {
        const props = node.properties || {};

        if (node.type === 'AGENT_RUN') {
          agents.push({
            id: node.id,
            type: NodeType.AGENT_RUN,
            label: props.agent_name as string || 'Unknown Agent',
            status: props.status as WorkflowNodeStatus || 'pending',
            metadata: {
              timestamp: props.start_time as string || new Date().toISOString(),
              phase: props.phase as string
            },
            data: {
              agentName: props.agent_name as string || 'Unknown',
              phase: (props.phase as any) || 'OSINT',
              startTime: props.start_time as string,
              endTime: props.end_time as string,
              duration: props.duration as number,
              tokens: props.tokens as number
            }
          });
        } else if (node.type === 'TOOL_CALL') {
          tools.push({
            id: node.id,
            type: NodeType.TOOL_CALL,
            label: props.tool as string || 'Unknown Tool',
            status: props.status as WorkflowNodeStatus || 'pending',
            metadata: {
              timestamp: props.start_time as string || new Date().toISOString(),
              source: props.agent_id as string
            },
            data: {
              toolName: props.tool as string || 'Unknown',
              agentId: props.agent_id as string || '',
              args: JSON.stringify(props.args || {}),
              startTime: props.start_time as string,
              endTime: props.end_time as string,
              duration: props.duration as number,
              result: JSON.stringify(props.result || {}),
              error: props.error as string
            }
          });
        }
      }
    }

    // TODO: Query edges separately if needed
    return { agents, tools, edges: [] };
  }

  // Event subscription methods
  onAgentStarted(handler: AgentStartedHandler): () => void {
    this.agentStartedHandlers.add(handler);
    return () => this.agentStartedHandlers.delete(handler);
  }

  onAgentFinished(handler: AgentFinishedHandler): () => void {
    this.agentFinishedHandlers.add(handler);
    return () => this.agentFinishedHandlers.delete(handler);
  }

  onToolCalled(handler: ToolCalledHandler): () => void {
    this.toolCalledHandlers.add(handler);
    return () => this.toolCalledHandlers.delete(handler);
  }

  onToolFinished(handler: ToolFinishedHandler): () => void {
    this.toolFinishedHandlers.add(handler);
    return () => this.toolFinishedHandlers.delete(handler);
  }

  onTrace(handler: TraceHandler): () => void {
    this.traceHandlers.add(handler);
    return () => this.traceHandlers.delete(handler);
  }

  onStatusChange(handler: StatusChangeHandler): () => void {
    this.statusHandlers.add(handler);
    return () => this.statusHandlers.delete(handler);
  }

  /**
   * Cleanup
   */
  cleanup(): void {
    this.unsubscribe();
    this.agentStartedHandlers.clear();
    this.agentFinishedHandlers.clear();
    this.toolCalledHandlers.clear();
    this.toolFinishedHandlers.clear();
    this.traceHandlers.clear();
    this.statusHandlers.clear();
  }
}

// Singleton instance
export const WorkflowService = new WorkflowServiceClass();
