"use client";

import { useMemo, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Activity,
  Clock,
  CheckCircle,
  XCircle,
  Cpu,
  Wrench,
  Link,
  ChevronRight,
  Zap,
} from "lucide-react";
import { useShallow } from "zustand/react/shallow";
import { useWorkflowStore } from "@/stores/workflowStore";
import type { AgentRunNode, ToolCallNode, TraceLogEntry } from "@/stores/workflowStore";

interface TracePanelProps {
  className?: string;
  maxHeight?: string;
}

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
  switch (type) {
    case "agent_started":
      return <Activity size={14} className="text-cyan-400" />;
    case "agent_finished":
      return <CheckCircle size={14} className="text-green-400" />;
    case "tool_called":
      return <Wrench size={14} className="text-amber-400" />;
    case "tool_finished":
      return <Zap size={14} className="text-emerald-400" />;
    case "asset_mutation":
      return <Link size={14} className="text-purple-400" />;
    default:
      return <ChevronRight size={14} className="text-gray-400" />;
  }
}

// Get color for trace type
function getTraceColor(type: string): string {
  switch (type) {
    case "agent_started":
      return "border-cyan-500/30";
    case "agent_finished":
      return "border-green-500/30";
    case "tool_called":
      return "border-amber-500/30";
    case "tool_finished":
      return "border-emerald-500/30";
    case "asset_mutation":
      return "border-purple-500/30";
    default:
      return "border-gray-500/30";
  }
}

export default function TracePanel({ className = "", maxHeight = "400px" }: TracePanelProps) {
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
    <div className={`flex flex-col bg-[#0d0d12] border border-[#1a1a25] rounded-lg ${className}`}>
      {/* Header */}
      <div className="px-4 py-3 border-b border-[#1a1a25] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity size={16} className="text-cyan-400" />
          <span className="text-sm font-medium text-white">Execution Trace</span>
        </div>
        <span className="text-xs text-gray-500">{traces.length} events</span>
      </div>

      {/* Selected Node Details */}
      <AnimatePresence>
        {selectedNodeDetails && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="border-b border-[#1a1a25] overflow-hidden"
          >
            <div className="p-4 bg-[#0a0a0f]">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  {selectedNodeDetails.type === "agent" ? (
                    <Cpu size={16} className="text-cyan-400" />
                  ) : (
                    <Wrench size={16} className="text-amber-400" />
                  )}
                  <span className="text-sm font-medium text-white">
                    {selectedNodeDetails.title}
                  </span>
                </div>
                <span
                  className={`px-2 py-0.5 text-xs rounded ${
                    selectedNodeDetails.status === "completed"
                      ? "bg-green-500/20 text-green-400"
                      : selectedNodeDetails.status === "running"
                      ? "bg-cyan-500/20 text-cyan-400"
                      : selectedNodeDetails.status === "error"
                      ? "bg-red-500/20 text-red-400"
                      : "bg-gray-500/20 text-gray-400"
                  }`}
                >
                  {selectedNodeDetails.status.toUpperCase()}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs">
                {selectedNodeDetails.phase && (
                  <div className="flex items-center gap-1.5">
                    <span className="text-gray-500">Phase:</span>
                    <span className="text-gray-300">{selectedNodeDetails.phase}</span>
                  </div>
                )}
                {selectedNodeDetails.latency !== undefined && (
                  <div className="flex items-center gap-1.5">
                    <Clock size={12} className="text-gray-500" />
                    <span className="text-gray-300">{formatDuration(selectedNodeDetails.latency)}</span>
                  </div>
                )}
                {selectedNodeDetails.duration !== undefined && (
                  <div className="flex items-center gap-1.5">
                    <Clock size={12} className="text-gray-500" />
                    <span className="text-gray-300">{formatDuration(selectedNodeDetails.duration)}</span>
                  </div>
                )}
                {selectedNodeDetails.tokens !== undefined && (
                  <div className="flex items-center gap-1.5">
                    <span className="text-gray-500">Tokens:</span>
                    <span className="text-gray-300">{selectedNodeDetails.tokens.toLocaleString()}</span>
                  </div>
                )}
                {selectedNodeDetails.outputNodeIds && selectedNodeDetails.outputNodeIds.length > 0 && (
                  <div className="col-span-2 flex items-center gap-1.5">
                    <Link size={12} className="text-purple-400" />
                    <span className="text-gray-300">
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
        className="flex-1 overflow-y-auto p-2 space-y-1"
        style={{ maxHeight }}
      >
        <AnimatePresence mode="popLayout">
          {filteredTraces.length === 0 ? (
            <div className="flex items-center justify-center h-20 text-gray-500 text-sm">
              {selectedNodeId ? "No events for selected node" : "Waiting for events..."}
            </div>
          ) : (
            filteredTraces.map((trace) => (
              <motion.div
                key={trace.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 10 }}
                className={`flex items-start gap-2 p-2 rounded border-l-2 ${getTraceColor(
                  trace.type
                )} bg-[#0a0a0f]/50 hover:bg-[#0a0a0f] transition-colors`}
              >
                <div className="mt-0.5">{getTraceIcon(trace.type)}</div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-gray-300 truncate">{trace.message}</p>
                  <p className="text-[10px] text-gray-500 mt-0.5">
                    {formatTime(trace.timestamp)}
                  </p>
                </div>
              </motion.div>
            ))
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
