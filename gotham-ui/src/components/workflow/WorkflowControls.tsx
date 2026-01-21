"use client";

/**
 * WorkflowControls
 * Controls bar for workflow visualization with play/pause, layer toggles, and layout actions.
 *
 * Design: Compact mode for status bar, full mode for dedicated controls area
 */

import { useState, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  RefreshCw,
  Save,
  Eye,
  EyeOff,
  Cpu,
  Wrench,
  Database,
  FastForward,
  RotateCcw,
} from "lucide-react";
import { useWorkflowStore } from "@/stores/workflowStore";
import { LayoutService } from "@/services/LayoutService";

interface WorkflowControlsProps {
  missionId: string;
  className?: string;
  compact?: boolean;
}

export default function WorkflowControls({ missionId, className = "", compact = false }: WorkflowControlsProps) {
  const [isSaving, setIsSaving] = useState(false);

  // Store state
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

  // Compact mode for status bar
  if (compact) {
    return (
      <div className={`flex items-center gap-3 ${className}`}>
        {/* Play/Pause Toggle */}
        <button
          onClick={toggleLivePause}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-[10px] font-bold tracking-wider transition-colors border ${
            replayMode === "live"
              ? "bg-cyan-500/20 text-cyan-400 border-cyan-500/30 hover:bg-cyan-500/30"
              : "bg-slate-800/50 text-slate-400 border-slate-700/50 hover:bg-slate-700/50 hover:text-white"
          }`}
        >
          {replayMode === "live" ? <Pause size={10} /> : <Play size={10} />}
          <span>{replayMode === "live" ? "PAUSE" : "PLAY"}</span>
        </button>

        {/* Step Controls (only in paused mode) */}
        {replayMode !== "live" && (
          <div className="flex items-center gap-1">
            <button
              onClick={stepBackward}
              disabled={replayIndex === 0}
              className="p-1 rounded bg-slate-800/50 border border-slate-700/50 text-slate-400 hover:text-white hover:bg-slate-700/50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              title="Step Backward"
            >
              <SkipBack size={10} />
            </button>
            <button
              onClick={stepForward}
              disabled={replayIndex >= replayEvents.length - 1}
              className="p-1 rounded bg-slate-800/50 border border-slate-700/50 text-slate-400 hover:text-white hover:bg-slate-700/50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              title="Step Forward"
            >
              <SkipForward size={10} />
            </button>
          </div>
        )}

        {/* Speed Control */}
        <button
          onClick={cycleSpeed}
          className="flex items-center gap-1 px-2 py-1 rounded bg-slate-800/50 border border-slate-700/50 text-slate-400 hover:text-white hover:bg-slate-700/50 text-[10px] font-mono transition-colors"
          title="Playback Speed"
        >
          <FastForward size={10} />
          <span>{replaySpeed}x</span>
        </button>

        <div className="h-4 w-px bg-slate-700/50" />

        {/* Layer Toggles */}
        <div className="flex items-center gap-1">
          <button
            onClick={toggleAgents}
            className={`p-1.5 rounded transition-colors border ${
              showAgents
                ? "bg-cyan-500/20 text-cyan-400 border-cyan-500/30"
                : "bg-slate-800/50 text-slate-500 border-slate-700/50 hover:text-slate-300"
            }`}
            title="Toggle Agents"
          >
            <Cpu size={11} />
          </button>
          <button
            onClick={toggleTools}
            className={`p-1.5 rounded transition-colors border ${
              showTools
                ? "bg-amber-500/20 text-amber-400 border-amber-500/30"
                : "bg-slate-800/50 text-slate-500 border-slate-700/50 hover:text-slate-300"
            }`}
            title="Toggle Tools"
          >
            <Wrench size={11} />
          </button>
          <button
            onClick={toggleAssets}
            className={`p-1.5 rounded transition-colors border ${
              showAssets
                ? "bg-purple-500/20 text-purple-400 border-purple-500/30"
                : "bg-slate-800/50 text-slate-500 border-slate-700/50 hover:text-slate-300"
            }`}
            title="Toggle Assets"
          >
            <Database size={11} />
          </button>
        </div>

        <div className="h-4 w-px bg-slate-700/50" />

        {/* Reset */}
        <button
          onClick={reset}
          className="p-1.5 rounded bg-slate-800/50 border border-slate-700/50 text-slate-400 hover:text-white hover:bg-slate-700/50 transition-colors"
          title="Reset View"
        >
          <RotateCcw size={11} />
        </button>
      </div>
    );
  }

  // Full mode
  return (
    <div className={`flex items-center justify-between px-6 bg-slate-900/30 border-b border-slate-800/50 ${className}`}>
      {/* Left: Mode Controls */}
      <div className="flex items-center gap-3">
        {/* Play/Pause Toggle */}
        <button
          onClick={toggleLivePause}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors border ${
            replayMode === "live"
              ? "bg-cyan-500/20 text-cyan-400 border-cyan-500/30 hover:bg-cyan-500/30"
              : "bg-slate-800/50 text-slate-400 border-slate-700/50 hover:bg-slate-700/50 hover:text-white"
          }`}
        >
          {replayMode === "live" ? (
            <>
              <Pause size={12} />
              <span>PAUSE</span>
            </>
          ) : (
            <>
              <Play size={12} />
              <span>RESUME</span>
            </>
          )}
        </button>

        {/* Step Controls (only in paused mode) */}
        {replayMode !== "live" && (
          <div className="flex items-center gap-1">
            <button
              onClick={stepBackward}
              disabled={replayIndex === 0}
              className="p-1.5 rounded bg-slate-800/50 border border-slate-700/50 text-slate-400 hover:text-white hover:bg-slate-700/50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              title="Step Backward"
            >
              <SkipBack size={14} />
            </button>
            <button
              onClick={stepForward}
              disabled={replayIndex >= replayEvents.length - 1}
              className="p-1.5 rounded bg-slate-800/50 border border-slate-700/50 text-slate-400 hover:text-white hover:bg-slate-700/50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              title="Step Forward"
            >
              <SkipForward size={14} />
            </button>
          </div>
        )}

        {/* Speed Control */}
        <button
          onClick={cycleSpeed}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded bg-slate-800/50 border border-slate-700/50 text-slate-400 hover:text-white hover:bg-slate-700/50 text-xs font-mono transition-colors"
          title="Playback Speed"
        >
          <FastForward size={12} />
          <span>{replaySpeed}x</span>
        </button>
      </div>

      {/* Center: Layer Toggles */}
      <div className="flex items-center gap-2">
        <span className="text-[10px] text-slate-500 font-bold tracking-wider mr-1">LAYERS</span>

        <button
          onClick={toggleAgents}
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-medium transition-colors border ${
            showAgents
              ? "bg-cyan-500/20 text-cyan-400 border-cyan-500/30"
              : "bg-slate-800/50 text-slate-500 border-slate-700/50 hover:text-slate-300"
          }`}
          title="Toggle Agents Layer"
        >
          <Cpu size={12} />
          <span>Agents</span>
          {showAgents ? <Eye size={10} /> : <EyeOff size={10} />}
        </button>

        <button
          onClick={toggleTools}
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-medium transition-colors border ${
            showTools
              ? "bg-amber-500/20 text-amber-400 border-amber-500/30"
              : "bg-slate-800/50 text-slate-500 border-slate-700/50 hover:text-slate-300"
          }`}
          title="Toggle Tools Layer"
        >
          <Wrench size={12} />
          <span>Tools</span>
          {showTools ? <Eye size={10} /> : <EyeOff size={10} />}
        </button>

        <button
          onClick={toggleAssets}
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-medium transition-colors border ${
            showAssets
              ? "bg-purple-500/20 text-purple-400 border-purple-500/30"
              : "bg-slate-800/50 text-slate-500 border-slate-700/50 hover:text-slate-300"
          }`}
          title="Toggle Assets Layer"
        >
          <Database size={12} />
          <span>Assets</span>
          {showAssets ? <Eye size={10} /> : <EyeOff size={10} />}
        </button>
      </div>

      {/* Right: Layout Actions */}
      <div className="flex items-center gap-2">
        <button
          onClick={handleSaveLayout}
          disabled={isSaving || !layout}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-slate-800/50 border border-slate-700/50 text-slate-400 hover:text-white hover:bg-slate-700/50 text-xs font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          title="Save Layout"
        >
          {isSaving ? (
            <motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity, ease: "linear" }}>
              <RefreshCw size={12} />
            </motion.div>
          ) : (
            <Save size={12} />
          )}
          <span>Save</span>
        </button>

        <button
          onClick={reset}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-red-500/10 text-red-400 hover:bg-red-500/20 text-xs font-medium transition-colors border border-red-500/20"
          title="Reset View"
        >
          <RotateCcw size={12} />
          <span>Reset</span>
        </button>
      </div>
    </div>
  );
}
