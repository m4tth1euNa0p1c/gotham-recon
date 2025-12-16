/**
 * useGraph Hook
 * Provides graph data and real-time updates to components
 */

import { useCallback, useEffect, useMemo } from 'react';
import { useGraphStore, selectNodeStats } from '@/stores';
import { NodeType, GraphNode, GraphEdge } from '@/services';

export interface UseGraphOptions {
  autoSubscribe?: boolean;
  autoFetch?: boolean;
}

export function useGraph(missionId?: string, options: UseGraphOptions = {}) {
  const { autoSubscribe = true, autoFetch = true } = options;

  const {
    nodes,
    edges,
    isLoading,
    error,
    connectionStatus,
    selectedNodeId,
    visibleNodeTypes,
    fetchGraph,
    subscribe,
    unsubscribe,
    setSelectedNode,
    setVisibleNodeTypes,
    getNodesArray,
    getFilteredNodes,
  } = useGraphStore();

  // Auto-fetch and subscribe when missionId changes
  useEffect(() => {
    if (missionId) {
      if (autoFetch) {
        fetchGraph(missionId);
      }

      if (autoSubscribe) {
        subscribe(missionId);
      }
    }

    return () => {
      if (autoSubscribe) {
        unsubscribe();
      }
    };
  }, [missionId, autoFetch, autoSubscribe, fetchGraph, subscribe, unsubscribe]);

  // Get nodes as array (memoized)
  const nodesArray = useMemo(() => getNodesArray(), [nodes, getNodesArray]);

  // Get filtered nodes (memoized)
  const filteredNodes = useMemo(() => getFilteredNodes(), [nodes, visibleNodeTypes, getFilteredNodes]);

  // Get selected node
  const selectedNode = useMemo(() => {
    if (!selectedNodeId) return null;
    return nodes.get(selectedNodeId) || null;
  }, [nodes, selectedNodeId]);

  // Stats
  const stats = useGraphStore(selectNodeStats);

  // Toggle node type visibility
  const toggleNodeType = useCallback(
    (type: NodeType) => {
      const current = visibleNodeTypes;
      const newTypes = current.includes(type)
        ? current.filter(t => t !== type)
        : [...current, type];
      setVisibleNodeTypes(newTypes);
    },
    [visibleNodeTypes, setVisibleNodeTypes]
  );

  // Show all node types
  const showAllNodeTypes = useCallback(() => {
    const allTypes: NodeType[] = [
      NodeType.SUBDOMAIN,
      NodeType.HTTP_SERVICE,
      NodeType.ENDPOINT,
      NodeType.PARAMETER,
      NodeType.HYPOTHESIS,
      NodeType.VULNERABILITY,
      NodeType.ATTACK_PATH,
      NodeType.AGENT_RUN,
      NodeType.TOOL_CALL,
      NodeType.LLM_REASONING,
    ];
    setVisibleNodeTypes(allTypes);
  }, [setVisibleNodeTypes]);

  // Get nodes by type
  const getNodesByType = useCallback(
    (type: NodeType): GraphNode[] => {
      return nodesArray.filter(node => node.type === type);
    },
    [nodesArray]
  );

  // Get edges for a specific node
  const getNodeEdges = useCallback(
    (nodeId: string): GraphEdge[] => {
      return edges.filter(edge => edge.fromNode === nodeId || edge.toNode === nodeId);
    },
    [edges]
  );

  // Get connected nodes for a specific node
  const getConnectedNodes = useCallback(
    (nodeId: string): GraphNode[] => {
      const connectedIds = new Set<string>();

      edges.forEach(edge => {
        if (edge.fromNode === nodeId) connectedIds.add(edge.toNode);
        if (edge.toNode === nodeId) connectedIds.add(edge.fromNode);
      });

      return nodesArray.filter(node => connectedIds.has(node.id));
    },
    [edges, nodesArray]
  );

  return {
    // State
    nodes: nodesArray,
    filteredNodes,
    edges,
    isLoading,
    error,
    connectionStatus,
    selectedNode,
    visibleNodeTypes,

    // Stats
    stats,
    nodeCount: nodes.size,
    edgeCount: edges.length,

    // Selection
    selectNode: setSelectedNode,
    clearSelection: () => setSelectedNode(null),

    // Filtering
    toggleNodeType,
    showAllNodeTypes,
    setVisibleNodeTypes,

    // Queries
    getNodesByType,
    getNodeEdges,
    getConnectedNodes,

    // Actions
    refresh: () => missionId && fetchGraph(missionId),
    subscribeToUpdates: () => missionId && subscribe(missionId),
    unsubscribeFromUpdates: unsubscribe,
  };
}

/**
 * useGraphNode Hook
 * For working with a specific node
 */
export function useGraphNode(nodeId: string | null) {
  const { nodes, edges } = useGraphStore();

  const node = useMemo(() => {
    if (!nodeId) return null;
    return nodes.get(nodeId) || null;
  }, [nodes, nodeId]);

  const connectedEdges = useMemo(() => {
    if (!nodeId) return [];
    return edges.filter(edge => edge.fromNode === nodeId || edge.toNode === nodeId);
  }, [edges, nodeId]);

  const connectedNodes = useMemo(() => {
    if (!nodeId) return [];

    const connectedIds = new Set<string>();
    connectedEdges.forEach(edge => {
      if (edge.fromNode === nodeId) connectedIds.add(edge.toNode);
      if (edge.toNode === nodeId) connectedIds.add(edge.fromNode);
    });

    return Array.from(connectedIds)
      .map(id => nodes.get(id))
      .filter((n): n is GraphNode => n !== undefined);
  }, [connectedEdges, nodeId, nodes]);

  return {
    node,
    connectedEdges,
    connectedNodes,
    incomingCount: connectedEdges.filter(e => e.toNode === nodeId).length,
    outgoingCount: connectedEdges.filter(e => e.fromNode === nodeId).length,
  };
}
