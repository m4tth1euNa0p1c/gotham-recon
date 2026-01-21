"use client";

/**
 * AgentPipeline
 * Visualizes agents in a horizontal sequential pipeline with phase-colored cards.
 *
 * Design Specs:
 * 1. Container: Horizontal scroll, dark bg (bg-slate-900/20), border-bottom, tracking-widest title.
 * 2. Card: 256px wide, Glassmorphism, Industrial look.
 *    - Header: Phase [OSINT], Activity Icon.
 *    - Body: Agent Name, Metadata (Time/Tokens), Hexagon Icon.
 *    - Tools: Max 3 items, Zap icon (pulsing orange if running).
 * 3. Connection: 32px spacer, 2px line, CSS Arrow Tip.
 */

import React, { useMemo, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Activity,
  Zap,
  Hexagon,
  Clock,
  Terminal,
  CheckCircle2,
  XCircle,
  Loader2,
  Cpu,
  Wrench,
  Timer,
} from "lucide-react";
import { useWorkflowStore, AgentRunNode, ToolCallNode } from "@/stores/workflowStore";

// Phase order for sorting
const PHASE_ORDER = ["OSINT", "ACTIVE", "INTEL", "VERIF", "PLANNER", "REPORT"];

// Phase colors matching design specs
const PHASE_COLORS: Record<string, { bg: string; border: string; text: string; glow: string }> = {
  OSINT: { bg: "bg-cyan-500/10", border: "border-cyan-500/50", text: "text-cyan-400", glow: "shadow-cyan-500/20" },
  ACTIVE: { bg: "bg-amber-500/10", border: "border-amber-500/50", text: "text-amber-400", glow: "shadow-amber-500/20" },
  INTEL: { bg: "bg-purple-500/10", border: "border-purple-500/50", text: "text-purple-400", glow: "shadow-purple-500/20" },
  VERIF: { bg: "bg-emerald-500/10", border: "border-emerald-500/50", text: "text-emerald-400", glow: "shadow-emerald-500/20" },
  PLANNER: { bg: "bg-rose-500/10", border: "border-rose-500/50", text: "text-rose-400", glow: "shadow-rose-500/20" },
  REPORT: { bg: "bg-blue-500/10", border: "border-blue-500/50", text: "text-blue-400", glow: "shadow-blue-500/20" },
};

const DEFAULT_PHASE_COLORS = { bg: "bg-slate-500/10", border: "border-slate-500/50", text: "text-slate-400", glow: "shadow-slate-500/20" };

// Format duration
function formatDuration(ms?: number): string {
  if (!ms) return "";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
}

// Format timestamp
function formatTime(timestamp?: string): string {
  if (!timestamp) return "";
  const date = new Date(timestamp);
  return date.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

// Status indicator component
function StatusIndicator({ status }: { status: string }) {
  switch (status) {
    case "running":
      return <Loader2 size={12} className="text-cyan-400 animate-spin" />;
    case "completed":
      return <CheckCircle2 size={12} className="text-emerald-400" />;
    case "error":
      return <XCircle size={12} className="text-red-400" />;
    default:
      return <Clock size={12} className="text-slate-500" />;
  }
}

// Arrow Connection Component
const ConnectionArrow = () => (
  <div className="flex items-center w-8 shrink-0 relative">
    {/* Line */}
    <div className="w-full h-0.5 bg-slate-800" />
    {/* Arrow Tip (CSS Square Rotated) */}
    <div className="absolute right-0 w-2 h-2 border-t border-r border-slate-600 bg-slate-900 rotate-45 transform translate-x-[-1px]" />
  </div>
);

// Agent card animation variants
const agentVariants = {
  hidden: { opacity: 0, x: -20, scale: 0.95 },
  visible: {
    opacity: 1,
    x: 0,
    scale: 1,
    transition: { type: "spring" as const, stiffness: 300, damping: 25 },
  },
};

interface AgentCardProps {
  agent: AgentRunNode;
  tools: ToolCallNode[];
}

function AgentCard({ agent, tools }: AgentCardProps) {
  const phase = agent.data.phase || "OSINT";
  const colors = PHASE_COLORS[phase] || DEFAULT_PHASE_COLORS;
  const isRunning = agent.status === "running";
  const isCompleted = agent.status === "completed";
  const isError = agent.status === "error";

  // Calculate tool stats
  const toolsRunning = tools.filter(t => t.status === "running").length;
  const toolsCompleted = tools.filter(t => t.status === "completed").length;

  return (
    <motion.div
      variants={agentVariants}
      initial="hidden"
      animate="visible"
      className={`
        relative w-72 shrink-0 rounded-lg border backdrop-blur-md overflow-hidden transition-all duration-300
        ${colors.bg} ${colors.border}
        ${isRunning ? `ring-1 ring-${colors.text.split('-')[1]}-500/50 shadow-lg ${colors.glow}` : ""}
      `}
    >
      {/* 1. Header */}
      <div className={`px-3 py-2 border-b ${colors.border} flex justify-between items-center bg-slate-900/50`}>
        <div className="flex items-center gap-2">
          <span className={`text-[10px] font-bold tracking-wider px-1.5 py-0.5 rounded ${colors.bg} ${colors.text}`}>
            {phase}
          </span>
          <StatusIndicator status={agent.status} />
        </div>
        <div className="flex items-center gap-2">
          {agent.data.model && (
            <span className="text-[9px] font-mono text-slate-500 bg-slate-800/50 px-1.5 py-0.5 rounded">
              {(agent.data.model || '').split('/').pop()?.substring(0, 12) || agent.data.model || ''}
            </span>
          )}
          <Hexagon size={14} className={colors.text} />
        </div>
      </div>

      {/* 2. Body */}
      <div className="p-3">
        {/* Agent Name + Status Badge */}
        <div className="flex items-center justify-between gap-2">
          <h4 className="text-sm font-semibold text-slate-100 truncate flex-1" title={agent.data.agentName}>
            {agent.data.agentName || "Unknown Agent"}
          </h4>
          <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${
            isRunning ? "bg-cyan-500/20 text-cyan-400 border-cyan-500/30" :
            isCompleted ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30" :
            isError ? "bg-red-500/20 text-red-400 border-red-500/30" :
            "bg-slate-500/20 text-slate-400 border-slate-500/30"
          }`}>
            {agent.status.toUpperCase()}
          </span>
        </div>

        {/* Time Info */}
        <div className="flex items-center gap-2 mt-2 text-[10px] text-slate-500">
          {agent.data.startTime && (
            <span className="flex items-center gap-1">
              <Timer size={10} />
              {formatTime(agent.data.startTime)}
            </span>
          )}
          {agent.data.endTime && (
            <>
              <span>→</span>
              <span>{formatTime(agent.data.endTime)}</span>
            </>
          )}
        </div>

        {/* Stats Row */}
        <div className="flex items-center gap-2 mt-2 flex-wrap">
          {/* Duration */}
          <span className="flex items-center gap-1 text-[10px] font-mono bg-slate-900/40 px-2 py-1 rounded border border-slate-800/50">
            <Clock size={10} className="text-slate-500" />
            <span className="text-slate-300">
              {agent.data.duration ? formatDuration(agent.data.duration) : (isRunning ? "Running..." : "—")}
            </span>
          </span>

          {/* Tokens */}
          {agent.data.tokens !== undefined && agent.data.tokens > 0 && (
            <span className="flex items-center gap-1 text-[10px] font-mono bg-slate-900/40 px-2 py-1 rounded border border-slate-800/50">
              <Cpu size={10} className="text-purple-400" />
              <span className="text-slate-300">{agent.data.tokens.toLocaleString()}</span>
            </span>
          )}

          {/* Tools Count */}
          <span className="flex items-center gap-1 text-[10px] font-mono bg-slate-900/40 px-2 py-1 rounded border border-slate-800/50">
            <Wrench size={10} className="text-amber-400" />
            <span className="text-slate-300">{tools.length}</span>
            {toolsRunning > 0 && (
              <span className="text-cyan-400 animate-pulse">({toolsRunning} active)</span>
            )}
          </span>
        </div>

        {/* 3. Tools List */}
        <div className="mt-3 space-y-1">
          <div className="text-[9px] text-slate-500 font-semibold tracking-wider mb-1">TOOLS</div>
          {tools.slice(0, 4).map((tool) => {
            const isToolRunning = tool.status === 'running';
            const isToolCompleted = tool.status === 'completed';
            const isToolError = tool.status === 'error';
            return (
              <div
                key={tool.id}
                className={`flex items-center gap-2 px-2 py-1.5 rounded border transition-colors ${
                  isToolRunning ? "bg-amber-500/10 border-amber-500/30" :
                  isToolError ? "bg-red-500/10 border-red-500/30" :
                  "bg-slate-900/40 border-slate-800/50"
                }`}
              >
                {isToolRunning ? (
                  <Loader2 size={10} className="text-amber-400 animate-spin" />
                ) : isToolCompleted ? (
                  <CheckCircle2 size={10} className="text-emerald-400" />
                ) : isToolError ? (
                  <XCircle size={10} className="text-red-400" />
                ) : (
                  <Zap size={10} className="text-slate-600" />
                )}
                <span className="text-[10px] font-mono text-slate-300 truncate flex-1">
                  {tool.data.toolName}
                </span>
                {tool.data.duration && (
                  <span className="text-[9px] text-slate-500 font-mono">
                    {formatDuration(tool.data.duration)}
                  </span>
                )}
              </div>
            );
          })}

          {tools.length > 4 && (
            <div className="text-[10px] text-slate-500 pl-2 mt-1">
              +{tools.length - 4} more...
            </div>
          )}
          {tools.length === 0 && (
            <div className="h-8 flex items-center justify-center text-[10px] text-slate-600 italic border border-dashed border-slate-700/50 rounded">
              No tools called yet
            </div>
          )}
        </div>
      </div>
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
        if (!map.has(agentId)) map.set(agentId, []);
        map.get(agentId)!.push(tool);
      }
    });
    return map;
  }, [toolCallsMap]);

  // Auto-scroll to latest agent
  useEffect(() => {
    if (scrollRef.current && agents.length > 0) {
      setTimeout(() => {
        if (scrollRef.current) scrollRef.current.scrollLeft = scrollRef.current.scrollWidth;
      }, 100);
    }
  }, [agents.length]);

  return (
    <div className={`flex flex-col bg-slate-900/20 border-b border-slate-800 ${className}`}>
      {/* Title */}
      <div className="px-4 py-2 shrink-0">
        <span className="text-[10px] font-bold text-slate-500 tracking-widest uppercase">
          Active Pipeline
        </span>
      </div>

      {/* Pipeline Track */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-x-auto overflow-y-visible scrollbar-thin scrollbar-track-slate-900 scrollbar-thumb-slate-700 pb-4 px-4 flex items-center"
      >
        <AnimatePresence>
          {agents.map((agent, index) => (
            <React.Fragment key={agent.id}>
              {/* Agent Card */}
              <AgentCard
                agent={agent}
                tools={toolsByAgent.get(agent.id) || []}
              />

              {/* Connector (if not last) */}
              {index < agents.length - 1 && (
                <ConnectionArrow />
              )}
            </React.Fragment>
          ))}

          {agents.length === 0 && (
            <div className="w-full flex justify-center py-8 text-slate-600 text-sm font-mono">
              {isHistorical ? "No pipeline data recorded." : "Waiting for agents to start..."}
            </div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
