"use client";

import { motion, AnimatePresence } from "framer-motion";
import {
  ChevronUp,
  Terminal,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  Zap,
  Bug,
  Wifi,
  WifiOff,
  Trash2,
} from "lucide-react";
import { useEffect, useRef } from "react";
import { useMissionStore, useUIStore } from "@/stores";
import { LogEntry } from "@/services";

const levelConfig = {
  INFO: { color: "text-[#00ffff]", icon: Terminal, prefix: "[*]", bg: "bg-[#00ffff]/5" },
  DEBUG: { color: "text-[#bf00ff]", icon: Zap, prefix: "[~]", bg: "bg-[#bf00ff]/5" },
  WARNING: { color: "text-[#ff6600]", icon: AlertTriangle, prefix: "[!]", bg: "bg-[#ff6600]/5" },
  ERROR: { color: "text-[#ff0040]", icon: Bug, prefix: "[X]", bg: "bg-[#ff0040]/5" },
};

export default function MissionPanel() {
  // UI State
  const expanded = useUIStore((state) => state.logPanelExpanded);
  const toggleExpanded = useUIStore((state) => state.toggleLogPanel);

  // Mission State
  const currentMission = useMissionStore((state) => state.currentMission);
  const logs = useMissionStore((state) => state.logs);
  const connectionStatus = useMissionStore((state) => state.connectionStatus);
  const clearLogs = useMissionStore((state) => state.clearLogs);

  const logsEndRef = useRef<HTMLDivElement>(null);

  // Derived state
  const isActive = currentMission?.status === "running";
  const isConnected = connectionStatus === "connected";

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (logsEndRef.current && expanded) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, expanded]);

  // Format timestamp
  const formatTime = (timestamp: string) => {
    try {
      return new Date(timestamp).toLocaleTimeString("en-US", { hour12: false });
    } catch {
      return timestamp;
    }
  };

  // Get config for log level
  const getConfig = (level: LogEntry["level"]) => {
    return levelConfig[level] || levelConfig.INFO;
  };

  return (
    <motion.div
      animate={{ height: expanded ? 220 : 36 }}
      className="border-t border-[#1a1a25] bg-[#0d0d12]/95 backdrop-blur-md"
    >
      {/* Header */}
      <div className="h-9 px-4 flex items-center justify-between text-xs">
        <button
          onClick={toggleExpanded}
          className="flex items-center gap-3 hover:bg-[#1a1a25]/50 transition-colors rounded px-2 py-1"
        >
          <Terminal size={12} className="text-[#00ff41]" />
          <span className="text-[#00ff41] font-bold uppercase tracking-wider">
            Mission Log
          </span>
          <span className="text-[#4a4a5a]">|</span>
          <span className="text-[#4a4a5a] font-mono">{logs.length} entries</span>

          {/* Status indicator */}
          {isActive && (
            <div className="flex items-center gap-2">
              {isConnected ? (
                <span className="flex items-center gap-1 text-[#00ff41]">
                  <Wifi size={10} />
                  <motion.span
                    animate={{ opacity: [1, 0.3, 1] }}
                    transition={{ duration: 0.8, repeat: Infinity }}
                  >
                    LIVE
                  </motion.span>
                </span>
              ) : (
                <span className="flex items-center gap-1 text-[#ff6600]">
                  <WifiOff size={10} />
                  <span>CONNECTING</span>
                </span>
              )}
            </div>
          )}

          <motion.div animate={{ rotate: expanded ? 180 : 0 }}>
            <ChevronUp size={14} className="text-[#4a4a5a]" />
          </motion.div>
        </button>

        {/* Clear logs button */}
        {logs.length > 0 && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              clearLogs();
            }}
            className="flex items-center gap-1 text-[#4a4a5a] hover:text-[#ff0040] transition-colors px-2 py-1 rounded hover:bg-[#1a1a25]/50"
            title="Clear logs"
          >
            <Trash2 size={12} />
            <span>Clear</span>
          </button>
        )}
      </div>

      {/* Log Content */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="h-[180px] overflow-y-auto px-4 pb-3 cyber-grid"
          >
            <div className="font-mono text-[11px] space-y-0.5">
              {logs.length === 0 ? (
                <div className="text-[#4a4a5a] py-4 text-center">
                  No logs yet. Start a mission to see activity.
                </div>
              ) : (
                // Reverse to show newest at bottom
                [...logs].reverse().map((log, i) => {
                  const config = getConfig(log.level);
                  const Icon = config.icon;

                  return (
                    <motion.div
                      key={`${log.timestamp}-${i}`}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      className={`flex items-start gap-2 py-0.5 hover:${config.bg} px-1 rounded group`}
                    >
                      <span className="text-[#3a3a4a] w-16 shrink-0">
                        {formatTime(log.timestamp)}
                      </span>
                      <span className={`${config.color} w-4 shrink-0 font-bold`}>
                        {config.prefix}
                      </span>
                      <span
                        className={`${config.color} w-20 shrink-0 uppercase font-bold truncate`}
                        title={log.phase || "SYSTEM"}
                      >
                        [{log.phase || "SYSTEM"}]
                      </span>
                      <span className="text-[#8a8a9a] flex-1">{log.message}</span>

                      {/* Show metadata on hover if present */}
                      {log.metadata && Object.keys(log.metadata).length > 0 && (
                        <span
                          className="text-[#4a4a5a] opacity-0 group-hover:opacity-100 transition-opacity cursor-help"
                          title={JSON.stringify(log.metadata, null, 2)}
                        >
                          [+]
                        </span>
                      )}
                    </motion.div>
                  );
                })
              )}
              <div ref={logsEndRef} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
