"use client";

/**
 * TracePanel
 * Execution trace log panel showing real-time events from workflow execution.
 *
 * Design: Colored left borders per event type, compact entries
 */

import { useMemo, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Activity,
  Clock,
  Cpu,
  Wrench,
  Link,
  ChevronRight,
  Zap,
  Database,
} from "lucide-react";
import { useShallow } from "zustand/react/shallow";
import { useWorkflowStore } from "@/stores/workflowStore";
import type { AgentRunNode, ToolCallNode, TraceLogEntry } from "@/stores/workflowStore";

interface TracePanelProps {
  className?: string;
  maxHeight?: string;
}

// Event type colors - matching mock design
const EVENT_COLORS: Record<string, { border: string; bg: string; icon: string }> = {
  agent_started: { border: "border-l-cyan-500", bg: "bg-cyan-500/5", icon: "text-cyan-400" },
  agent_finished: { border: "border-l-emerald-500", bg: "bg-emerald-500/5", icon: "text-emerald-400" },
  tool_called: { border: "border-l-amber-500", bg: "bg-amber-500/5", icon: "text-amber-400" },
  tool_finished: { border: "border-l-emerald-500", bg: "bg-emerald-500/5", icon: "text-emerald-400" },
  asset_mutation: { border: "border-l-purple-500", bg: "bg-purple-500/5", icon: "text-purple-400" },
  error: { border: "border-l-red-500", bg: "bg-red-500/5", icon: "text-red-400" },
};

const DEFAULT_EVENT_COLORS = { border: "border-l-slate-600", bg: "bg-slate-800/30", icon: "text-slate-500" };

// Format timestamp for display
function formatTime(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

// Format duration
function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
}

// Get icon for trace type
function getTraceIcon(type: string) {
  const colors = EVENT_COLORS[type] || DEFAULT_EVENT_COLORS;
  switch (type) {
    case "agent_started":
      return <Cpu size={12} className={colors.icon} />;
    case "agent_finished":
      return <Zap size={12} className={colors.icon} />;
    case "tool_called":
      return <Wrench size={12} className={colors.icon} />;
    case "tool_finished":
      return <Zap size={12} className={colors.icon} />;
    case "asset_mutation":
      return <Database size={12} className={colors.icon} />;
    case "error":
      return <Activity size={12} className={colors.icon} />;
    default:
      return <ChevronRight size={12} className={colors.icon} />;
  }
}

export default function TracePanel({ className = "", maxHeight = "100%" }: TracePanelProps) {
  // Use useShallow to prevent infinite re-renders when arrays are recreated
  const traces = useWorkflowStore(useShallow((state) => state.traces));
  const agentRunsMap = useWorkflowStore((state) => state.agentRuns);
  const toolCallsMap = useWorkflowStore((state) => state.toolCalls);
  const selectedNodeId = useWorkflowStore((state) => state.selectedNodeId);

  // Memoize the array conversions to avoid creating new arrays on every render
  const agentRuns = useMemo(() => Array.from(agentRunsMap.values()), [agentRunsMap]);
  const toolCalls = useMemo(() => Array.from(toolCallsMap.values()), [toolCallsMap]);

  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new traces
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [traces.length]);

  // Get selected node details
  const selectedNodeDetails = useMemo(() => {
    if (!selectedNodeId) return null;

    // Check if it's an agent
    const agent = agentRuns.find((a) => a.id === selectedNodeId);
    if (agent) {
      return {
        type: "agent" as const,
        data: agent,
        title: agent.data.agentName || agent.label,
        status: agent.status,
        phase: agent.data.phase,
        latency: agent.data.duration,
        duration: undefined as number | undefined,
        tokens: agent.data.tokens,
        startTime: agent.data.startTime,
        endTime: agent.data.endTime,
        agentId: undefined as string | undefined,
        inputHash: undefined as string | undefined,
        outputNodeIds: undefined as string[] | undefined,
      };
    }

    // Check if it's a tool
    const tool = toolCalls.find((t) => t.id === selectedNodeId);
    if (tool) {
      return {
        type: "tool" as const,
        data: tool,
        title: tool.data.toolName || tool.label,
        status: tool.status,
        phase: undefined as string | undefined,
        latency: undefined as number | undefined,
        duration: tool.data.duration,
        tokens: undefined as number | undefined,
        startTime: undefined as string | undefined,
        endTime: undefined as string | undefined,
        agentId: tool.data.agentId,
        inputHash: tool.data.inputHash,
        outputNodeIds: undefined as string[] | undefined,
      };
    }

    return null;
  }, [selectedNodeId, agentRuns, toolCalls]);

  // Filter traces for selected node
  const filteredTraces = useMemo(() => {
    if (!selectedNodeId) return traces;
    return traces.filter((t) => t.nodeId === selectedNodeId);
  }, [traces, selectedNodeId]);

  return (
    <div className={`flex flex-col bg-slate-900/30 ${className}`}>
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-800/50 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-md bg-cyan-500/10 border border-cyan-500/20">
            <Activity size={12} className="text-cyan-400" />
          </div>
          <span className="text-xs font-semibold text-white">Execution Trace</span>
        </div>
        <span className="text-[10px] text-slate-500 font-mono px-2 py-0.5 rounded bg-slate-800/50 border border-slate-700/50">
          {traces.length} events
        </span>
      </div>

      {/* Selected Node Details */}
      <AnimatePresence>
        {selectedNodeDetails && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="border-b border-slate-800/50 overflow-hidden shrink-0"
          >
            <div className="p-3 bg-slate-800/20">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  {selectedNodeDetails.type === "agent" ? (
                    <Cpu size={14} className="text-cyan-400" />
                  ) : (
                    <Wrench size={14} className="text-amber-400" />
                  )}
                  <span className="text-xs font-medium text-white">
                    {selectedNodeDetails.title}
                  </span>
                </div>
                <span
                  className={`px-2 py-0.5 text-[10px] font-mono rounded border ${
                    selectedNodeDetails.status === "completed"
                      ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
                      : selectedNodeDetails.status === "running"
                      ? "bg-cyan-500/20 text-cyan-400 border-cyan-500/30 animate-pulse"
                      : selectedNodeDetails.status === "error"
                      ? "bg-red-500/20 text-red-400 border-red-500/30"
                      : "bg-slate-500/20 text-slate-400 border-slate-500/30"
                  }`}
                >
                  {selectedNodeDetails.status.toUpperCase()}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 text-[10px]">
                {selectedNodeDetails.phase && (
                  <div className="flex items-center gap-1.5">
                    <span className="text-slate-500">Phase:</span>
                    <span className="text-slate-300">{selectedNodeDetails.phase}</span>
                  </div>
                )}
                {selectedNodeDetails.latency !== undefined && (
                  <div className="flex items-center gap-1.5">
                    <Clock size={10} className="text-slate-500" />
                    <span className="text-slate-300">{formatDuration(selectedNodeDetails.latency)}</span>
                  </div>
                )}
                {selectedNodeDetails.duration !== undefined && (
                  <div className="flex items-center gap-1.5">
                    <Clock size={10} className="text-slate-500" />
                    <span className="text-slate-300">{formatDuration(selectedNodeDetails.duration)}</span>
                  </div>
                )}
                {selectedNodeDetails.tokens !== undefined && (
                  <div className="flex items-center gap-1.5">
                    <span className="text-slate-500">Tokens:</span>
                    <span className="text-slate-300">{selectedNodeDetails.tokens.toLocaleString()}</span>
                  </div>
                )}
                {selectedNodeDetails.outputNodeIds && selectedNodeDetails.outputNodeIds.length > 0 && (
                  <div className="col-span-2 flex items-center gap-1.5">
                    <Link size={10} className="text-purple-400" />
                    <span className="text-slate-300">
                      {selectedNodeDetails.outputNodeIds.length} assets produced
                    </span>
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Trace List */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-2 space-y-1 scrollbar-thin scrollbar-track-slate-800/50 scrollbar-thumb-slate-700"
        style={{ maxHeight }}
      >
        <AnimatePresence mode="popLayout">
          {filteredTraces.length === 0 ? (
            <div className="flex items-center justify-center h-20 text-slate-500 text-xs">
              {selectedNodeId ? "No events for selected node" : "Waiting for events..."}
            </div>
          ) : (
            filteredTraces.map((trace) => {
              const colors = EVENT_COLORS[trace.type] || DEFAULT_EVENT_COLORS;
              return (
                <motion.div
                  key={trace.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 10 }}
                  className={`flex items-start gap-2 p-2 rounded border-l-2 ${colors.border} ${colors.bg} hover:bg-opacity-50 transition-colors`}
                >
                  <div className="mt-0.5 shrink-0">{getTraceIcon(trace.type)}</div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[11px] text-slate-300 truncate">{trace.message}</p>
                    <p className="text-[9px] text-slate-500 mt-0.5 font-mono">
                      {formatTime(trace.timestamp)}
                    </p>
                  </div>
                </motion.div>
              );
            })
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
