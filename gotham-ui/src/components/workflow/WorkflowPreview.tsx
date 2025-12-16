"use client";

import { useEffect, useMemo } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  Activity,
  Cpu,
  Wrench,
  ArrowRight,
  CheckCircle,
  XCircle,
  Loader2,
} from "lucide-react";
import { useWorkflowStore } from "@/stores/workflowStore";
import { WorkflowService } from "@/services/WorkflowService";

interface WorkflowPreviewProps {
  missionId: string;
  className?: string;
}

export default function WorkflowPreview({ missionId, className = "" }: WorkflowPreviewProps) {
  // Store state - access Maps directly and memoize array conversions
  const agentRunsMap = useWorkflowStore((state) => state.agentRuns);
  const toolCallsMap = useWorkflowStore((state) => state.toolCalls);
  const connectionStatus = useWorkflowStore((state) => state.connectionStatus);
  const addAgentRun = useWorkflowStore((state) => state.addAgentRun);
  const updateAgentStatus = useWorkflowStore((state) => state.updateAgentStatus);
  const addToolCall = useWorkflowStore((state) => state.addToolCall);
  const updateToolCall = useWorkflowStore((state) => state.updateToolCall);
  const setConnectionStatus = useWorkflowStore((state) => state.setConnectionStatus);

  // Memoize array conversions to avoid creating new arrays on every render
  const agentRuns = useMemo(() => Array.from(agentRunsMap.values()), [agentRunsMap]);
  const toolCalls = useMemo(() => Array.from(toolCallsMap.values()), [toolCallsMap]);

  // Calculate stats
  const stats = useMemo(() => {
    const agents = {
      total: agentRuns.length,
      running: agentRuns.filter((a) => a.status === "running").length,
      completed: agentRuns.filter((a) => a.status === "completed").length,
      error: agentRuns.filter((a) => a.status === "error").length,
    };

    const tools = {
      total: toolCalls.length,
      running: toolCalls.filter((t) => t.status === "running").length,
      completed: toolCalls.filter((t) => t.status === "completed").length,
      error: toolCalls.filter((t) => t.status === "error").length,
    };

    // Get current phase from running agent
    const currentAgent = agentRuns.find((a) => a.status === "running");
    const currentPhase = currentAgent?.data?.phase || "Idle";

    return { agents, tools, currentPhase };
  }, [agentRuns, toolCalls]);

  // Subscribe to workflow events
  useEffect(() => {
    if (!missionId) return;

    WorkflowService.subscribe(missionId);

    const unsubAgentStarted = WorkflowService.onAgentStarted((agent) => {
      addAgentRun(agent);
    });

    const unsubAgentFinished = WorkflowService.onAgentFinished((agentId, status, latency) => {
      updateAgentStatus(agentId, status, new Date().toISOString(), latency);
    });

    const unsubToolCalled = WorkflowService.onToolCalled((tool) => {
      addToolCall(tool);
    });

    const unsubToolFinished = WorkflowService.onToolFinished((toolId, duration, outcome) => {
      updateToolCall(toolId, { duration, outcome, endTime: new Date().toISOString() });
    });

    const unsubStatus = WorkflowService.onStatusChange((status) => {
      setConnectionStatus(status);
    });

    // Load initial snapshot
    WorkflowService.getWorkflowSnapshot(missionId).then(({ agents, tools }) => {
      agents.forEach(addAgentRun);
      tools.forEach(addToolCall);
    });

    return () => {
      unsubAgentStarted();
      unsubAgentFinished();
      unsubToolCalled();
      unsubToolFinished();
      unsubStatus();
    };
  }, [
    missionId,
    addAgentRun,
    updateAgentStatus,
    addToolCall,
    updateToolCall,
    setConnectionStatus,
  ]);

  return (
    <div
      className={`bg-[#0d0d12] border border-[#1a1a25] rounded-lg overflow-hidden ${className}`}
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-[#1a1a25] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity size={16} className="text-cyan-400" />
          <span className="text-sm font-medium text-white">Agent Workflow</span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${
              connectionStatus === "connected"
                ? "bg-green-400 animate-pulse"
                : "bg-gray-500"
            }`}
          />
          <Link
            href={`/mission/${missionId}/workflow`}
            className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
          >
            Full View
            <ArrowRight size={12} />
          </Link>
        </div>
      </div>

      {/* Content */}
      <div className="p-4">
        {/* Current Phase */}
        <div className="mb-4">
          <span className="text-xs text-gray-500 uppercase tracking-wider">
            Current Phase
          </span>
          <div className="mt-1 flex items-center gap-2">
            {stats.agents.running > 0 && (
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
              >
                <Loader2 size={14} className="text-cyan-400" />
              </motion.div>
            )}
            <span className="text-lg font-medium text-white">
              {stats.currentPhase}
            </span>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 gap-3">
          {/* Agents */}
          <div className="bg-[#0a0a0f] rounded-lg p-3">
            <div className="flex items-center gap-2 mb-2">
              <Cpu size={14} className="text-cyan-400" />
              <span className="text-xs text-gray-400">Agents</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-2xl font-bold text-white">
                {stats.agents.total}
              </span>
              <div className="flex items-center gap-2 text-xs">
                {stats.agents.running > 0 && (
                  <span className="text-cyan-400">{stats.agents.running} active</span>
                )}
                {stats.agents.completed > 0 && (
                  <CheckCircle size={12} className="text-green-400" />
                )}
                {stats.agents.error > 0 && (
                  <XCircle size={12} className="text-red-400" />
                )}
              </div>
            </div>
          </div>

          {/* Tools */}
          <div className="bg-[#0a0a0f] rounded-lg p-3">
            <div className="flex items-center gap-2 mb-2">
              <Wrench size={14} className="text-amber-400" />
              <span className="text-xs text-gray-400">Tools</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-2xl font-bold text-white">
                {stats.tools.total}
              </span>
              <div className="flex items-center gap-2 text-xs">
                {stats.tools.running > 0 && (
                  <span className="text-amber-400">{stats.tools.running} active</span>
                )}
                {stats.tools.completed > 0 && (
                  <CheckCircle size={12} className="text-green-400" />
                )}
                {stats.tools.error > 0 && (
                  <XCircle size={12} className="text-red-400" />
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Recent Agents */}
        {agentRuns.length > 0 && (
          <div className="mt-4">
            <span className="text-xs text-gray-500 uppercase tracking-wider">
              Recent Agents
            </span>
            <div className="mt-2 space-y-1">
              {agentRuns.slice(-3).reverse().map((agent) => (
                <div
                  key={agent.id}
                  className="flex items-center justify-between py-1.5 px-2 rounded bg-[#0a0a0f]"
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={`w-1.5 h-1.5 rounded-full ${
                        agent.status === "running"
                          ? "bg-cyan-400 animate-pulse"
                          : agent.status === "completed"
                          ? "bg-green-400"
                          : agent.status === "error"
                          ? "bg-red-400"
                          : "bg-gray-500"
                      }`}
                    />
                    <span className="text-xs text-gray-300">{agent.data?.agentName}</span>
                  </div>
                  <span className="text-[10px] text-gray-500">{agent.data?.phase}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Empty State */}
        {agentRuns.length === 0 && (
          <div className="mt-4 py-6 text-center">
            <Activity size={24} className="text-gray-600 mx-auto mb-2" />
            <p className="text-xs text-gray-500">No workflow data yet</p>
          </div>
        )}
      </div>
    </div>
  );
}
