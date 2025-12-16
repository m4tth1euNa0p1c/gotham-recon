"use client";

import { useState, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  RefreshCw,
  Save,
  Layers,
  Eye,
  EyeOff,
  Wifi,
  WifiOff,
  Cpu,
  Wrench,
  Database,
  FastForward,
  Rewind,
} from "lucide-react";
import { useWorkflowStore, ReplayMode } from "@/stores/workflowStore";
import { LayoutService } from "@/services/LayoutService";

interface WorkflowControlsProps {
  missionId: string;
  className?: string;
}

export default function WorkflowControls({ missionId, className = "" }: WorkflowControlsProps) {
  const [isSaving, setIsSaving] = useState(false);

  // Store state
  const connectionStatus = useWorkflowStore((state) => state.connectionStatus);
  const replayMode = useWorkflowStore((state) => state.replayMode);
  const replaySpeed = useWorkflowStore((state) => state.replaySpeed);
  const replayIndex = useWorkflowStore((state) => state.replayIndex);
  const replayEvents = useWorkflowStore((state) => state.replayEvents || []);
  const showAgents = useWorkflowStore((state) => state.showAgents);
  const showTools = useWorkflowStore((state) => state.showTools);
  const showAssets = useWorkflowStore((state) => state.showAssets);
  const layout = useWorkflowStore((state) => state.layout);

  // Actions
  const setReplayMode = useWorkflowStore((state) => state.setReplayMode);
  const setReplaySpeed = useWorkflowStore((state) => state.setReplaySpeed);
  const stepForward = useWorkflowStore((state) => state.stepForward);
  const stepBackward = useWorkflowStore((state) => state.stepBackward);
  const toggleAgents = useWorkflowStore((state) => state.toggleAgents);
  const toggleTools = useWorkflowStore((state) => state.toggleTools);
  const toggleAssets = useWorkflowStore((state) => state.toggleAssets);
  const reset = useWorkflowStore((state) => state.reset);

  // Toggle between live and paused
  const toggleLivePause = useCallback(() => {
    if (replayMode === "live") {
      setReplayMode("paused");
    } else {
      setReplayMode("live");
    }
  }, [replayMode, setReplayMode]);

  // Cycle replay speed
  const cycleSpeed = useCallback(() => {
    const speeds = [1, 2, 4];
    const currentIndex = speeds.indexOf(replaySpeed);
    const nextSpeed = speeds[(currentIndex + 1) % speeds.length];
    setReplaySpeed(nextSpeed);
  }, [replaySpeed, setReplaySpeed]);

  // Save layout
  const handleSaveLayout = useCallback(async () => {
    if (!layout) return;
    setIsSaving(true);
    try {
      await LayoutService.saveLayout(missionId, layout);
    } finally {
      setIsSaving(false);
    }
  }, [missionId, layout]);

  // Connection status indicator
  const ConnectionIndicator = () => {
    const isConnected = connectionStatus === "connected";
    return (
      <div className="flex items-center gap-1.5">
        {isConnected ? (
          <>
            <Wifi size={14} className="text-green-400" />
            <span className="text-xs text-green-400 font-medium">LIVE</span>
          </>
        ) : (
          <>
            <WifiOff size={14} className="text-gray-500" />
            <span className="text-xs text-gray-500">OFFLINE</span>
          </>
        )}
      </div>
    );
  };

  return (
    <div
      className={`flex items-center justify-between px-4 py-2 bg-[#0d0d12] border-b border-[#1a1a25] ${className}`}
    >
      {/* Left: Connection Status & Mode Controls */}
      <div className="flex items-center gap-4">
        <ConnectionIndicator />

        <div className="h-4 w-px bg-[#2a2a3a]" />

        {/* Live/Pause Toggle */}
        <button
          onClick={toggleLivePause}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors ${replayMode === "live"
              ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
              : "bg-gray-500/20 text-gray-400 border border-gray-500/30"
            }`}
        >
          {replayMode === "live" ? (
            <>
              <Pause size={12} />
              PAUSE
            </>
          ) : (
            <>
              <Play size={12} />
              LIVE
            </>
          )}
        </button>

        {/* Step Controls (only in paused/step mode) */}
        {replayMode !== "live" && (
          <div className="flex items-center gap-1">
            <button
              onClick={stepBackward}
              disabled={replayIndex === 0}
              className="p-1.5 rounded hover:bg-[#1a1a25] text-gray-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              title="Step Backward"
            >
              <SkipBack size={14} />
            </button>
            <button
              onClick={stepForward}
              disabled={replayIndex >= replayEvents.length - 1}
              className="p-1.5 rounded hover:bg-[#1a1a25] text-gray-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              title="Step Forward"
            >
              <SkipForward size={14} />
            </button>
          </div>
        )}

        {/* Speed Control */}
        <button
          onClick={cycleSpeed}
          className="flex items-center gap-1.5 px-2 py-1.5 rounded bg-[#1a1a25] text-gray-400 hover:text-white text-xs font-mono transition-colors"
          title="Playback Speed"
        >
          <FastForward size={12} />
          {replaySpeed}x
        </button>
      </div>

      {/* Center: Layer Toggles */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-500 mr-2">Layers:</span>

        <button
          onClick={toggleAgents}
          className={`flex items-center gap-1.5 px-2 py-1.5 rounded text-xs transition-colors ${showAgents
              ? "bg-cyan-500/20 text-cyan-400"
              : "bg-[#1a1a25] text-gray-500"
            }`}
          title="Toggle Agents"
        >
          <Cpu size={12} />
          Agents
          {showAgents ? <Eye size={10} /> : <EyeOff size={10} />}
        </button>

        <button
          onClick={toggleTools}
          className={`flex items-center gap-1.5 px-2 py-1.5 rounded text-xs transition-colors ${showTools
              ? "bg-amber-500/20 text-amber-400"
              : "bg-[#1a1a25] text-gray-500"
            }`}
          title="Toggle Tools"
        >
          <Wrench size={12} />
          Tools
          {showTools ? <Eye size={10} /> : <EyeOff size={10} />}
        </button>

        <button
          onClick={toggleAssets}
          className={`flex items-center gap-1.5 px-2 py-1.5 rounded text-xs transition-colors ${showAssets
              ? "bg-purple-500/20 text-purple-400"
              : "bg-[#1a1a25] text-gray-500"
            }`}
          title="Toggle Assets"
        >
          <Database size={12} />
          Assets
          {showAssets ? <Eye size={10} /> : <EyeOff size={10} />}
        </button>
      </div>

      {/* Right: Layout Controls */}
      <div className="flex items-center gap-2">
        <button
          onClick={handleSaveLayout}
          disabled={isSaving || !layout}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#1a1a25] text-gray-400 hover:text-white text-xs transition-colors disabled:opacity-50"
          title="Save Layout"
        >
          {isSaving ? (
            <motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity }}>
              <RefreshCw size={12} />
            </motion.div>
          ) : (
            <Save size={12} />
          )}
          Save
        </button>

        <button
          onClick={reset}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-red-500/10 text-red-400 hover:bg-red-500/20 text-xs transition-colors"
          title="Reset View"
        >
          <RefreshCw size={12} />
          Reset
        </button>
      </div>
    </div>
  );
}
