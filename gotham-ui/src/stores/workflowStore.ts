/**
 * Workflow Store
 * Manages workflow visualization state (agents, tools, traces)
 */

import { create } from 'zustand';
import { devtools, subscribeWithSelector } from 'zustand/middleware';
import {
  NodeType,
  EdgeType,
  WorkflowEvent,
  WorkflowEventType,
  DomainNode,
  DomainEdge,
  MissionPhase,
  WorkflowNodeStatus,
  TraceEntry // Import locally if needed or remove definition
} from '@/services/types';

export interface AgentRunNode extends DomainNode {
  type: NodeType.AGENT_RUN;
  status: WorkflowNodeStatus;
  data: {
    agentName: string;
    phase: MissionPhase;
    startTime?: string;
    endTime?: string;
    duration?: number;
    model?: string;
    tokens?: number;
  }
}

export interface ToolCallNode extends DomainNode {
  type: NodeType.TOOL_CALL;
  status: WorkflowNodeStatus;
  data: {
    toolName: string;
    agentId: string;
    args: string;
    result?: string;
    error?: string;
    startTime?: string;
    endTime?: string;
    duration?: number;
    inputHash?: string;
    outcome?: 'success' | 'failure';
    producedAssets?: string[]; // IDs of assets produced by this tool
  }
}

// Asset node produced by agents/tools
export interface AssetNode {
  id: string;
  type: string; // ENDPOINT, VULNERABILITY, HYPOTHESIS, SUBDOMAIN, etc.
  label: string;
  originAgentId?: string;
  originToolId?: string;
  properties: Record<string, unknown>;
  createdAt?: string;
}

export interface TraceLogEntry {
  id: string;
  type: string;
  nodeId?: string;
  message: string;
  timestamp: string;
  data?: Record<string, unknown>;
}

export type ReplayMode = 'live' | 'paused' | 'replay';

export interface WorkflowState {
  // Data
  agentRuns: Map<string, AgentRunNode>;
  toolCalls: Map<string, ToolCallNode>;
  producedAssets: Map<string, AssetNode>; // Assets with origin tracking
  edges: DomainEdge[];
  traces: TraceLogEntry[];

  // Replay State
  replayMode: ReplayMode;
  replaySpeed: number; // 1x, 2x, 4x
  replayIndex: number;
  replayEvents: WorkflowEvent[];

  // UI State
  selectedNodeId: string | null;
  layout: any | null; // Cytoscape layout options
  connectionStatus: 'disconnected' | 'connecting' | 'connected' | 'error';

  // Layer visibility
  showAgents: boolean;
  showTools: boolean;
  showAssets: boolean;

  // Actions
  handleEvent: (event: WorkflowEvent) => void;
  subscribe: (missionId: string) => void;
  unsubscribe: () => void;
  selectNode: (id: string | null) => void;
  setLayout: (layout: any) => void;
  updateNodePosition: (nodeId: string, x: number, y: number) => void;
  setConnectionStatus: (status: WorkflowState['connectionStatus']) => void;
  toggleAgents: () => void;
  toggleTools: () => void;
  toggleAssets: () => void;

  // Agent/Tool mutation actions
  addAgentRun: (agent: Omit<AgentRunNode, 'type'> & { type?: string }) => void;
  updateAgentStatus: (agentId: string, status: WorkflowNodeStatus, endTime?: string, latency?: number) => void;
  addToolCall: (tool: Omit<ToolCallNode, 'type'> & { type?: string }) => void;
  updateToolCall: (toolId: string, updates: Partial<ToolCallNode['data']>) => void;

  // Asset tracking
  addProducedAsset: (asset: AssetNode) => void;
  linkAssetToOrigin: (assetId: string, originId: string, originType: 'agent' | 'tool') => void;

  // Replay Actions
  setReplayMode: (mode: ReplayMode) => void;
  setReplaySpeed: (speed: number) => void;
  stepForward: () => void;
  stepBackward: () => void;

  reset: () => void;

  // Force complete all running items (for mission completion)
  forceCompleteAll: () => void;
}

const initialState = {
  agentRuns: new Map<string, AgentRunNode>(),
  toolCalls: new Map<string, ToolCallNode>(),
  producedAssets: new Map<string, AssetNode>(),
  edges: [] as DomainEdge[],
  traces: [] as TraceLogEntry[],

  replayMode: 'live' as ReplayMode,
  replaySpeed: 1,
  replayIndex: 0,
  replayEvents: [] as WorkflowEvent[],

  selectedNodeId: null,
  layout: null,
  connectionStatus: 'disconnected' as const,
  showAgents: true,
  showTools: true,
  showAssets: true,
};

// Helper to add trace entry
function createTrace(type: string, message: string, nodeId?: string, data?: Record<string, unknown>): TraceLogEntry {
  return {
    id: `trace-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    type,
    nodeId,
    message,
    timestamp: new Date().toISOString(),
    data
  };
}

export const useWorkflowStore = create<WorkflowState>()(
  devtools(
    subscribeWithSelector((set, get) => ({
      ...initialState,

      subscribe: (missionId: string) => {
        // TODO: Import WorkflowService to subscribe
        // For now, we assume WorkflowService emits events that we map to handleEvent
        // Ideally WorkflowService should have a generic onEvent or we map specific callbacks

        // Placeholder for subscription logic
        // WorkflowService.subscribe(missionId);
        // WorkflowService.onEvent((event) => get().handleEvent(event));
      },

      unsubscribe: () => {
        // WorkflowService.unsubscribe();
        set({ connectionStatus: 'disconnected' });
      },

      handleEvent: (event: WorkflowEvent) => {
        const { type, data, timestamp } = event;

        switch (type) {
          case 'agent_started':
            set(state => {
              const newAgents = new Map(state.agentRuns);
              const agentId = data.run_id || data.id;

              newAgents.set(agentId, {
                id: agentId,
                type: NodeType.AGENT_RUN,
                label: data.agent_name || 'Unknown Agent',
                metadata: { timestamp, phase: data.phase },
                status: 'running',
                data: {
                  agentName: data.agent_name,
                  phase: (data.phase as MissionPhase) || MissionPhase.OSINT,
                  startTime: timestamp,
                  model: data.model
                }
              });

              const trace = createTrace('agent_started', `Agent ${data.agent_name} started (${data.phase})`, agentId, data);
              return { agentRuns: newAgents, traces: [...state.traces, trace] };
            });
            break;

          case 'agent_finished':
            set(state => {
              const newAgents = new Map(state.agentRuns);
              const agentId = data.run_id || data.id;
              const agent = newAgents.get(agentId);

              if (agent) {
                newAgents.set(agentId, {
                  ...agent,
                  status: data.status === 'success' ? 'completed' : 'error',
                  data: {
                    ...agent.data,
                    endTime: timestamp,
                    duration: data.duration,
                    tokens: data.usage?.total_tokens
                  }
                });
              }

              const trace = createTrace('agent_finished', `Agent ${data.agent_name || agentId} finished (${data.status})`, agentId, data);
              return { agentRuns: newAgents, traces: [...state.traces, trace] };
            });
            break;

          case 'tool_called':
            set(state => {
              const newTools = new Map(state.toolCalls);
              const toolId = data.call_id || data.id;

              newTools.set(toolId, {
                id: toolId,
                type: NodeType.TOOL_CALL,
                label: data.tool_name,
                metadata: { timestamp, source: data.agent_id },
                status: 'running',
                data: {
                  toolName: data.tool_name,
                  agentId: data.agent_id,
                  args: JSON.stringify(data.arguments),
                  startTime: timestamp
                }
              });

              // Add edge from Agent -> Tool
              const newEdges = [...state.edges];
              if (data.agent_id) {
                newEdges.push({
                  id: `${data.agent_id}_uses_${toolId}`,
                  source: data.agent_id,
                  target: toolId,
                  type: EdgeType.USES_TOOL
                });
              }

              const trace = createTrace('tool_called', `Tool ${data.tool_name} called`, toolId, data);
              return { toolCalls: newTools, edges: newEdges, traces: [...state.traces, trace] };
            });
            break;

          case 'tool_finished':
            set(state => {
              const newTools = new Map(state.toolCalls);
              const toolId = data.call_id || data.id;
              const tool = newTools.get(toolId);

              if (tool) {
                newTools.set(toolId, {
                  ...tool,
                  status: data.status === 'error' ? 'error' : 'completed',
                  data: {
                    ...tool.data,
                    endTime: timestamp,
                    duration: data.duration,
                    result: JSON.stringify(data.result),
                    error: data.error
                  }
                });
              }

              const trace = createTrace('tool_finished', `Tool ${data.tool_name || toolId} finished`, toolId, data);
              return { toolCalls: newTools, traces: [...state.traces, trace] };
            });
            break;

          case 'asset_mutation':
          case 'node_added':
          case 'NODE_ADDED':
            set(state => {
              const node = data.node || data;
              const props = node.properties || node;
              const nodeType = node.type || props.type;

              // Only track assets with origin information
              const originAgentId = props.origin_agent_id || props.agent_id || props.discovered_by_agent;
              const originToolId = props.origin_tool_id || props.tool_id || props.discovered_by_tool;

              // Skip workflow nodes (AGENT_RUN, TOOL_CALL)
              if (['AGENT_RUN', 'TOOL_CALL', 'LLM_REASONING'].includes(nodeType)) {
                const trace = createTrace('asset_mutation', `Workflow node: ${nodeType}`, undefined, data);
                return { traces: [...state.traces, trace] };
              }

              // Track asset with origin
              if (originAgentId || originToolId) {
                const newAssets = new Map(state.producedAssets);
                const newEdges = [...state.edges];

                const assetNode: AssetNode = {
                  id: node.id,
                  type: nodeType,
                  label: props.name || props.subdomain || props.path || props.url || node.id.substring(0, 16),
                  originAgentId,
                  originToolId,
                  properties: props,
                  createdAt: timestamp,
                };

                newAssets.set(node.id, assetNode);

                // Create PRODUCES edge from origin to asset
                const originId = originToolId || originAgentId;
                if (originId) {
                  const edgeExists = newEdges.some(
                    e => e.source === originId && e.target === node.id && e.type === EdgeType.PRODUCES
                  );
                  if (!edgeExists) {
                    newEdges.push({
                      id: `${originId}_produces_${node.id}`,
                      source: originId,
                      target: node.id,
                      type: EdgeType.PRODUCES,
                      label: 'produces'
                    });
                  }

                  // Also update the tool's producedAssets list
                  if (originToolId) {
                    const newTools = new Map(state.toolCalls);
                    const tool = newTools.get(originToolId);
                    if (tool) {
                      const producedAssets = tool.data.producedAssets || [];
                      if (!producedAssets.includes(node.id)) {
                        newTools.set(originToolId, {
                          ...tool,
                          data: {
                            ...tool.data,
                            producedAssets: [...producedAssets, node.id]
                          }
                        });
                        return {
                          producedAssets: newAssets,
                          edges: newEdges,
                          toolCalls: newTools,
                          traces: [...state.traces, createTrace('asset_mutation', `Asset ${nodeType}: ${assetNode.label} (from ${originToolId})`, node.id, data)]
                        };
                      }
                    }
                  }
                }

                const trace = createTrace('asset_mutation', `Asset ${nodeType}: ${assetNode.label}`, node.id, data);
                return { producedAssets: newAssets, edges: newEdges, traces: [...state.traces, trace] };
              }

              const trace = createTrace('asset_mutation', `Asset ${data.operation || 'added'}: ${nodeType}`, undefined, data);
              return { traces: [...state.traces, trace] };
            });
            break;

          // Handle mission completion - mark all running items as completed
          case 'mission_completed':
          case 'mission_finished':
          case 'MISSION_COMPLETED':
          case 'MISSION_FINISHED':
            set(state => {
              const newAgents = new Map(state.agentRuns);
              const newTools = new Map(state.toolCalls);

              // Mark all running agents as completed
              newAgents.forEach((agent, id) => {
                if (agent.status === 'running') {
                  newAgents.set(id, {
                    ...agent,
                    status: 'completed',
                    data: {
                      ...agent.data,
                      endTime: timestamp,
                    }
                  });
                }
              });

              // Mark all running tools as completed
              newTools.forEach((tool, id) => {
                if (tool.status === 'running') {
                  newTools.set(id, {
                    ...tool,
                    status: 'completed',
                    data: {
                      ...tool.data,
                      endTime: timestamp,
                    }
                  });
                }
              });

              const trace = createTrace('mission_completed', `Mission completed`, undefined, data);
              console.log(`[WorkflowStore] Mission completed - marked ${newAgents.size} agents and ${newTools.size} tools as completed`);
              return { agentRuns: newAgents, toolCalls: newTools, traces: [...state.traces, trace] };
            });
            break;

          // P0.5-FIX: Handle initial snapshot from SSE
          case 'SNAPSHOT':
          case 'snapshot':
            set(state => {
              const newAgents = new Map(state.agentRuns);
              const newTools = new Map(state.toolCalls);
              const newEdges = [...state.edges];

              // Process nodes from snapshot
              const nodes = data.nodes || [];
              for (const node of nodes) {
                if (node.type === 'AGENT_RUN') {
                  const props = node.properties || {};
                  // Normalize status: backend sends 'success' for completed agents
                  const normalizedStatus = (props.status === 'completed' || props.status === 'success')
                    ? 'completed'
                    : (props.status === 'running' ? 'running' : (props.end_time ? 'completed' : 'running'));
                  newAgents.set(node.id, {
                    id: node.id,
                    type: NodeType.AGENT_RUN,
                    label: props.agent_name || 'Unknown Agent',
                    metadata: { timestamp: props.start_time, phase: props.phase },
                    status: normalizedStatus,
                    data: {
                      agentName: props.agent_name,
                      phase: (props.phase as MissionPhase) || MissionPhase.OSINT,
                      startTime: props.start_time,
                      endTime: props.end_time,
                      duration: props.duration,
                      model: props.model
                    }
                  });
                } else if (node.type === 'TOOL_CALL') {
                  const props = node.properties || {};
                  // Normalize status: check for 'success' and use end_time as fallback
                  const normalizedStatus = (props.status === 'completed' || props.status === 'success')
                    ? 'completed'
                    : (props.status === 'running' ? 'running' : (props.end_time ? 'completed' : 'running'));
                  newTools.set(node.id, {
                    id: node.id,
                    type: NodeType.TOOL_CALL,
                    label: props.tool_name || props.tool || 'Unknown Tool',
                    metadata: { timestamp: props.start_time, source: props.agent_id },
                    status: normalizedStatus,
                    data: {
                      toolName: props.tool_name || props.tool,
                      agentId: props.agent_id,
                      args: JSON.stringify(props.args || props.arguments || {}),
                      result: props.result ? JSON.stringify(props.result) : undefined,
                      startTime: props.start_time,
                      endTime: props.end_time,
                      duration: props.duration
                    }
                  });
                }
              }

              // Process edges from snapshot
              const edges = data.edges || [];
              for (const edge of edges) {
                if (edge.relation === 'USES_TOOL' || edge.edge_type === 'USES_TOOL') {
                  newEdges.push({
                    id: edge.id || `${edge.from_node}_uses_${edge.to_node}`,
                    source: edge.from_node,
                    target: edge.to_node,
                    type: EdgeType.USES_TOOL,
                    label: 'uses'
                  });
                }
              }

              console.log(`[WorkflowStore] Snapshot loaded: ${newAgents.size} agents, ${newTools.size} tools`);
              return { agentRuns: newAgents, toolCalls: newTools, edges: newEdges };
            });
            break;
        }
      },

      selectNode: (id) => set({ selectedNodeId: id }),
      setLayout: (layout) => set({ layout }),
      updateNodePosition: (nodeId, x, y) => {
        set((state) => {
          if (!state.layout) return state;
          return {
            layout: {
              ...state.layout,
              positions: {
                ...state.layout.positions,
                [nodeId]: { x, y },
              },
            },
          };
        });
      },
      setConnectionStatus: (status) => set({ connectionStatus: status }),
      toggleAgents: () => set((state) => ({ showAgents: !state.showAgents })),
      toggleTools: () => set((state) => ({ showTools: !state.showTools })),
      toggleAssets: () => set((state) => ({ showAssets: !state.showAssets })),

      // Replay Actions Implementation
      setReplayMode: (mode) => set({ replayMode: mode }),
      setReplaySpeed: (speed) => set({ replaySpeed: speed }),
      stepForward: () => set((state) => {
        if (state.replayIndex < state.replayEvents.length - 1) {
          // Logic to apply next event would go here if we were doing true time-travel
          return { replayIndex: state.replayIndex + 1 };
        }
        return state;
      }),
      stepBackward: () => set((state) => {
        if (state.replayIndex > 0) {
          return { replayIndex: state.replayIndex - 1 };
        }
        return state;
      }),

      // Agent/Tool mutation actions
      addAgentRun: (agent) => set((state) => {
        const newAgents = new Map(state.agentRuns);
        const agentNode: AgentRunNode = {
          ...agent,
          type: NodeType.AGENT_RUN,
          status: agent.status || 'running',
        } as AgentRunNode;
        newAgents.set(agent.id, agentNode);
        const trace = createTrace('agent_started', `Agent ${agent.data?.agentName || agent.id} started`, agent.id);
        return { agentRuns: newAgents, traces: [...state.traces, trace] };
      }),

      updateAgentStatus: (agentId, status, endTime, latency) => set((state) => {
        const newAgents = new Map(state.agentRuns);
        const agent = newAgents.get(agentId);
        if (agent) {
          newAgents.set(agentId, {
            ...agent,
            status,
            data: {
              ...agent.data,
              endTime,
              duration: latency,
            },
          });
        }
        const trace = createTrace('agent_finished', `Agent ${agentId} ${status}`, agentId);
        return { agentRuns: newAgents, traces: [...state.traces, trace] };
      }),

  addToolCall: (tool) => set((state) => {
        const newTools = new Map(state.toolCalls);
        const toolNode: ToolCallNode = {
          ...tool,
          type: NodeType.TOOL_CALL,
          status: tool.status || 'running',
        } as ToolCallNode;
        newTools.set(tool.id, toolNode);
        const trace = createTrace('tool_called', `Tool ${tool.data?.toolName || tool.id} called`, tool.id);
        return { toolCalls: newTools, traces: [...state.traces, trace] };
      }),

  updateToolCall: (toolId, updates) => set((state) => {
        const newTools = new Map(state.toolCalls);
        const tool = newTools.get(toolId);
        if (tool) {
          newTools.set(toolId, {
            ...tool,
            status: updates.outcome === 'failure' ? 'error' : 'completed',
            data: {
              ...tool.data,
              ...updates,
            },
          });
        }
        const trace = createTrace('tool_finished', `Tool ${toolId} finished`, toolId);
        return { toolCalls: newTools, traces: [...state.traces, trace] };
      }),

      addProducedAsset: (asset: AssetNode) => set((state) => {
        const newAssets = new Map(state.producedAssets);
        newAssets.set(asset.id, asset);

        const newEdges = [...state.edges];

        // Create PRODUCES edge from origin
        const originId = asset.originToolId || asset.originAgentId;
        if (originId) {
          const edgeExists = newEdges.some(
            e => e.source === originId && e.target === asset.id && e.type === EdgeType.PRODUCES
          );
          if (!edgeExists) {
            newEdges.push({
              id: `${originId}_produces_${asset.id}`,
              source: originId,
              target: asset.id,
              type: EdgeType.PRODUCES,
              label: 'produces'
            });
          }
        }

        return { producedAssets: newAssets, edges: newEdges };
      }),

      linkAssetToOrigin: (assetId: string, originId: string, originType: 'agent' | 'tool') => set((state) => {
        const newAssets = new Map(state.producedAssets);
        const asset = newAssets.get(assetId);

        if (asset) {
          if (originType === 'agent') {
            asset.originAgentId = originId;
          } else {
            asset.originToolId = originId;
          }
          newAssets.set(assetId, asset);
        }

        // Create PRODUCES edge
        const newEdges = [...state.edges];
        const edgeExists = newEdges.some(
          e => e.source === originId && e.target === assetId && e.type === EdgeType.PRODUCES
        );
        if (!edgeExists) {
          newEdges.push({
            id: `${originId}_produces_${assetId}`,
            source: originId,
            target: assetId,
            type: EdgeType.PRODUCES,
            label: 'produces'
          });
        }

        return { producedAssets: newAssets, edges: newEdges };
      }),

      reset: () => set(initialState),

      forceCompleteAll: () => set((state) => {
        const newAgents = new Map(state.agentRuns);
        const newTools = new Map(state.toolCalls);
        const timestamp = new Date().toISOString();

        // Mark all running agents as completed
        newAgents.forEach((agent, id) => {
          if (agent.status === 'running') {
            newAgents.set(id, {
              ...agent,
              status: 'completed',
              data: {
                ...agent.data,
                endTime: agent.data.endTime || timestamp,
              }
            });
          }
        });

        // Mark all running tools as completed
        newTools.forEach((tool, id) => {
          if (tool.status === 'running') {
            newTools.set(id, {
              ...tool,
              status: 'completed',
              data: {
                ...tool.data,
                endTime: tool.data.endTime || timestamp,
              }
            });
          }
        });

        console.log(`[WorkflowStore] Force completed all running items`);
        return { agentRuns: newAgents, toolCalls: newTools };
      }),
    })),
    { name: 'workflow-store' }
  )
);

// Stable Selectors (prevent infinite loops)
export const selectAgentRuns = (state: WorkflowState) => Array.from(state.agentRuns.values());
export const selectToolCalls = (state: WorkflowState) => Array.from(state.toolCalls.values());
export const selectTraces = (state: WorkflowState) => state.traces;
export const selectEdges = (state: WorkflowState) => state.edges;
