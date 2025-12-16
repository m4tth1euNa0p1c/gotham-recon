"use client";

/**
 * Workflow Visualization Page
 * Real-time sequential workflow visualization that reacts to live events.
 * NO MOCK DATA - all data populated via WebSocket/SSE events from Python backend.
 *
 * Route: /mission/[mission-id]/workflow
 */

import { useParams, useRouter } from "next/navigation";
import { useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowLeft,
  Activity,
  Shield,
  Cpu,
  Database,
  Wifi,
  WifiOff,
  RefreshCw,
  Clock,
} from "lucide-react";
import {
  WorkflowHierarchy,
  TracePanel,
  WorkflowControls,
  AgentPipeline,
  AssetMap,
  LiveStreamStatus,
} from "@/components/workflow";
import { useWorkflowStore } from "@/stores/workflowStore";
import { useMissionStore } from "@/stores";
import { LiveStreamProvider, useLiveStream } from "@/providers/LiveStreamProvider";
import Sidebar from "@/components/dashboard/Sidebar";

// Inner component that uses the LiveStream context
function WorkflowContent() {
  const params = useParams();
  const router = useRouter();
  const missionId = params.id as string;

  // Live stream connection
  const { connect, disconnect, status, isLive, isHistorical, loadHistoricalData } = useLiveStream();

  // Mission state
  const currentMission = useMissionStore((state) => state.currentMission);
  const fetchMission = useMissionStore((state) => state.fetchMission);

  // Workflow state
  const connectionStatus = useWorkflowStore((state) => state.connectionStatus);
  const agentRuns = useWorkflowStore((state) => state.agentRuns);
  const toolCalls = useWorkflowStore((state) => state.toolCalls);
  const reset = useWorkflowStore((state) => state.reset);

  // Track if data has been loaded to prevent duplicate calls
  const dataLoadedRef = useRef<string | null>(null);

  // Fetch mission details first, then decide whether to connect live or load historical
  useEffect(() => {
    if (missionId && !currentMission) {
      fetchMission(missionId);
    }
  }, [missionId, currentMission, fetchMission]);

  // Connect to live stream or load historical data based on mission status
  useEffect(() => {
    if (!missionId) return;

    // Prevent duplicate loads for the same mission
    if (dataLoadedRef.current === missionId && isHistorical) {
      return;
    }

    // Wait for mission data to determine mode
    if (currentMission) {
      const missionStatus = currentMission.status;

      // If mission is running, connect to live stream
      if (missionStatus === "running" || missionStatus === "pending") {
        console.log("[Workflow] Mission is active, connecting to live stream");
        dataLoadedRef.current = null; // Reset for live mode
        connect(missionId);
      } else {
        // Mission is completed, failed, or paused - load historical data
        if (dataLoadedRef.current !== missionId) {
          console.log("[Workflow] Mission is finished, loading historical data");
          dataLoadedRef.current = missionId;
          loadHistoricalData(missionId);
        }
      }
    } else {
      // No mission data yet, wait for mission to load
      // Don't eagerly load historical - wait for mission status
    }

    return () => {
      disconnect();
    };
  }, [missionId, currentMission?.status, connect, disconnect, loadHistoricalData, isHistorical]);

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
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
      {/* Header */}
      <header className="h-14 border-b border-slate-800 px-4 flex items-center justify-between bg-slate-900/90 backdrop-blur-md">
        {/* Left: Back & Logo */}
        <div className="flex items-center gap-4">
          <button
            onClick={handleBack}
            className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors"
          >
            <ArrowLeft size={18} />
            <span className="text-sm">Back</span>
          </button>

          <div className="h-6 w-px bg-slate-700" />

          <div className="flex items-center gap-2">
            <Shield size={20} className="text-cyan-400" />
            <span className="text-sm font-medium text-white">
              Live Workflow
            </span>
          </div>
        </div>

        {/* Center: Mission Info */}
        <div className="flex items-center gap-3">
          {currentMission && (
            <>
              <span className="text-sm text-cyan-400 font-mono">
                {currentMission.targetDomain}
              </span>
              <span
                className={`px-2 py-0.5 text-xs rounded ${
                  currentMission.status === "running"
                    ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                    : currentMission.status === "completed"
                    ? "bg-blue-500/20 text-blue-400 border border-blue-500/30"
                    : "bg-slate-500/20 text-slate-400 border border-slate-500/30"
                }`}
              >
                {currentMission.status.toUpperCase()}
              </span>
            </>
          )}
        </div>

        {/* Right: Stats & Connection */}
        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-1.5">
            <Cpu size={12} className="text-cyan-400" />
            <span className="text-slate-400">Agents:</span>
            <span className="text-white font-mono">{agentCount}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Activity size={12} className="text-amber-400" />
            <span className="text-slate-400">Tools:</span>
            <span className="text-white font-mono">{toolCount}</span>
          </div>

          {/* Live/Historical indicator */}
          <div className="flex items-center gap-1.5 ml-2">
            <span
              className={`w-2 h-2 rounded-full ${
                isHistorical
                  ? "bg-blue-400"
                  : isLive
                  ? "bg-emerald-400 animate-pulse"
                  : status === "connecting"
                  ? "bg-amber-400"
                  : "bg-slate-500"
              }`}
            />
            <span
              className={`font-medium ${
                isHistorical
                  ? "text-blue-400"
                  : isLive
                  ? "text-emerald-400"
                  : status === "connecting"
                  ? "text-amber-400"
                  : "text-slate-500"
              }`}
            >
              {isHistorical ? "HISTORY" : isLive ? "LIVE" : status.toUpperCase()}
            </span>
          </div>

          {/* Reconnect button */}
          {status === "error" && (
            <button
              onClick={handleReconnect}
              className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
              title="Reconnect"
            >
              <RefreshCw size={14} />
            </button>
          )}
        </div>
      </header>

      {/* Live Stream Status Bar */}
      <div className="border-b border-slate-800 bg-slate-900/50 px-4 py-2">
        <LiveStreamStatus />
      </div>

      {/* Controls Bar */}
      <WorkflowControls missionId={missionId} />

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Section: Agent Pipeline */}
        <div className="border-b border-slate-800 bg-slate-900/30 px-4 py-4">
          <AgentPipeline maxAgents={8} isHistorical={isHistorical} />
        </div>

        {/* Bottom Section: Graph + Asset Map + Trace Panel */}
        <div className="flex-1 flex overflow-hidden">
          {/* Main Graph Area */}
          <div className="flex-1 relative">
            <WorkflowHierarchy
              missionId={missionId}
              className="absolute inset-0"
            />

            {/* Empty State Overlay */}
            <AnimatePresence>
              {!hasData && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="absolute inset-0 flex items-center justify-center pointer-events-none bg-slate-950/50"
                >
                  <motion.div
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="text-center"
                  >
                    {isHistorical ? (
                      <>
                        <Database size={48} className="text-blue-500/50 mx-auto mb-4" />
                        <p className="text-slate-400 text-sm">
                          No workflow data recorded
                        </p>
                        <p className="text-slate-600 text-xs mt-1">
                          This mission has no agent execution history
                        </p>
                      </>
                    ) : isLive ? (
                      <>
                        <motion.div
                          animate={{ rotate: 360 }}
                          transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                          className="mx-auto mb-4"
                        >
                          <Activity size={48} className="text-cyan-500/50" />
                        </motion.div>
                        <p className="text-slate-400 text-sm">
                          Connected to mission stream
                        </p>
                        <p className="text-slate-600 text-xs mt-1">
                          Waiting for workflow events...
                        </p>
                      </>
                    ) : (
                      <>
                        <WifiOff size={48} className="text-slate-600 mx-auto mb-4" />
                        <p className="text-slate-500 text-sm">
                          {status === "connecting"
                            ? "Loading workflow data..."
                            : "Not connected"}
                        </p>
                        <p className="text-slate-600 text-xs mt-1">
                          {status === "connecting"
                            ? "Please wait..."
                            : status === "reconnecting"
                            ? "Reconnecting..."
                            : "Start a mission to see workflow events"}
                        </p>
                        {status === "error" && (
                          <button
                            onClick={handleReconnect}
                            className="mt-3 px-4 py-2 rounded bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/30 text-sm transition-colors pointer-events-auto"
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

          {/* Right Sidebar: Asset Map + Trace Panel */}
          <div className="w-96 border-l border-slate-800 flex flex-col">
            {/* Asset Map (collapsible) */}
            <div className="h-1/2 border-b border-slate-800 overflow-hidden">
              <AssetMap
                missionId={missionId}
                className="h-full"
              />
            </div>

            {/* Trace Panel */}
            <div className="flex-1 overflow-hidden">
              <TracePanel className="h-full" maxHeight="100%" />
            </div>
          </div>
        </div>
      </div>
      </div>
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
