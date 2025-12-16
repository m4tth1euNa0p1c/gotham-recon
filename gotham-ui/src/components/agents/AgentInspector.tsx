"use client";

/**
 * AgentInspector
 * Drawer component showing detailed agent information, logs, and tool calls.
 */

import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
    X,
    CheckCircle2,
    Loader2,
    Clock,
    AlertCircle,
    Wrench,
    Terminal,
    MessageSquare,
    Activity,
    ChevronDown,
    ChevronRight,
} from "lucide-react";
import { useMissionStore, useGraphStore } from "@/stores";

interface AgentInspectorProps {
    isOpen: boolean;
    onClose: () => void;
    selectedAgentId?: string | null;
}

// Agent configuration
const AGENT_CONFIG: Record<string, { name: string; role: string; phase: string; description: string }> = {
    pathfinder: {
        name: "Pathfinder",
        role: "Lead Orchestrator",
        phase: "INIT",
        description: "Coordinates the overall mission flow and delegates tasks to specialized agents.",
    },
    watchtower: {
        name: "Watchtower",
        role: "Intel Analyst",
        phase: "PASSIVE_RECON",
        description: "Performs passive reconnaissance using OSINT techniques and subdomain enumeration.",
    },
    stacktrace: {
        name: "StackTrace",
        role: "Tech Fingerprinter",
        phase: "ACTIVE_RECON",
        description: "Identifies technologies, services, and potential attack vectors through active probing.",
    },
    deepscript: {
        name: "DeepScript",
        role: "JS Miner",
        phase: "JS_ANALYSIS",
        description: "Analyzes JavaScript files to extract endpoints, API routes, and sensitive data.",
    },
    enricher: {
        name: "Enricher",
        role: "Phase 23 Pipeline",
        phase: "ENRICHMENT",
        description: "Enriches discovered assets with additional context, risk scores, and categorization.",
    },
    verifier: {
        name: "Verifier",
        role: "Phase 25 Pipeline",
        phase: "VERIFICATION",
        description: "Validates vulnerabilities and performs security testing on high-risk targets.",
    },
};

const statusConfig = {
    pending: { icon: Clock, color: "#4a4a5a", label: "Pending" },
    running: { icon: Loader2, color: "#00ffff", label: "Running" },
    completed: { icon: CheckCircle2, color: "#00ff41", label: "Completed" },
    error: { icon: AlertCircle, color: "#ff0040", label: "Error" },
};

export default function AgentInspector({ isOpen, onClose, selectedAgentId }: AgentInspectorProps) {
    // Mission state
    const currentMission = useMissionStore((state) => state.currentMission);
    const logs = useMissionStore((state) => state.logs);

    // Graph state
    const graphNodes = useGraphStore((state) => state.nodes);

    // Local state
    const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
        logs: true,
        tools: true,
        stats: false,
    });

    // Filter logs by phase
    const filteredLogs = useMemo(() => {
        if (!selectedAgentId) return logs.slice(0, 50);

        const agentConfig = AGENT_CONFIG[selectedAgentId];
        if (!agentConfig) return logs.slice(0, 50);

        return logs
            .filter((log) => {
                const logPhase = log.phase?.toUpperCase() || "";
                return logPhase.includes(agentConfig.phase);
            })
            .slice(0, 50);
    }, [logs, selectedAgentId]);

    // Extract tool calls from logs
    const toolCalls = useMemo(() => {
        return filteredLogs
            .filter((log) => log.metadata?.tool)
            .map((log) => ({
                tool: log.metadata?.tool as string,
                timestamp: log.timestamp,
                message: log.message,
            }));
    }, [filteredLogs]);

    // Calculate agent stats
    const agentStats = useMemo(() => {
        const nodes = Array.from(graphNodes.values());
        const agentConfig = selectedAgentId ? AGENT_CONFIG[selectedAgentId] : null;

        if (selectedAgentId === "watchtower") {
            return {
                discovered: nodes.filter(n => n.type === "SUBDOMAIN").length,
                processed: nodes.filter(n => n.type === "SUBDOMAIN").length,
            };
        }
        if (selectedAgentId === "stacktrace") {
            return {
                discovered: nodes.filter(n => n.type === "HTTP_SERVICE").length,
                processed: nodes.filter(n => n.type === "HTTP_SERVICE").length,
            };
        }
        if (selectedAgentId === "deepscript") {
            return {
                discovered: nodes.filter(n => n.type === "ENDPOINT").length,
                processed: nodes.filter(n => n.type === "ENDPOINT").length,
            };
        }
        if (selectedAgentId === "verifier") {
            return {
                discovered: nodes.filter(n => n.type === "VULNERABILITY").length,
                processed: nodes.filter(n => n.type === "VULNERABILITY").length,
            };
        }

        return { discovered: 0, processed: 0 };
    }, [graphNodes, selectedAgentId]);

    // Determine agent status
    const getAgentStatus = () => {
        if (!currentMission) return "pending";
        if (currentMission.status === "completed") return "completed";
        if (currentMission.status === "failed") return "error";

        const currentPhase = currentMission.currentPhase?.toUpperCase() || "";
        const agentConfig = selectedAgentId ? AGENT_CONFIG[selectedAgentId] : null;

        if (agentConfig && currentPhase.includes(agentConfig.phase)) {
            return "running";
        }

        // Check if this phase has logs (meaning it's completed)
        if (filteredLogs.length > 0) return "completed";

        return "pending";
    };

    const agentStatus = getAgentStatus();
    const config = statusConfig[agentStatus as keyof typeof statusConfig];
    const StatusIcon = config.icon;
    const agentInfo = selectedAgentId ? AGENT_CONFIG[selectedAgentId] : null;

    const toggleSection = (section: string) => {
        setExpandedSections((prev) => ({ ...prev, [section]: !prev[section] }));
    };

    return (
        <AnimatePresence>
            {isOpen && (
                <>
                    {/* Backdrop */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 bg-black/50 z-40"
                        onClick={onClose}
                    />

                    {/* Drawer */}
                    <motion.div
                        initial={{ x: "100%" }}
                        animate={{ x: 0 }}
                        exit={{ x: "100%" }}
                        transition={{ type: "spring", damping: 30, stiffness: 300 }}
                        className="fixed right-0 top-0 h-full w-96 bg-[#0d0d12] border-l border-[#1a1a25] z-50 flex flex-col"
                    >
                        {/* Header */}
                        <div className="flex items-center justify-between px-4 py-3 border-b border-[#1a1a25]">
                            <div className="flex items-center gap-3">
                                <div
                                    className="w-8 h-8 rounded-lg flex items-center justify-center"
                                    style={{
                                        background: `${config.color}15`,
                                        border: `1px solid ${config.color}30`,
                                    }}
                                >
                                    <StatusIcon
                                        size={16}
                                        style={{ color: config.color }}
                                        className={agentStatus === "running" ? "animate-spin" : ""}
                                    />
                                </div>
                                <div>
                                    <h3 className="text-sm font-bold text-white">
                                        {agentInfo?.name || "Agent Inspector"}
                                    </h3>
                                    <p className="text-xs text-[#4a4a5a]">
                                        {agentInfo?.role || "Select an agent"}
                                    </p>
                                </div>
                            </div>
                            <button
                                onClick={onClose}
                                className="p-2 rounded-lg hover:bg-[#1a1a25] transition-colors"
                            >
                                <X size={16} className="text-[#4a4a5a]" />
                            </button>
                        </div>

                        {/* Content */}
                        <div className="flex-1 overflow-y-auto">
                            {agentInfo ? (
                                <>
                                    {/* Description */}
                                    <div className="px-4 py-3 border-b border-[#1a1a25]">
                                        <p className="text-xs text-[#8a8a9a] leading-relaxed">
                                            {agentInfo.description}
                                        </p>
                                    </div>

                                    {/* Status */}
                                    <div className="px-4 py-3 border-b border-[#1a1a25]">
                                        <div className="flex items-center justify-between">
                                            <span className="text-xs text-[#4a4a5a] uppercase tracking-wider">
                                                Status
                                            </span>
                                            <span
                                                className="text-xs font-bold uppercase"
                                                style={{ color: config.color }}
                                            >
                                                {config.label}
                                            </span>
                                        </div>
                                    </div>

                                    {/* Stats Section */}
                                    <div className="border-b border-[#1a1a25]">
                                        <button
                                            onClick={() => toggleSection("stats")}
                                            className="w-full px-4 py-3 flex items-center justify-between hover:bg-[#1a1a25]/50 transition-colors"
                                        >
                                            <div className="flex items-center gap-2">
                                                <Activity size={14} className="text-cyan-400" />
                                                <span className="text-xs text-[#8a8a9a] uppercase tracking-wider">
                                                    Statistics
                                                </span>
                                            </div>
                                            {expandedSections.stats ? (
                                                <ChevronDown size={14} className="text-[#4a4a5a]" />
                                            ) : (
                                                <ChevronRight size={14} className="text-[#4a4a5a]" />
                                            )}
                                        </button>
                                        {expandedSections.stats && (
                                            <div className="px-4 pb-3 grid grid-cols-2 gap-3">
                                                <div className="bg-[#1a1a25] rounded-lg p-3">
                                                    <div className="text-lg font-bold text-[#00ffff] font-mono">
                                                        {agentStats.discovered}
                                                    </div>
                                                    <div className="text-[10px] text-[#4a4a5a] uppercase">
                                                        Discovered
                                                    </div>
                                                </div>
                                                <div className="bg-[#1a1a25] rounded-lg p-3">
                                                    <div className="text-lg font-bold text-[#00ff41] font-mono">
                                                        {agentStats.processed}
                                                    </div>
                                                    <div className="text-[10px] text-[#4a4a5a] uppercase">
                                                        Processed
                                                    </div>
                                                </div>
                                            </div>
                                        )}
                                    </div>

                                    {/* Tool Calls Section */}
                                    <div className="border-b border-[#1a1a25]">
                                        <button
                                            onClick={() => toggleSection("tools")}
                                            className="w-full px-4 py-3 flex items-center justify-between hover:bg-[#1a1a25]/50 transition-colors"
                                        >
                                            <div className="flex items-center gap-2">
                                                <Wrench size={14} className="text-amber-400" />
                                                <span className="text-xs text-[#8a8a9a] uppercase tracking-wider">
                                                    Tool Calls ({toolCalls.length})
                                                </span>
                                            </div>
                                            {expandedSections.tools ? (
                                                <ChevronDown size={14} className="text-[#4a4a5a]" />
                                            ) : (
                                                <ChevronRight size={14} className="text-[#4a4a5a]" />
                                            )}
                                        </button>
                                        {expandedSections.tools && (
                                            <div className="px-4 pb-3 space-y-2 max-h-40 overflow-y-auto">
                                                {toolCalls.length > 0 ? (
                                                    toolCalls.map((call, i) => (
                                                        <div
                                                            key={i}
                                                            className="flex items-center gap-2 text-xs bg-[#1a1a25] rounded px-2 py-1.5"
                                                        >
                                                            <Terminal size={10} className="text-amber-400 shrink-0" />
                                                            <span className="text-[#00ffff] font-mono truncate">
                                                                {call.tool}
                                                            </span>
                                                        </div>
                                                    ))
                                                ) : (
                                                    <div className="text-xs text-[#4a4a5a] text-center py-2">
                                                        No tool calls yet
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>

                                    {/* Logs Section */}
                                    <div>
                                        <button
                                            onClick={() => toggleSection("logs")}
                                            className="w-full px-4 py-3 flex items-center justify-between hover:bg-[#1a1a25]/50 transition-colors"
                                        >
                                            <div className="flex items-center gap-2">
                                                <MessageSquare size={14} className="text-purple-400" />
                                                <span className="text-xs text-[#8a8a9a] uppercase tracking-wider">
                                                    Logs ({filteredLogs.length})
                                                </span>
                                            </div>
                                            {expandedSections.logs ? (
                                                <ChevronDown size={14} className="text-[#4a4a5a]" />
                                            ) : (
                                                <ChevronRight size={14} className="text-[#4a4a5a]" />
                                            )}
                                        </button>
                                        {expandedSections.logs && (
                                            <div className="px-4 pb-3 space-y-1 max-h-64 overflow-y-auto">
                                                {filteredLogs.length > 0 ? (
                                                    filteredLogs.map((log, i) => (
                                                        <div
                                                            key={i}
                                                            className="text-xs bg-[#1a1a25] rounded px-2 py-1.5"
                                                        >
                                                            <div className="flex items-center gap-2 mb-0.5">
                                                                <span
                                                                    className={`text-[10px] font-mono ${
                                                                        log.level === "ERROR"
                                                                            ? "text-red-400"
                                                                            : log.level === "WARNING"
                                                                            ? "text-amber-400"
                                                                            : "text-[#4a4a5a]"
                                                                    }`}
                                                                >
                                                                    [{log.level}]
                                                                </span>
                                                                <span className="text-[10px] text-[#3a3a4a] font-mono">
                                                                    {new Date(log.timestamp).toLocaleTimeString()}
                                                                </span>
                                                            </div>
                                                            <p className="text-[#8a8a9a] truncate">{log.message}</p>
                                                        </div>
                                                    ))
                                                ) : (
                                                    <div className="text-xs text-[#4a4a5a] text-center py-2">
                                                        No logs for this agent
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                </>
                            ) : (
                                <div className="flex items-center justify-center h-full">
                                    <div className="text-center">
                                        <Activity size={32} className="text-[#2a2a3a] mx-auto mb-3" />
                                        <p className="text-sm text-[#4a4a5a]">Select an agent to inspect</p>
                                    </div>
                                </div>
                            )}
                        </div>
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    );
}
