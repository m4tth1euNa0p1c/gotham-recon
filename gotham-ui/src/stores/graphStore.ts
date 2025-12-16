/**
 * Graph Store
 * Zustand store for graph state management
 */

import { create } from 'zustand';
import { devtools, subscribeWithSelector } from 'zustand/middleware';
import {
  GraphService,
  GraphNode,
  GraphEdge,
  NodeType,
  ConnectionStatus
} from '@/services';

interface GraphState {
  // Graph data
  nodes: Map<string, GraphNode>;
  edges: GraphEdge[];

  // Loading states
  isLoading: boolean;
  error: string | null;

  // Connection status
  connectionStatus: ConnectionStatus;

  // Selected node
  selectedNodeId: string | null;

  // Filters
  visibleNodeTypes: NodeType[];

  // Actions
  fetchGraph: (missionId: string) => Promise<void>;
  subscribe: (missionId: string) => void;
  unsubscribe: () => void;
  addNode: (node: GraphNode) => void;
  updateNode: (node: GraphNode) => void;
  removeNode: (nodeId: string) => void;
  addEdge: (edge: GraphEdge) => void;
  removeEdge: (fromNode: string, toNode: string) => void;
  setSelectedNode: (nodeId: string | null) => void;
  setVisibleNodeTypes: (types: NodeType[]) => void;
  setConnectionStatus: (status: ConnectionStatus) => void;
  getNodesArray: () => GraphNode[];
  getFilteredNodes: () => GraphNode[];
  reset: () => void;
}

const ALL_NODE_TYPES: NodeType[] = [
  NodeType.DOMAIN,
  NodeType.SUBDOMAIN,
  NodeType.IP,
  NodeType.HTTP_SERVICE,
  NodeType.ENDPOINT,
  NodeType.PARAMETER,
  NodeType.DNS_RECORD,
  NodeType.TECHNOLOGY,
  NodeType.CREDENTIAL,
  NodeType.FINDING,
  NodeType.HYPOTHESIS,
  NodeType.VULNERABILITY,
  NodeType.ATTACK_PATH,
  NodeType.AGENT_RUN,
  NodeType.TOOL_CALL,
  NodeType.LLM_REASONING,
];

const initialState = {
  nodes: new Map<string, GraphNode>(),
  edges: [],
  isLoading: false,
  error: null,
  connectionStatus: 'disconnected' as ConnectionStatus,
  selectedNodeId: null,
  visibleNodeTypes: ALL_NODE_TYPES,
};

export const useGraphStore = create<GraphState>()(
  devtools(
    subscribeWithSelector((set, get) => ({
      ...initialState,

      fetchGraph: async (missionId: string) => {
        set({ isLoading: true, error: null });

        try {
          const snapshot = await GraphService.getGraphSnapshot(missionId);

          const nodesMap = new Map<string, GraphNode>();
          snapshot.nodes.forEach(node => nodesMap.set(node.id, node));

          set({
            nodes: nodesMap,
            edges: snapshot.edges,
            isLoading: false,
          });
        } catch (error) {
          set({ isLoading: false, error: (error as Error).message });
        }
      },

      subscribe: (missionId: string) => {
        // Set up event handlers
        GraphService.onNodeAdded((node) => {
          get().addNode(node);
        });

        GraphService.onNodeUpdated((node) => {
          get().updateNode(node);
        });

        GraphService.onNodeDeleted((node) => {
          get().removeNode(node.id);
        });

        GraphService.onEdgeAdded((edge) => {
          get().addEdge(edge);
        });

        GraphService.onEdgeDeleted((edge) => {
          get().removeEdge(edge.fromNode, edge.toNode);
        });

        GraphService.onStatusChange((status) => {
          get().setConnectionStatus(status);
        });

        // Subscribe to WebSocket
        GraphService.subscribe(missionId);
      },

      unsubscribe: () => {
        GraphService.unsubscribe();
        set({ connectionStatus: 'disconnected' });
      },

      addNode: (node: GraphNode) => {
        set(state => {
          const newNodes = new Map(state.nodes);
          newNodes.set(node.id, node);
          return { nodes: newNodes };
        });
      },

      updateNode: (node: GraphNode) => {
        set(state => {
          const newNodes = new Map(state.nodes);
          const existing = newNodes.get(node.id);
          if (existing) {
            newNodes.set(node.id, { ...existing, ...node });
          } else {
            newNodes.set(node.id, node);
          }
          return { nodes: newNodes };
        });
      },

      removeNode: (nodeId: string) => {
        set(state => {
          const newNodes = new Map(state.nodes);
          newNodes.delete(nodeId);

          // Also remove edges connected to this node
          const newEdges = state.edges.filter(
            edge => edge.fromNode !== nodeId && edge.toNode !== nodeId
          );

          return { nodes: newNodes, edges: newEdges };
        });
      },

      addEdge: (edge: GraphEdge) => {
        set(state => {
          // Check if edge already exists (using full key: fromNode + relation + toNode)
          const exists = state.edges.some(
            e => e.fromNode === edge.fromNode &&
                 e.relation === edge.relation &&
                 e.toNode === edge.toNode
          );

          if (exists) return state;

          return { edges: [...state.edges, edge] };
        });
      },

      removeEdge: (fromNode: string, toNode: string) => {
        set(state => ({
          edges: state.edges.filter(
            e => !(e.fromNode === fromNode && e.toNode === toNode)
          ),
        }));
      },

      setSelectedNode: (nodeId: string | null) => {
        set({ selectedNodeId: nodeId });
      },

      setVisibleNodeTypes: (types: NodeType[]) => {
        set({ visibleNodeTypes: types });
      },

      setConnectionStatus: (status: ConnectionStatus) => {
        set({ connectionStatus: status });
      },

      getNodesArray: () => {
        return Array.from(get().nodes.values());
      },

      getFilteredNodes: () => {
        const { nodes, visibleNodeTypes } = get();
        return Array.from(nodes.values()).filter(node =>
          visibleNodeTypes.includes(node.type)
        );
      },

      reset: () => {
        GraphService.cleanup();
        set({
          ...initialState,
          nodes: new Map(),
        });
      },
    })),
    { name: 'graph-store' }
  )
);

// Selectors
export const selectNodes = (state: GraphState) => state.nodes;
export const selectNodesArray = (state: GraphState) => Array.from(state.nodes.values());
export const selectEdges = (state: GraphState) => state.edges;
export const selectConnectionStatus = (state: GraphState) => state.connectionStatus;
export const selectSelectedNode = (state: GraphState) => {
  if (!state.selectedNodeId) return null;
  return state.nodes.get(state.selectedNodeId) || null;
};
export const selectNodeCount = (state: GraphState) => state.nodes.size;
export const selectEdgeCount = (state: GraphState) => state.edges.length;

// Statistics selector
export const selectNodeStats = (state: GraphState) => {
  const stats: Partial<Record<NodeType, number>> = {
    [NodeType.SUBDOMAIN]: 0,
    [NodeType.HTTP_SERVICE]: 0,
    [NodeType.ENDPOINT]: 0,
    [NodeType.PARAMETER]: 0,
    [NodeType.DNS_RECORD]: 0,
    [NodeType.HYPOTHESIS]: 0,
    [NodeType.VULNERABILITY]: 0,
    [NodeType.ATTACK_PATH]: 0,
    [NodeType.AGENT_RUN]: 0,
    [NodeType.TOOL_CALL]: 0,
    [NodeType.LLM_REASONING]: 0,
  };

  state.nodes.forEach(node => {
    if (stats[node.type] !== undefined) {
      stats[node.type]!++;
    }
  });

  return stats;
};
