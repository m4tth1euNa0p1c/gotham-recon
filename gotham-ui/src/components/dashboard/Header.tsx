"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Shield,
  Play,
  Square,
  Clock,
  Target,
  Wifi,
  WifiOff,
  Cpu,
  Database,
  Loader2,
  XCircle,
  AlertTriangle,
} from "lucide-react";
import { useMissionStore, useGraphStore } from "@/stores";
import { MissionMode } from "@/services";

export default function Header() {
  // Mission State from store
  const currentMission = useMissionStore((state) => state.currentMission);
  const isLoading = useMissionStore((state) => state.isLoading);
  const connectionStatus = useMissionStore((state) => state.connectionStatus);
  const startMissionAction = useMissionStore((state) => state.startMission);
  const cancelMission = useMissionStore((state) => state.cancelMission);
  const subscribeToLogs = useMissionStore((state) => state.subscribeToLogs);
  const unsubscribeFromLogs = useMissionStore((state) => state.unsubscribeFromLogs);

  // Graph State
  const graphSubscribe = useGraphStore((state) => state.subscribe);
  const graphUnsubscribe = useGraphStore((state) => state.unsubscribe);
  const graphFetch = useGraphStore((state) => state.fetchGraph);
  const graphReset = useGraphStore((state) => state.reset);
  const nodeCount = useGraphStore((state) => state.nodes.size);
  const edgeCount = useGraphStore((state) => state.edges.length);

  // Local state for form
  const [targetDomain, setTargetDomain] = useState("");
  const [mode, setMode] = useState<MissionMode>("AGGRESSIVE");
  const [elapsedTime, setElapsedTime] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [isCancelling, setIsCancelling] = useState(false);
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);

  // Derived state
  const isActive = currentMission?.status === "running";
  const isPaused = currentMission?.status === "paused";
  const isConnected = connectionStatus === "connected";

  // Timer for elapsed time
  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;

    if (isActive && currentMission?.createdAt) {
      interval = setInterval(() => {
        const start = new Date(currentMission.createdAt).getTime();
        setElapsedTime(Math.floor((Date.now() - start) / 1000));
      }, 1000);
    } else if (!isActive) {
      setElapsedTime(0);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isActive, currentMission?.createdAt]);

  // Format elapsed time
  const formatTime = useCallback((seconds: number) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  }, []);

  // Handle mission start
  const handleStartMission = async () => {
    if (!targetDomain.trim()) {
      setError("Please enter a target domain");
      return;
    }

    // Validate domain format
    const domainRegex = /^[a-zA-Z0-9][a-zA-Z0-9-]{0,61}[a-zA-Z0-9]?(\.[a-zA-Z]{2,})+$/;
    if (!domainRegex.test(targetDomain.trim())) {
      setError("Invalid domain format (e.g., example.com)");
      return;
    }

    setError(null);

    // Reset graph state before starting new mission
    graphReset();

    const mission = await startMissionAction({
      targetDomain: targetDomain.trim(),
      mode,
    });

    if (mission) {
      // Subscribe to real-time updates
      subscribeToLogs(mission.id);
      graphSubscribe(mission.id);
      graphFetch(mission.id);
    }
  };

  // Handle mission cancel with confirmation
  const handleCancelClick = () => {
    setShowCancelConfirm(true);
  };

  // Confirm cancellation
  const handleConfirmCancel = async () => {
    setIsCancelling(true);
    setShowCancelConfirm(false);

    try {
      const success = await cancelMission();

      if (success) {
        // Unsubscribe from real-time updates
        unsubscribeFromLogs();
        graphUnsubscribe();
        setError(null);
      } else {
        setError("Failed to cancel mission");
      }
    } catch (err) {
      setError("Error cancelling mission");
    } finally {
      setIsCancelling(false);
    }
  };

  // Mode colors
  const modeColors = {
    STEALTH: { bg: "bg-[#00ff41]/20", text: "text-[#00ff41]", border: "border-[#00ff41]/50" },
    AGGRESSIVE: { bg: "bg-[#ff0040]/20", text: "text-[#ff0040]", border: "border-[#ff0040]/50" },
    BALANCED: { bg: "bg-[#ff6600]/20", text: "text-[#ff6600]", border: "border-[#ff6600]/50" },
  };

  return (
    <header className="h-16 border-b border-[#1a1a25] px-4 flex items-center justify-between bg-[#0d0d12]/90 backdrop-blur-md relative">
      {/* Left: Logo & Title */}
      <div className="flex items-center gap-3">
        <div className="relative">
          <Shield size={24} className="text-[#00ffff]" />
          <motion.div
            animate={{ opacity: [0.3, 1, 0.3] }}
            transition={{ duration: 2, repeat: Infinity }}
            className="absolute inset-0 blur-md bg-[#00ffff]/30"
          />
        </div>
        <div>
          <h1 className="font-display text-lg font-bold tracking-wider text-[#00ffff] cyan-glow">
            GOTHAM RECON
          </h1>
          <span className="text-[10px] text-[#00ff41] uppercase tracking-widest">
            War Room v3.0
          </span>
        </div>
      </div>

      {/* Center: Target Input or Active Target */}
      <div className="flex items-center gap-4">
        {!isActive ? (
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2 bg-[#0f0f18] border border-[#1e1e2e] px-3 py-1.5 rounded">
              <Target size={12} className="text-[#bf00ff]" />
              <input
                type="text"
                value={targetDomain}
                onChange={(e) => {
                  setTargetDomain(e.target.value);
                  setError(null);
                }}
                onKeyDown={(e) => e.key === "Enter" && handleStartMission()}
                placeholder="target.com"
                className="bg-transparent text-[#00ffff] font-mono text-sm w-40 focus:outline-none placeholder-[#3a3a4a]"
              />
            </div>

            {/* Mode Selector */}
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as MissionMode)}
              className={`px-2 py-1.5 text-[10px] ${modeColors[mode].bg} ${modeColors[mode].text} border ${modeColors[mode].border} rounded font-bold uppercase bg-transparent cursor-pointer focus:outline-none`}
            >
              <option value="STEALTH" className="bg-[#0f0f18]">
                STEALTH
              </option>
              <option value="BALANCED" className="bg-[#0f0f18]">
                BALANCED
              </option>
              <option value="AGGRESSIVE" className="bg-[#0f0f18]">
                AGGRESSIVE
              </option>
            </select>
          </div>
        ) : (
          <div className="flex items-center gap-2 bg-[#0f0f18] border border-[#1e1e2e] px-3 py-1.5 rounded">
            <Target size={12} className="text-[#bf00ff]" />
            <span className="text-[#00ffff] font-mono text-sm">
              {currentMission?.targetDomain || targetDomain}
            </span>
            <span
              className={`px-1.5 py-0.5 text-[10px] ${modeColors[currentMission?.mode || mode].bg} ${modeColors[currentMission?.mode || mode].text} border ${modeColors[currentMission?.mode || mode].border} rounded font-bold`}
            >
              {currentMission?.mode || mode}
            </span>
          </div>
        )}

        {/* Error Message */}
        <AnimatePresence>
          {error && (
            <motion.span
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
              className="text-[#ff0040] text-xs flex items-center gap-1"
            >
              <AlertTriangle size={12} />
              {error}
            </motion.span>
          )}
        </AnimatePresence>

        {/* Quick Stats (only when active) */}
        {isActive && (
          <div className="hidden md:flex items-center gap-4 text-xs">
            <div className="flex items-center gap-1.5">
              <Database size={10} className="text-[#00ffff]" />
              <span className="text-[#4a4a5a]">NODES:</span>
              <motion.span
                key={nodeCount}
                initial={{ scale: 1.2, color: "#00ff41" }}
                animate={{ scale: 1, color: "#00ff41" }}
                className="font-bold font-mono"
              >
                {nodeCount}
              </motion.span>
            </div>
            <div className="flex items-center gap-1.5">
              <Cpu size={10} className="text-[#bf00ff]" />
              <span className="text-[#4a4a5a]">EDGES:</span>
              <motion.span
                key={edgeCount}
                initial={{ scale: 1.2, color: "#00ff41" }}
                animate={{ scale: 1, color: "#00ff41" }}
                className="font-bold font-mono"
              >
                {edgeCount}
              </motion.span>
            </div>
            <div className="flex items-center gap-1.5">
              {isConnected ? (
                <Wifi size={10} className="text-[#00ff41]" />
              ) : (
                <WifiOff size={10} className="text-[#ff0040]" />
              )}
              <span className={isConnected ? "text-[#00ff41]" : "text-[#ff0040]"}>
                {isConnected ? "LIVE" : "OFFLINE"}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Right: Controls */}
      <div className="flex items-center gap-3">
        {/* Status */}
        <div className="flex items-center gap-2 text-xs">
          {isActive ? (
            <>
              <motion.div
                animate={{ scale: [1, 1.2, 1], opacity: [1, 0.7, 1] }}
                transition={{ duration: 1, repeat: Infinity }}
                className="w-2 h-2 rounded-full bg-[#00ff41]"
                style={{ boxShadow: "0 0 8px #00ff41" }}
              />
              <span className="text-[#00ff41] font-bold uppercase tracking-wider">
                LIVE
              </span>
            </>
          ) : isPaused ? (
            <>
              <div className="w-2 h-2 rounded-full bg-yellow-500" />
              <span className="text-yellow-500 uppercase tracking-wider">
                PAUSED
              </span>
            </>
          ) : currentMission?.status === "cancelled" ? (
            <>
              <div className="w-2 h-2 rounded-full bg-[#ff0040]" />
              <span className="text-[#ff0040] uppercase tracking-wider">
                CANCELLED
              </span>
            </>
          ) : (
            <>
              <div className="w-2 h-2 rounded-full bg-[#4a4a5a]" />
              <span className="text-[#4a4a5a] uppercase tracking-wider">IDLE</span>
            </>
          )}
        </div>

        {/* Timer */}
        <div className="flex items-center gap-1.5 bg-[#0f0f18] border border-[#1e1e2e] px-2 py-1 rounded">
          <Clock size={10} className="text-[#4a4a5a]" />
          <span className="font-mono text-xs text-[#00ffff]">
            {formatTime(elapsedTime)}
          </span>
        </div>

        {/* Start/Stop */}
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={isActive ? handleCancelClick : handleStartMission}
          disabled={isLoading || isCancelling}
          className={`px-4 py-1.5 rounded flex items-center gap-2 font-bold text-xs uppercase tracking-wider transition-all ${
            isActive
              ? "bg-[#ff0040]/20 text-[#ff0040] border border-[#ff0040]/50 hover:bg-[#ff0040]/30"
              : "bg-[#00ffff] text-[#0a0a0f] hover:shadow-[0_0_20px_rgba(0,255,255,0.5)]"
          } ${isLoading || isCancelling ? "opacity-50 cursor-not-allowed" : ""}`}
        >
          {isLoading ? (
            <>
              <Loader2 size={10} className="animate-spin" />
              STARTING...
            </>
          ) : isCancelling ? (
            <>
              <Loader2 size={10} className="animate-spin" />
              CANCELLING...
            </>
          ) : isActive ? (
            <>
              <Square size={10} />
              ABORT
            </>
          ) : (
            <>
              <Play size={10} />
              ENGAGE
            </>
          )}
        </motion.button>
      </div>

      {/* Cancel Confirmation Modal */}
      <AnimatePresence>
        {showCancelConfirm && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 bg-[#0a0a0f]/80 backdrop-blur-sm flex items-center justify-center z-50"
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="bg-[#0d0d12] border border-[#ff0040]/30 rounded-lg p-6 max-w-sm"
            >
              <div className="flex items-center gap-3 mb-4">
                <XCircle size={24} className="text-[#ff0040]" />
                <h3 className="text-white font-bold">Abort Mission?</h3>
              </div>
              <p className="text-[#8a8a9a] text-sm mb-6">
                This will stop all reconnaissance activities and cannot be undone.
                Discovered assets will be preserved.
              </p>
              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => setShowCancelConfirm(false)}
                  className="px-4 py-2 text-sm text-[#8a8a9a] hover:text-white transition-colors"
                >
                  Continue Mission
                </button>
                <button
                  onClick={handleConfirmCancel}
                  className="px-4 py-2 bg-[#ff0040]/20 text-[#ff0040] border border-[#ff0040]/50 rounded text-sm font-bold hover:bg-[#ff0040]/30 transition-colors"
                >
                  Abort Mission
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
