"use client";

/**
 * LiveStreamStatus
 * Displays real-time connection status and event queue metrics.
 * Shows buffered events count, processing rate, and connection health.
 */

import React from "react";
import { motion } from "framer-motion";
import {
  Wifi,
  WifiOff,
  Pause,
  Play,
  Activity,
  Zap,
  Loader2,
  AlertCircle,
  RefreshCw,
  Clock,
  Database,
} from "lucide-react";
import { useLiveStreamOptional, StreamStatus } from "@/providers/LiveStreamProvider";

interface LiveStreamStatusProps {
  className?: string;
  compact?: boolean;
}

// Status colors
const STATUS_COLORS: Record<StreamStatus, { bg: string; text: string; icon: string }> = {
  connected: { bg: "bg-emerald-500/20", text: "text-emerald-400", icon: "text-emerald-400" },
  connecting: { bg: "bg-amber-500/20", text: "text-amber-400", icon: "text-amber-400" },
  reconnecting: { bg: "bg-amber-500/20", text: "text-amber-400", icon: "text-amber-400" },
  disconnected: { bg: "bg-slate-500/20", text: "text-slate-400", icon: "text-slate-400" },
  error: { bg: "bg-red-500/20", text: "text-red-400", icon: "text-red-400" },
  historical: { bg: "bg-blue-500/20", text: "text-blue-400", icon: "text-blue-400" },
};

export default function LiveStreamStatus({ className = "", compact = false }: LiveStreamStatusProps) {
  const stream = useLiveStreamOptional();

  // If no provider, show disconnected state
  if (!stream) {
    return (
      <div className={`flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-800/50 border border-slate-700 ${className}`}>
        <WifiOff size={14} className="text-slate-500" />
        <span className="text-xs text-slate-500">No Stream</span>
      </div>
    );
  }

  const { status, isLive, isPaused, isHistorical, queueLength, processedCount, eventsPerSecond, pause, resume, disconnect } = stream;
  const statusConfig = STATUS_COLORS[status];

  // Status icon
  const StatusIcon = () => {
    switch (status) {
      case "historical":
        return <Database size={14} className={statusConfig.icon} />;
      case "connected":
        return isLive ? (
          <motion.div
            animate={{ scale: [1, 1.2, 1] }}
            transition={{ duration: 2, repeat: Infinity }}
          >
            <Wifi size={14} className={statusConfig.icon} />
          </motion.div>
        ) : (
          <Wifi size={14} className={statusConfig.icon} />
        );
      case "connecting":
      case "reconnecting":
        return <Loader2 size={14} className={`animate-spin ${statusConfig.icon}`} />;
      case "error":
        return <AlertCircle size={14} className={statusConfig.icon} />;
      default:
        return <WifiOff size={14} className={statusConfig.icon} />;
    }
  };

  // Status label
  const getStatusLabel = () => {
    if (isPaused) return "PAUSED";
    switch (status) {
      case "historical":
        return "HISTORY";
      case "connected":
        return "LIVE";
      case "connecting":
        return "LOADING";
      case "reconnecting":
        return "RECONNECTING";
      case "error":
        return "ERROR";
      default:
        return "OFFLINE";
    }
  };

  if (compact) {
    return (
      <div className={`flex items-center gap-2 ${className}`}>
        <StatusIcon />
        <span className={`text-xs font-medium ${statusConfig.text}`}>
          {getStatusLabel()}
        </span>
        {queueLength > 0 && (
          <span className="text-xs text-slate-500 font-mono">
            ({queueLength})
          </span>
        )}
      </div>
    );
  }

  return (
    <div
      className={`flex items-center gap-4 px-4 py-2 rounded-lg border backdrop-blur-sm ${statusConfig.bg} ${
        status === "connected" ? "border-emerald-500/30" :
        status === "historical" ? "border-blue-500/30" : "border-slate-700"
      } ${className}`}
    >
      {/* Status Indicator */}
      <div className="flex items-center gap-2">
        <StatusIcon />
        <div className="flex flex-col">
          <span className={`text-xs font-bold ${statusConfig.text}`}>
            {getStatusLabel()}
          </span>
          {stream.missionId && (
            <span className="text-[10px] text-slate-500 font-mono truncate max-w-[100px]">
              {stream.missionId.substring(0, 8)}...
            </span>
          )}
        </div>
      </div>

      {/* Separator */}
      <div className="h-6 w-px bg-slate-700" />

      {/* Queue Metrics */}
      <div className="flex items-center gap-3">
        {/* Queue Length */}
        <div className="flex items-center gap-1.5" title="Events in queue">
          <Activity size={12} className="text-cyan-400" />
          <span className="text-xs font-mono text-slate-300">
            {queueLength}
          </span>
        </div>

        {/* Events per second */}
        <div className="flex items-center gap-1.5" title="Events per second">
          <Zap size={12} className="text-amber-400" />
          <span className="text-xs font-mono text-slate-300">
            {eventsPerSecond}/s
          </span>
        </div>

        {/* Processed count */}
        <div className="flex items-center gap-1.5" title="Total processed">
          <RefreshCw size={12} className="text-purple-400" />
          <span className="text-xs font-mono text-slate-300">
            {processedCount.toLocaleString()}
          </span>
        </div>
      </div>

      {/* Separator */}
      <div className="h-6 w-px bg-slate-700" />

      {/* Controls - Only show for live mode */}
      {!isHistorical && (
        <>
          <div className="h-6 w-px bg-slate-700" />
          <div className="flex items-center gap-1">
            {status === "connected" && (
              <button
                onClick={isPaused ? resume : pause}
                className={`p-1.5 rounded transition-colors ${
                  isPaused
                    ? "bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/30"
                    : "bg-slate-700 text-slate-400 hover:bg-slate-600 hover:text-white"
                }`}
                title={isPaused ? "Resume" : "Pause"}
              >
                {isPaused ? <Play size={12} /> : <Pause size={12} />}
              </button>
            )}

            {status === "connected" && (
              <button
                onClick={disconnect}
                className="p-1.5 rounded bg-slate-700 text-slate-400 hover:bg-red-500/20 hover:text-red-400 transition-colors"
                title="Disconnect"
              >
                <WifiOff size={12} />
              </button>
            )}
          </div>
        </>
      )}

      {/* Historical mode info */}
      {isHistorical && processedCount > 0 && (
        <div className="flex items-center gap-1.5 text-blue-400">
          <Clock size={12} />
          <span className="text-xs font-medium">Recorded Session</span>
        </div>
      )}
    </div>
  );
}
