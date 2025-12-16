/**
 * Stores Index
 * Central export for all Zustand stores
 */

export {
  useMissionStore,
  selectCurrentMission,
  selectMissionStatus,
  selectLogs,
  selectConnectionStatus as selectMissionConnectionStatus,
  selectIsLoading as selectMissionIsLoading,
  selectError as selectMissionError,
} from './missionStore';

export {
  useGraphStore,
  selectNodes,
  selectNodesArray,
  selectEdges,
  selectConnectionStatus as selectGraphConnectionStatus,
  selectSelectedNode,
  selectNodeCount,
  selectEdgeCount,
  selectNodeStats,
} from './graphStore';

export {
  useUIStore,
  selectActiveTab,
  selectLogPanelExpanded,
  selectNotifications,
} from './uiStore';
export type { ViewTab, SidebarView } from './uiStore';

export {
  useWorkflowStore,
  selectAgentRuns,
  selectToolCalls,
  selectEdges as selectWorkflowEdges,
  selectTraces,
} from './workflowStore';
export type {
  AgentRunNode,
  ToolCallNode,
  TraceLogEntry,
  ReplayMode,
  WorkflowState,
} from './workflowStore';
