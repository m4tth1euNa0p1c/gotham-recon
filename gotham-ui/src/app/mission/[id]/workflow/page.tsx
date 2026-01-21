"use client";

/**
 * Workflow Visualization Page
 * Real-time sequential workflow visualization that reacts to live events.
 * NO MOCK DATA - all data populated via WebSocket/SSE events from Python backend.
 *
 * Route: /mission/[mission-id]/workflow
 *
 * Design: Exact match to mock with radial gradient, resizable panels, ping animations
 */

import { useParams, useRouter } from "next/navigation";
import { useEffect, useCallback, useRef, useState, MouseEvent as ReactMouseEvent } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowLeft,
  Activity,
  Shield,
  Cpu,
  Database,
  WifiOff,
  RefreshCw,
  Clock,
  Zap,
} from "lucide-react";
import {
  WorkflowHierarchy,
  TracePanel,
  WorkflowControls,
  AgentPipeline,
  AssetMap,
} from "@/components/workflow";
import { useWorkflowStore } from "@/stores/workflowStore";
import { useMissionStore, useGraphStore } from "@/stores";
import { LiveStreamProvider, useLiveStream } from "@/providers/LiveStreamProvider";
import Sidebar from "@/components/dashboard/Sidebar";

// Status badge component matching mock design
const StatusBadge = ({ status }: { status: string }) => {
  const styles: Record<string, string> = {
    running: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30 animate-pulse",
    completed: "bg-blue-500/20 text-blue-400 border-blue-500/30",
    pending: "bg-slate-500/20 text-slate-400 border-slate-500/30",
    failed: "bg-red-500/20 text-red-400 border-red-500/30",
    error: "bg-red-500/20 text-red-400 border-red-500/30",
  };
  return (
    <span className={`px-2 py-0.5 rounded text-[10px] font-mono border ${styles[status] || styles.pending} uppercase tracking-wider`}>
      {status}
    </span>
  );
};

// Connection indicator with ping animation matching mock
const ConnectionIndicator = ({ status, isLive, isHistorical }: { status: string; isLive: boolean; isHistorical: boolean }) => {
  if (isHistorical) {
    return (
      <div className="flex items-center gap-2 bg-slate-800/50 px-3 py-1.5 rounded-full border border-slate-700/50">
        <div className="relative flex h-2 w-2">
          <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-400"></span>
        </div>
        <span className="text-[10px] font-bold tracking-wider text-cyan-400">HISTORY</span>
      </div>
    );
  }

  if (isLive) {
    return (
      <div className="flex items-center gap-2 bg-slate-800/50 px-3 py-1.5 rounded-full border border-slate-700/50">
        <div className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 bg-emerald-400"></span>
          <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400"></span>
        </div>
        <span className="text-[10px] font-bold tracking-wider text-emerald-400">LIVE</span>
      </div>
    );
  }

  if (status === "connecting" || status === "reconnecting") {
    return (
      <div className="flex items-center gap-2 bg-slate-800/50 px-3 py-1.5 rounded-full border border-slate-700/50">
        <div className="relative flex h-2 w-2">
          <span className="animate-pulse relative inline-flex rounded-full h-2 w-2 bg-amber-400"></span>
        </div>
        <span className="text-[10px] font-bold tracking-wider text-amber-400">
          {status === "reconnecting" ? "RECONNECTING" : "CONNECTING"}
        </span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 bg-slate-800/50 px-3 py-1.5 rounded-full border border-slate-700/50">
      <div className="relative flex h-2 w-2">
        <span className="relative inline-flex rounded-full h-2 w-2 bg-slate-500"></span>
      </div>
      <span className="text-[10px] font-bold tracking-wider text-slate-400">OFFLINE</span>
    </div>
  );
};

// Inner component that uses the LiveStream context
function WorkflowContent() {
  const params = useParams();
  const router = useRouter();
  const missionId = params.id as string;

  // Resizable layout state
  const [layout, setLayout] = useState({
    pipelineHeight: 192,
    sidebarWidth: 384,
    tracePanelHeight: 300,
  });
  const [dragging, setDragging] = useState<"pipeline" | "sidebar" | "trace" | null>(null);
  const dragStartRef = useRef({ x: 0, y: 0, value: 0 });

  // Live stream connection
  const { connect, disconnect, status, isLive, isHistorical, loadHistoricalData, queueLength, processedCount, eventsPerSecond } = useLiveStream();

  // Mission state
  const currentMission = useMissionStore((state) => state.currentMission);
  const fetchMission = useMissionStore((state) => state.fetchMission);

  // Graph state (for AssetMap)
  const fetchGraph = useGraphStore((state) => state.fetchGraph);

  // Workflow state
  const agentRuns = useWorkflowStore((state) => state.agentRuns);
  const toolCalls = useWorkflowStore((state) => state.toolCalls);
  const reset = useWorkflowStore((state) => state.reset);

  // Track if data has been loaded to prevent duplicate calls
  const dataLoadedRef = useRef<string | null>(null);
  const previousMissionIdRef = useRef<string | null>(null);

  // Handle mouse move for resizing
  useEffect(() => {
    if (!dragging) return;

    // Disable text selection during drag
    document.body.style.userSelect = "none";
    document.body.style.cursor = dragging === "sidebar" ? "ew-resize" : "ns-resize";

    const handleMouseMove = (e: globalThis.MouseEvent) => {
      e.preventDefault();
      if (dragging === "pipeline") {
        const delta = e.clientY - dragStartRef.current.y;
        setLayout((prev) => ({
          ...prev,
          pipelineHeight: Math.max(120, Math.min(400, dragStartRef.current.value + delta)),
        }));
      } else if (dragging === "sidebar") {
        const delta = dragStartRef.current.x - e.clientX;
        setLayout((prev) => ({
          ...prev,
          sidebarWidth: Math.max(280, Math.min(600, dragStartRef.current.value + delta)),
        }));
      } else if (dragging === "trace") {
        const delta = dragStartRef.current.y - e.clientY;
        setLayout((prev) => ({
          ...prev,
          tracePanelHeight: Math.max(150, Math.min(500, dragStartRef.current.value + delta)),
        }));
      }
    };

    const handleMouseUp = () => {
      setDragging(null);
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
    };

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
    };
  }, [dragging]);

  const startDrag = (type: "pipeline" | "sidebar" | "trace", e: ReactMouseEvent) => {
    e.preventDefault();
    dragStartRef.current = {
      x: e.clientX,
      y: e.clientY,
      value: type === "pipeline" ? layout.pipelineHeight : type === "sidebar" ? layout.sidebarWidth : layout.tracePanelHeight,
    };
    setDragging(type);
  };

  // Reset state when mission ID changes
  useEffect(() => {
    if (missionId && missionId !== previousMissionIdRef.current) {
      console.log("[Workflow] Mission changed from", previousMissionIdRef.current, "to", missionId);
      previousMissionIdRef.current = missionId;
      dataLoadedRef.current = null;
      reset();
      disconnect();
    }
  }, [missionId, reset, disconnect]);

  // Fetch mission details first, then decide whether to connect live or load historical
  useEffect(() => {
    if (missionId && (!currentMission || currentMission.id !== missionId)) {
      console.log("[Workflow] Fetching mission:", missionId, "current:", currentMission?.id);
      fetchMission(missionId);
    }
  }, [missionId, currentMission, fetchMission]);

  // Fetch graph data for AssetMap
  useEffect(() => {
    if (missionId) {
      console.log("[Workflow] Fetching graph for AssetMap:", missionId);
      fetchGraph(missionId);
    }
  }, [missionId, fetchGraph]);

  // Connect to live stream or load historical data based on mission status
  useEffect(() => {
    if (!missionId) return;

    if (currentMission && currentMission.id === missionId) {
      const missionStatus = currentMission.status;

      if (missionStatus === "running" || missionStatus === "pending") {
        console.log("[Workflow] Mission is active, connecting to live stream");
        dataLoadedRef.current = null;
        connect(missionId);
      } else {
        if (dataLoadedRef.current !== missionId) {
          console.log("[Workflow] Mission is finished, loading historical data");
          dataLoadedRef.current = missionId;
          loadHistoricalData(missionId);
        }
      }
    }
  }, [missionId, currentMission, connect, loadHistoricalData]);

  const handleBack = useCallback(() => {
    router.back();
  }, [router]);

  const handleReconnect = useCallback(() => {
    if (missionId) {
      disconnect();
      setTimeout(() => connect(missionId), 100);
    }
  }, [missionId, connect, disconnect]);

  // Total counts
  const agentCount = agentRuns.size;
  const toolCount = toolCalls.size;
  const hasData = agentCount > 0 || toolCount > 0;

  return (
    <div className="flex h-screen bg-slate-950">
      {/* Sidebar - w-16 fixed */}
      <Sidebar />

      {/* Main Content Area with radial gradient */}
      <main className="flex-1 flex flex-col min-w-0 relative bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-900 via-slate-950 to-slate-950">
        {/* Header - h-14 */}
        <header className="h-14 shrink-0 border-b border-slate-800/50 px-6 flex items-center justify-between backdrop-blur-sm">
          {/* Left: Back & Title */}
          <div className="flex items-center gap-4">
            <button
              onClick={handleBack}
              className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors"
            >
              <ArrowLeft size={18} />
            </button>

            <div className="h-5 w-px bg-slate-700/50" />

            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-cyan-500/10 border border-cyan-500/20">
                <Shield size={18} className="text-cyan-400" />
              </div>
              <div className="flex flex-col">
                <span className="text-sm font-semibold text-white">Workflow Monitor</span>
                {currentMission && (
                  <span className="text-[10px] text-slate-500 font-mono">
                    {currentMission.targetDomain}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Center: Mission Status */}
          <div className="flex items-center gap-4">
            {currentMission && (
              <>
                <StatusBadge status={currentMission.status} />
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <Clock size={12} />
                  <span className="font-mono">
                    {new Date(currentMission.createdAt).toLocaleTimeString()}
                  </span>
                </div>
              </>
            )}
          </div>

          {/* Right: Stats & Connection */}
          <div className="flex items-center gap-4">
            {/* Stats */}
            <div className="flex items-center gap-3 text-xs">
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-800/50 border border-slate-700/50">
                <Cpu size={12} className="text-cyan-400" />
                <span className="text-slate-400">Agents</span>
                <span className="text-white font-mono font-medium">{agentCount}</span>
              </div>
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-800/50 border border-slate-700/50">
                <Activity size={12} className="text-amber-400" />
                <span className="text-slate-400">Tools</span>
                <span className="text-white font-mono font-medium">{toolCount}</span>
              </div>
            </div>

            <div className="h-5 w-px bg-slate-700/50" />

            {/* Connection Status */}
            <ConnectionIndicator status={status} isLive={isLive} isHistorical={isHistorical} />

            {status === "error" && (
              <button
                onClick={handleReconnect}
                className="p-1.5 rounded-md bg-slate-800/50 border border-slate-700/50 text-slate-400 hover:text-white hover:border-slate-600 transition-colors"
                title="Reconnect"
              >
                <RefreshCw size={14} />
              </button>
            )}
          </div>
        </header>

        {/* Stream Status Bar */}
        <div className="h-9 shrink-0 border-b border-slate-800/50 bg-slate-900/30 px-6 flex items-center justify-between">
          <div className="flex items-center gap-4 text-xs">
            <div className="flex items-center gap-1.5" title="Events in queue">
              <Activity size={11} className="text-cyan-400" />
              <span className="text-slate-500">Queue:</span>
              <span className="text-slate-300 font-mono">{queueLength}</span>
            </div>
            <div className="flex items-center gap-1.5" title="Events per second">
              <Zap size={11} className="text-amber-400" />
              <span className="text-slate-500">Rate:</span>
              <span className="text-slate-300 font-mono">{eventsPerSecond}/s</span>
            </div>
            <div className="flex items-center gap-1.5" title="Total processed">
              <RefreshCw size={11} className="text-purple-400" />
              <span className="text-slate-500">Processed:</span>
              <span className="text-slate-300 font-mono">{processedCount.toLocaleString()}</span>
            </div>
          </div>
          <WorkflowControls missionId={missionId} compact />
        </div>

        {/* Agent Pipeline Section - Resizable */}
        <div
          className="shrink-0 border-b border-slate-800/50 relative group"
          style={{ height: layout.pipelineHeight }}
        >
          <div className="absolute inset-0 overflow-hidden">
            <AgentPipeline maxAgents={10} isHistorical={isHistorical} className="h-full px-6 py-4" />
          </div>
          {/* Resize Handle */}
          <div
            className="absolute bottom-0 left-0 right-0 h-1.5 cursor-row-resize bg-transparent hover:bg-cyan-500/30 transition-colors z-20 flex items-center justify-center"
            onMouseDown={(e) => startDrag("pipeline", e)}
          >
            <div className="w-16 h-1 rounded-full bg-slate-700 group-hover:bg-cyan-400 transition-colors" />
          </div>
        </div>

        {/* Main Content: Graph + Sidebar */}
        <div className="flex-1 flex overflow-hidden min-h-0">
          {/* Graph Area */}
          <div className="flex-1 relative min-w-0">
            {/* SVG Grid Background */}
            <svg className="absolute inset-0 w-full h-full pointer-events-none opacity-30">
              <defs>
                <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                  <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgb(51, 65, 85)" strokeWidth="0.5" />
                </pattern>
              </defs>
              <rect width="100%" height="100%" fill="url(#grid)" />
            </svg>

            {/* Workflow Graph */}
            <WorkflowHierarchy missionId={missionId} className="absolute inset-0" />

            {/* Empty State Overlay */}
            <AnimatePresence>
              {!hasData && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="absolute inset-0 flex items-center justify-center pointer-events-none bg-slate-950/60 backdrop-blur-sm"
                >
                  <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="text-center p-8 rounded-xl bg-slate-900/80 border border-slate-800/50 shadow-2xl"
                  >
                    {isHistorical ? (
                      <>
                        <div className="p-4 rounded-xl bg-cyan-500/10 border border-cyan-500/20 w-fit mx-auto mb-4">
                          <Database size={32} className="text-cyan-400" />
                        </div>
                        <p className="text-slate-200 text-sm font-medium">No workflow data recorded</p>
                        <p className="text-slate-500 text-xs mt-2">
                          This mission has no agent execution history
                        </p>
                      </>
                    ) : isLive ? (
                      <>
                        <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 w-fit mx-auto mb-4">
                          <motion.div
                            animate={{ rotate: 360 }}
                            transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                          >
                            <Activity size={32} className="text-emerald-400" />
                          </motion.div>
                        </div>
                        <p className="text-slate-200 text-sm font-medium">Connected to mission stream</p>
                        <p className="text-slate-500 text-xs mt-2">Waiting for workflow events...</p>
                      </>
                    ) : (
                      <>
                        <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/50 w-fit mx-auto mb-4">
                          <WifiOff size={32} className="text-slate-500" />
                        </div>
                        <p className="text-slate-300 text-sm font-medium">
                          {status === "connecting" ? "Loading workflow data..." : "Not connected"}
                        </p>
                        <p className="text-slate-500 text-xs mt-2">
                          {status === "connecting"
                            ? "Please wait..."
                            : status === "reconnecting"
                            ? "Reconnecting..."
                            : "Start a mission to see workflow events"}
                        </p>
                        {status === "error" && (
                          <button
                            onClick={handleReconnect}
                            className="mt-4 px-4 py-2 rounded-lg bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/30 text-xs font-medium transition-colors pointer-events-auto border border-cyan-500/30"
                          >
                            Try Reconnect
                          </button>
                        )}
                      </>
                    )}
                  </motion.div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Right Sidebar - Resizable */}
          <div
            className="shrink-0 flex flex-col border-l border-slate-800/50 bg-slate-900/30 relative group overflow-hidden"
            style={{ width: layout.sidebarWidth }}
          >
            {/* Resize Handle - positioned outside the overflow container */}
            <div
              className="absolute left-0 top-0 bottom-0 w-3 cursor-ew-resize z-30 flex items-center justify-center hover:bg-cyan-500/20 transition-colors"
              onMouseDown={(e) => startDrag("sidebar", e)}
            >
              <div className="h-16 w-1 rounded-full bg-slate-600 group-hover:bg-cyan-400 transition-colors" />
            </div>

            {/* Asset Map */}
            <div className="flex-1 overflow-hidden border-b border-slate-800/50 min-h-0">
              <AssetMap missionId={missionId} className="h-full w-full" />
            </div>

            {/* Trace Panel - Resizable */}
            <div className="shrink-0 relative group/trace overflow-hidden" style={{ height: layout.tracePanelHeight }}>
              {/* Resize Handle */}
              <div
                className="absolute top-0 left-0 right-0 h-3 cursor-ns-resize z-30 flex items-center justify-center hover:bg-cyan-500/20 transition-colors"
                onMouseDown={(e) => startDrag("trace", e)}
              >
                <div className="w-16 h-1 rounded-full bg-slate-600 group-hover/trace:bg-cyan-400 transition-colors" />
              </div>
              <TracePanel className="h-full w-full" maxHeight="100%" />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

// Main page component with provider
export default function WorkflowPage() {
  return (
    <LiveStreamProvider>
      <WorkflowContent />
    </LiveStreamProvider>
  );
}
