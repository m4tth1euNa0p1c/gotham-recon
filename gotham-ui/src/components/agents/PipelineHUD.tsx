"use client";

/**
 * PipelineHUD
 * Displays the current pipeline status with phase, timer, counters, and controls.
 */

import { useState, useEffect, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
    Play,
    Pause,
    RefreshCw,
    User,
    Timer,
    Globe,
    Server,
    AlertTriangle,
    Link2,
    Wifi,
    WifiOff,
    ChevronRight,
} from "lucide-react";
import { useMissionStore, useGraphStore } from "@/stores";

interface PipelineHUDProps {
    onOpenInspector?: () => void;
    onRefresh?: () => void;
    isRefreshing?: boolean;
    liveMode?: boolean;
    onToggleLive?: () => void;
}

// Phase configuration
const PHASE_CONFIG: Record<string, { label: string; color: string }> = {
    "INIT": { label: "Initializing", color: "#6366f1" },
    "PASSIVE_RECON": { label: "Passive Recon", color: "#06b6d4" },
    "ACTIVE_RECON": { label: "Active Recon", color: "#8b5cf6" },
    "JS_ANALYSIS": { label: "JS Analysis", color: "#f59e0b" },
    "ENRICHMENT": { label: "Enrichment", color: "#10b981" },
    "VERIFICATION": { label: "Verification", color: "#ef4444" },
    "REPORTING": { label: "Reporting", color: "#3b82f6" },
    "COMPLETED": { label: "Completed", color: "#00ff41" },
};

export default function PipelineHUD({
    onOpenInspector,
    onRefresh,
    isRefreshing = false,
    liveMode = true,
    onToggleLive,
}: PipelineHUDProps) {
    // Mission state
    const currentMission = useMissionStore((state) => state.currentMission);
    const connectionStatus = useMissionStore((state) => state.connectionStatus);

    // Graph state for stats
    const graphNodes = useGraphStore((state) => state.nodes);

    // Timer state
    const [elapsedTime, setElapsedTime] = useState(0);

    // Calculate stats from graph
    const stats = useMemo(() => {
        const nodes = Array.from(graphNodes.values());
        return {
            subdomains: nodes.filter(n => n.type === "SUBDOMAIN").length,
            services: nodes.filter(n => n.type === "HTTP_SERVICE").length,
            endpoints: nodes.filter(n => n.type === "ENDPOINT").length,
            vulnerabilities: nodes.filter(n => n.type === "VULNERABILITY").length,
        };
    }, [graphNodes]);

    // Timer effect
    useEffect(() => {
        if (!currentMission?.createdAt) {
            setElapsedTime(0);
            return;
        }

        const startTime = new Date(currentMission.createdAt).getTime();
        const isRunning = currentMission.status === "running";

        if (!isRunning) {
            // For completed missions, show final elapsed time
            const endTime = currentMission.updatedAt
                ? new Date(currentMission.updatedAt).getTime()
                : Date.now();
            setElapsedTime(Math.floor((endTime - startTime) / 1000));
            return;
        }

        // Update timer every second while running
        const updateTimer = () => {
            setElapsedTime(Math.floor((Date.now() - startTime) / 1000));
        };

        updateTimer();
        const interval = setInterval(updateTimer, 1000);

        return () => clearInterval(interval);
    }, [currentMission?.createdAt, currentMission?.status, currentMission?.updatedAt]);

    // Format elapsed time
    const formatTime = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
    };

    // Get current phase config
    const currentPhase = currentMission?.currentPhase?.toUpperCase() || "";
    const phaseConfig = PHASE_CONFIG[currentPhase] || PHASE_CONFIG["INIT"];
    const isActive = currentMission?.status === "running";
    const isConnected = connectionStatus === "connected";

    return (
        <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-gradient-to-br from-[#0d0d12]/95 to-[#1a1a25]/95 backdrop-blur-md rounded-xl border border-cyan-500/20 shadow-lg shadow-cyan-500/10 overflow-hidden"
        >
            {/* Phase Header */}
            <div
                className="px-4 py-2 border-b border-[#1a1a25]"
                style={{
                    background: `linear-gradient(90deg, ${phaseConfig.color}15, transparent)`,
                }}
            >
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        {/* Phase Indicator */}
                        <div className="flex items-center gap-2">
                            <div
                                className="w-2 h-2 rounded-full"
                                style={{
                                    backgroundColor: phaseConfig.color,
                                    boxShadow: isActive ? `0 0 8px ${phaseConfig.color}` : "none",
                                }}
                            />
                            <span
                                className="text-xs font-bold uppercase tracking-wider"
                                style={{ color: phaseConfig.color }}
                            >
                                {phaseConfig.label}
                            </span>
                        </div>

                        {/* Timer */}
                        <div className="flex items-center gap-1.5 px-2 py-0.5 bg-[#1a1a25] rounded">
                            <Timer size={12} className="text-[#4a4a5a]" />
                            <span className="text-xs font-mono text-[#8a8a9a]">
                                {formatTime(elapsedTime)}
                            </span>
                        </div>
                    </div>

                    {/* Connection Status */}
                    <div
                        className={`flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium ${
                            isConnected
                                ? "bg-[#00ff41]/10 text-[#00ff41]"
                                : "bg-[#1a1a25] text-[#4a4a5a]"
                        }`}
                    >
                        {isConnected ? <Wifi size={10} /> : <WifiOff size={10} />}
                        {isConnected ? "LIVE" : "OFFLINE"}
                    </div>
                </div>
            </div>

            {/* Stats Grid */}
            <div className="px-4 py-3">
                <div className="grid grid-cols-4 gap-3">
                    {/* Subdomains */}
                    <div className="flex items-center gap-2">
                        <div className="p-1.5 bg-cyan-500/10 rounded">
                            <Globe size={12} className="text-cyan-400" />
                        </div>
                        <div>
                            <div className="text-sm font-bold text-white font-mono">
                                {stats.subdomains}
                            </div>
                            <div className="text-[10px] text-[#4a4a5a] uppercase">Subs</div>
                        </div>
                    </div>

                    {/* Services */}
                    <div className="flex items-center gap-2">
                        <div className="p-1.5 bg-purple-500/10 rounded">
                            <Server size={12} className="text-purple-400" />
                        </div>
                        <div>
                            <div className="text-sm font-bold text-white font-mono">
                                {stats.services}
                            </div>
                            <div className="text-[10px] text-[#4a4a5a] uppercase">Services</div>
                        </div>
                    </div>

                    {/* Endpoints */}
                    <div className="flex items-center gap-2">
                        <div className="p-1.5 bg-amber-500/10 rounded">
                            <Link2 size={12} className="text-amber-400" />
                        </div>
                        <div>
                            <div className="text-sm font-bold text-white font-mono">
                                {stats.endpoints}
                            </div>
                            <div className="text-[10px] text-[#4a4a5a] uppercase">Endpoints</div>
                        </div>
                    </div>

                    {/* Vulnerabilities */}
                    <div className="flex items-center gap-2">
                        <div className="p-1.5 bg-red-500/10 rounded">
                            <AlertTriangle size={12} className="text-red-400" />
                        </div>
                        <div>
                            <div className="text-sm font-bold text-white font-mono">
                                {stats.vulnerabilities}
                            </div>
                            <div className="text-[10px] text-[#4a4a5a] uppercase">Vulns</div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Controls */}
            <div className="px-4 py-2 border-t border-[#1a1a25] flex items-center justify-between">
                <div className="flex items-center gap-2">
                    {/* Live/Pause Toggle */}
                    {onToggleLive && (
                        <button
                            onClick={onToggleLive}
                            className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                                liveMode
                                    ? "bg-[#00ffff]/20 text-[#00ffff] hover:bg-[#00ffff]/30"
                                    : "bg-[#1a1a25] text-[#4a4a5a] hover:bg-[#2a2a3a]"
                            }`}
                        >
                            {liveMode ? <Pause size={10} /> : <Play size={10} />}
                            {liveMode ? "PAUSE" : "RESUME"}
                        </button>
                    )}

                    {/* Refresh */}
                    {onRefresh && (
                        <button
                            onClick={onRefresh}
                            disabled={isRefreshing}
                            className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium bg-[#1a1a25] text-[#4a4a5a] hover:bg-[#2a2a3a] transition-colors disabled:opacity-50"
                        >
                            <RefreshCw size={10} className={isRefreshing ? "animate-spin" : ""} />
                            REFRESH
                        </button>
                    )}
                </div>

                {/* Agent Inspector Button */}
                {onOpenInspector && (
                    <button
                        onClick={onOpenInspector}
                        className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium bg-[#bf00ff]/20 text-[#bf00ff] hover:bg-[#bf00ff]/30 transition-colors"
                    >
                        <User size={10} />
                        Inspector
                        <ChevronRight size={10} />
                    </button>
                )}
            </div>
        </motion.div>
    );
}
