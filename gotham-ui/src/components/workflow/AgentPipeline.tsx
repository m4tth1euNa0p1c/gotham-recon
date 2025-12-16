"use client";

/**
 * AgentPipeline
 * Visualizes agents in a horizontal sequential pipeline with animations.
 * Agents appear sequentially as they start, with tool calls shown underneath.
 * NO MOCK DATA - populated via live WebSocket events only.
 */

import React, { useMemo, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Cpu,
  Wrench,
  CheckCircle,
  XCircle,
  Loader2,
  Clock,
  Zap,
  ChevronRight,
} from "lucide-react";
import { useWorkflowStore, AgentRunNode, ToolCallNode } from "@/stores/workflowStore";

// Phase order for sorting
const PHASE_ORDER = ["OSINT", "ACTIVE", "INTEL", "VERIF", "PLANNER", "REPORT"];

// Phase colors (Gotham theme)
const PHASE_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  OSINT: { bg: "bg-cyan-500/20", border: "border-cyan-500/50", text: "text-cyan-400" },
  ACTIVE: { bg: "bg-amber-500/20", border: "border-amber-500/50", text: "text-amber-400" },
  INTEL: { bg: "bg-purple-500/20", border: "border-purple-500/50", text: "text-purple-400" },
  VERIF: { bg: "bg-emerald-500/20", border: "border-emerald-500/50", text: "text-emerald-400" },
  PLANNER: { bg: "bg-rose-500/20", border: "border-rose-500/50", text: "text-rose-400" },
  REPORT: { bg: "bg-blue-500/20", border: "border-blue-500/50", text: "text-blue-400" },
};

// Status colors
const STATUS_COLORS: Record<string, { bg: string; border: string; icon: string }> = {
  pending: { bg: "bg-slate-600", border: "border-slate-500", icon: "text-slate-400" },
  running: { bg: "bg-cyan-500", border: "border-cyan-400", icon: "text-cyan-300" },
  completed: { bg: "bg-emerald-500", border: "border-emerald-400", icon: "text-emerald-300" },
  error: { bg: "bg-red-500", border: "border-red-400", icon: "text-red-300" },
};

// Format duration
function formatDuration(ms?: number): string {
  if (!ms) return "";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
}

// Agent card animation variants
const agentVariants = {
  hidden: { opacity: 0, x: -50, scale: 0.8 },
  visible: {
    opacity: 1,
    x: 0,
    scale: 1,
    transition: {
      type: "spring" as const,
      stiffness: 300,
      damping: 25,
      duration: 0.5,
    },
  },
  exit: {
    opacity: 0,
    scale: 0.8,
    transition: { duration: 0.2 },
  },
};

// Tool card animation variants
const toolVariants = {
  hidden: { opacity: 0, y: -10, scale: 0.9 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      type: "spring" as const,
      stiffness: 400,
      damping: 25,
    },
  },
  exit: { opacity: 0, y: -10, scale: 0.9 },
};

// Connector line animation
const connectorVariants = {
  hidden: { scaleX: 0, opacity: 0 },
  visible: {
    scaleX: 1,
    opacity: 1,
    transition: {
      duration: 0.4,
      ease: "easeOut" as const,
      delay: 0.2,
    },
  },
};

interface AgentCardProps {
  agent: AgentRunNode;
  tools: ToolCallNode[];
  isLast: boolean;
  index: number;
}

function AgentCard({ agent, tools, isLast, index }: AgentCardProps) {
  const phase = agent.data.phase || "OSINT";
  const phaseColors = PHASE_COLORS[phase] || PHASE_COLORS.OSINT;
  const statusColors = STATUS_COLORS[agent.status] || STATUS_COLORS.pending;

  // Status icon
  const StatusIcon = () => {
    switch (agent.status) {
      case "running":
        return <Loader2 size={14} className="animate-spin text-cyan-400" />;
      case "completed":
        return <CheckCircle size={14} className="text-emerald-400" />;
      case "error":
        return <XCircle size={14} className="text-red-400" />;
      default:
        return <Clock size={14} className="text-slate-400" />;
    }
  };

  return (
    <motion.div
      className="flex items-center"
      variants={agentVariants}
      initial="hidden"
      animate="visible"
      exit="exit"
      layout
    >
      {/* Agent Card */}
      <div className="relative flex flex-col">
        {/* Phase Badge */}
        <div
          className={`absolute -top-3 left-1/2 -translate-x-1/2 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${phaseColors.bg} ${phaseColors.border} border ${phaseColors.text}`}
        >
          {phase}
        </div>

        {/* Main Card */}
        <motion.div
          className={`relative min-w-[160px] p-4 rounded-lg border-2 backdrop-blur-sm transition-all duration-300 ${
            agent.status === "running"
              ? "bg-slate-900/90 border-cyan-500/70 shadow-lg shadow-cyan-500/20"
              : agent.status === "completed"
              ? "bg-slate-900/70 border-emerald-500/50"
              : agent.status === "error"
              ? "bg-slate-900/70 border-red-500/50"
              : "bg-slate-900/50 border-slate-700"
          }`}
          whileHover={{ scale: 1.02 }}
        >
          {/* Glow effect for running agents */}
          {agent.status === "running" && (
            <motion.div
              className="absolute inset-0 rounded-lg bg-cyan-500/10"
              animate={{ opacity: [0.3, 0.6, 0.3] }}
              transition={{ duration: 2, repeat: Infinity }}
            />
          )}

          {/* Header */}
          <div className="flex items-center gap-2 mb-2">
            <div
              className={`p-1.5 rounded ${statusColors.bg}/20 border ${statusColors.border}`}
            >
              <Cpu size={16} className={statusColors.icon} />
            </div>
            <StatusIcon />
          </div>

          {/* Agent Name */}
          <h4 className="text-sm font-semibold text-white truncate">
            {agent.data.agentName || agent.label}
          </h4>

          {/* Duration */}
          {agent.data.duration && (
            <div className="flex items-center gap-1 mt-1 text-xs text-slate-400">
              <Clock size={10} />
              <span>{formatDuration(agent.data.duration)}</span>
            </div>
          )}

          {/* Token count */}
          {agent.data.tokens && (
            <div className="flex items-center gap-1 mt-0.5 text-xs text-slate-500">
              <Zap size={10} />
              <span>{agent.data.tokens.toLocaleString()} tokens</span>
            </div>
          )}
        </motion.div>

        {/* Tool calls underneath */}
        <AnimatePresence mode="popLayout">
          {tools.length > 0 && (
            <motion.div
              className="mt-2 space-y-1"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
            >
              {tools.slice(0, 5).map((tool) => (
                <motion.div
                  key={tool.id}
                  variants={toolVariants}
                  initial="hidden"
                  animate="visible"
                  exit="exit"
                  className={`flex items-center gap-2 px-2 py-1 rounded text-xs border ${
                    tool.status === "running"
                      ? "bg-amber-500/10 border-amber-500/30 text-amber-300"
                      : tool.status === "completed"
                      ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                      : tool.status === "error"
                      ? "bg-red-500/10 border-red-500/30 text-red-300"
                      : "bg-slate-800/50 border-slate-700 text-slate-400"
                  }`}
                >
                  {tool.status === "running" ? (
                    <Loader2 size={10} className="animate-spin" />
                  ) : (
                    <Wrench size={10} />
                  )}
                  <span className="truncate">{tool.data.toolName}</span>
                </motion.div>
              ))}
              {tools.length > 5 && (
                <div className="text-xs text-slate-500 px-2">
                  +{tools.length - 5} more
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Connector Arrow (except for last) */}
      {!isLast && (
        <motion.div
          className="flex items-center mx-2"
          variants={connectorVariants}
          initial="hidden"
          animate="visible"
          style={{ originX: 0 }}
        >
          <div className="w-8 h-0.5 bg-gradient-to-r from-slate-600 to-slate-500" />
          <ChevronRight size={16} className="text-slate-500 -ml-1" />
        </motion.div>
      )}
    </motion.div>
  );
}

interface AgentPipelineProps {
  className?: string;
  maxAgents?: number;
  isHistorical?: boolean;
}

export default function AgentPipeline({ className = "", maxAgents = 10, isHistorical = false }: AgentPipelineProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Get agents and tools from store
  const agentRunsMap = useWorkflowStore((state) => state.agentRuns);
  const toolCallsMap = useWorkflowStore((state) => state.toolCalls);

  // Convert to arrays and sort
  const agents = useMemo(() => {
    const agentArray = Array.from(agentRunsMap.values());

    // Sort by phase order, then by start time
    return agentArray.sort((a, b) => {
      const phaseA = PHASE_ORDER.indexOf(a.data.phase || "OSINT");
      const phaseB = PHASE_ORDER.indexOf(b.data.phase || "OSINT");

      if (phaseA !== phaseB) return phaseA - phaseB;

      // Same phase, sort by start time
      const timeA = a.data.startTime ? new Date(a.data.startTime).getTime() : 0;
      const timeB = b.data.startTime ? new Date(b.data.startTime).getTime() : 0;
      return timeA - timeB;
    });
  }, [agentRunsMap]);

  // Group tools by agent
  const toolsByAgent = useMemo(() => {
    const map = new Map<string, ToolCallNode[]>();

    Array.from(toolCallsMap.values()).forEach((tool) => {
      const agentId = tool.data.agentId;
      if (agentId) {
        if (!map.has(agentId)) {
          map.set(agentId, []);
        }
        map.get(agentId)!.push(tool);
      }
    });

    return map;
  }, [toolCallsMap]);

  // Auto-scroll to latest agent
  useEffect(() => {
    if (scrollRef.current && agents.length > 0) {
      scrollRef.current.scrollLeft = scrollRef.current.scrollWidth;
    }
  }, [agents.length]);

  // Limit displayed agents
  const displayedAgents = agents.slice(-maxAgents);

  return (
    <div className={`relative ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3 px-2">
        <div className="flex items-center gap-2">
          <Cpu size={16} className="text-cyan-400" />
          <span className="text-sm font-medium text-white">Agent Pipeline</span>
        </div>
        <span className="text-xs text-slate-500 font-mono">
          {agents.length} agent{agents.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Pipeline Container */}
      <div
        ref={scrollRef}
        className="overflow-x-auto overflow-y-visible pb-4 scrollbar-thin scrollbar-track-slate-900 scrollbar-thumb-slate-700"
      >
        <div className="flex items-start gap-0 px-4 min-h-[140px]">
          <AnimatePresence mode="popLayout">
            {displayedAgents.length === 0 ? (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex items-center justify-center w-full h-[120px] text-slate-500 text-sm"
              >
                <div className="flex flex-col items-center gap-2">
                  {isHistorical ? (
                    <>
                      <Cpu size={24} className="text-slate-600" />
                      <span>No agent execution data recorded</span>
                      <span className="text-xs text-slate-600">This mission was run before workflow tracking was enabled</span>
                    </>
                  ) : (
                    <>
                      <Loader2 size={24} className="animate-spin text-slate-600" />
                      <span>Waiting for agents...</span>
                    </>
                  )}
                </div>
              </motion.div>
            ) : (
              displayedAgents.map((agent, index) => (
                <AgentCard
                  key={agent.id}
                  agent={agent}
                  tools={toolsByAgent.get(agent.id) || []}
                  isLast={index === displayedAgents.length - 1}
                  index={index}
                />
              ))
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Show more indicator */}
      {agents.length > maxAgents && (
        <div className="absolute left-0 top-1/2 -translate-y-1/2 bg-gradient-to-r from-slate-950 to-transparent pl-2 pr-6 py-2">
          <span className="text-xs text-slate-500">
            +{agents.length - maxAgents} earlier
          </span>
        </div>
      )}
    </div>
  );
}
