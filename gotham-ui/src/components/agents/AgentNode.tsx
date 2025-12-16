"use client";

import { memo } from "react";
import { Handle, Position, NodeProps } from "@xyflow/react";
import { motion } from "framer-motion";
import {
    CheckCircle2,
    Loader2,
    Clock,
    AlertCircle,
    Wrench,
    Cpu,
    Zap
} from "lucide-react";

interface AgentData {
    name: string;
    role: string;
    status: "pending" | "running" | "completed" | "error";
    progress: number;
    tool: string | null;
    stats?: {
        found?: number;
        processed?: number;
    };
}

const statusConfig = {
    pending: {
        icon: Clock,
        color: "#4a4a5a",
        glow: "none",
        border: "#2a2a3a",
        bg: "#141421"
    },
    running: {
        icon: Loader2,
        color: "#00ffff",
        glow: "0 0 15px rgba(0,255,255,0.4)",
        border: "#00ffff",
        bg: "rgba(0,255,255,0.05)"
    },
    completed: {
        icon: CheckCircle2,
        color: "#00ff41",
        glow: "0 0 10px rgba(0,255,65,0.3)",
        border: "#00ff41",
        bg: "rgba(0,255,65,0.05)"
    },
    error: {
        icon: AlertCircle,
        color: "#ff0040",
        glow: "0 0 15px rgba(255,0,64,0.4)",
        border: "#ff0040",
        bg: "rgba(255,0,64,0.05)"
    },
};

function AgentNode({ data }: NodeProps) {
    const agentData = data as unknown as AgentData;
    const config = statusConfig[agentData.status];
    const StatusIcon = config.icon;

    return (
        <>
            <Handle
                type="target"
                position={Position.Top}
                className="!w-2 !h-2 !bg-[#bf00ff] !border-none"
                style={{ boxShadow: '0 0 6px #bf00ff' }}
            />

            <motion.div
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                className="min-w-[120px] rounded-md overflow-hidden bg-[#0d0d12]/90 backdrop-blur-sm"
                style={{
                    border: `1px solid ${config.border}`,
                    boxShadow: config.glow
                }}
            >
                {/* Header Bar with Gradient */}
                <div
                    className="h-1.5 w-full relative overflow-hidden"
                    style={{ background: `linear-gradient(90deg, ${config.color}, transparent)` }}
                >
                    {agentData.status === "running" && (
                        <motion.div
                            className="absolute inset-0 bg-white/50"
                            initial={{ x: "-100%" }}
                            animate={{ x: "100%" }}
                            transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
                        />
                    )}
                </div>

                <div className="p-2">
                    {/* Agent Info - Simplified */}
                    <div className="flex items-center gap-2">
                        <div
                            className="w-6 h-6 rounded flex items-center justify-center relative shrink-0"
                            style={{
                                background: `${config.color}10`,
                                border: `1px solid ${config.color}30`
                            }}
                        >
                            {/* Spinning ring for running state */}
                            {agentData.status === "running" && (
                                <motion.div
                                    className="absolute inset-0 rounded border-t border-r border-[#00ffff]"
                                    animate={{ rotate: 360 }}
                                    transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
                                />
                            )}
                            <StatusIcon
                                size={14}
                                color={config.color}
                            />
                        </div>
                        <div className="flex-1 min-w-0">
                            <div
                                className="font-bold text-xs uppercase tracking-wide truncate"
                                style={{ color: config.color }}
                            >
                                {agentData.name}
                            </div>
                        </div>
                    </div>
                </div>
            </motion.div>

            <Handle
                type="source"
                position={Position.Bottom}
                className="!w-2 !h-2 !bg-[#00ffff] !border-none"
                style={{ boxShadow: '0 0 6px #00ffff' }}
            />
        </>
    );
}

export default memo(AgentNode);
