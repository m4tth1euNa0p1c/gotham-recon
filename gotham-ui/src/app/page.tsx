"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useCallback } from "react";
import { motion } from "framer-motion";
import { Activity, Globe, Loader2 } from "lucide-react";
import Sidebar from "@/components/dashboard/Sidebar";
import Header from "@/components/dashboard/Header";
import MissionPanel from "@/components/dashboard/MissionPanel";
import { useUIStore, useMissionStore, useGraphStore } from "@/stores";

// Dynamic imports to prevent SSR issues with canvas/WebGL libraries
const AgentGraph = dynamic(() => import("@/components/agents/AgentGraph"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center bg-[#0a0a0f]">
      <Loader2 className="w-8 h-8 text-cyan-500 animate-spin" />
    </div>
  ),
});

const AssetGraph = dynamic(() => import("@/components/assets/AssetGraph"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center bg-[#0a0a0f]">
      <Loader2 className="w-8 h-8 text-cyan-500 animate-spin" />
    </div>
  ),
});

export default function Dashboard() {
  // UI State
  const activeView = useUIStore((state) => state.activeTab);
  const setActiveView = useUIStore((state) => state.setActiveTab);

  // Mission State
  const currentMission = useMissionStore((state) => state.currentMission);
  const fetchMission = useMissionStore((state) => state.fetchMission);
  const subscribeToLogs = useMissionStore((state) => state.subscribeToLogs);
  const unsubscribeFromLogs = useMissionStore((state) => state.unsubscribeFromLogs);

  // Graph State
  const fetchGraph = useGraphStore((state) => state.fetchGraph);
  const subscribeGraph = useGraphStore((state) => state.subscribe);
  const unsubscribeGraph = useGraphStore((state) => state.unsubscribe);
  const resetGraph = useGraphStore((state) => state.reset);

  const missionId = currentMission?.id;
  const isActive = currentMission?.status === "running";

  // Track previous mission ID to detect changes
  const prevMissionIdRef = useRef<string | null>(null);

  /**
   * Centralized reactivity: when currentMission?.id changes,
   * auto fetchMission, subscribeToLogs, fetchGraph, subscribeGraph
   * and cleanup systematically to avoid double connections
   */
  useEffect(() => {
    // Skip if same mission or no mission
    if (missionId === prevMissionIdRef.current) return;

    // Cleanup previous subscriptions
    if (prevMissionIdRef.current) {
      console.log("[Dashboard] Cleaning up previous mission:", prevMissionIdRef.current);
      unsubscribeFromLogs();
      unsubscribeGraph();
    }

    // Update ref
    prevMissionIdRef.current = missionId || null;

    // Subscribe to new mission
    if (missionId) {
      console.log("[Dashboard] Setting up subscriptions for mission:", missionId);

      // Fetch initial data
      fetchMission(missionId);
      fetchGraph(missionId);

      // Subscribe to real-time updates
      subscribeToLogs(missionId);
      subscribeGraph(missionId);
    }

    // Cleanup on unmount
    return () => {
      if (missionId) {
        console.log("[Dashboard] Unmount cleanup for mission:", missionId);
        unsubscribeFromLogs();
        unsubscribeGraph();
      }
    };
  }, [missionId, fetchMission, fetchGraph, subscribeToLogs, subscribeGraph, unsubscribeFromLogs, unsubscribeGraph]);

  // Reset graph when no mission is selected
  useEffect(() => {
    if (!missionId) {
      resetGraph();
    }
  }, [missionId, resetGraph]);

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <Sidebar />

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <Header />

        {/* View Tabs */}
        <div className="border-b border-[#1a1a25] px-6 bg-[#0d0d12]">
          <div className="flex gap-4">
            <button
              onClick={() => setActiveView("agents")}
              className={`px-4 py-3 text-xs font-bold uppercase tracking-wider transition-colors relative ${
                activeView === "agents"
                  ? "text-[#00ffff]"
                  : "text-[#4a4a5a] hover:text-[#8a8a9a]"
              }`}
            >
              <span className="flex items-center gap-2">
                <Activity size={14} />
                Agent Workflow
              </span>
              {activeView === "agents" && (
                <motion.div
                  layoutId="activeTab"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#00ffff]"
                  style={{ boxShadow: "0 0 10px #00ffff" }}
                />
              )}
            </button>
            <button
              onClick={() => setActiveView("assets")}
              className={`px-4 py-3 text-xs font-bold uppercase tracking-wider transition-colors relative ${
                activeView === "assets"
                  ? "text-[#00ffff]"
                  : "text-[#4a4a5a] hover:text-[#8a8a9a]"
              }`}
            >
              <span className="flex items-center gap-2">
                <Globe size={14} />
                Asset Graph
              </span>
              {activeView === "assets" && (
                <motion.div
                  layoutId="activeTab"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#00ffff]"
                  style={{ boxShadow: "0 0 10px #00ffff" }}
                />
              )}
            </button>
          </div>
        </div>

        {/* Graph Container */}
        <div className="flex-1 relative bg-[#0a0a0f]">
          {activeView === "agents" ? (
            <AgentGraph missionId={missionId} />
          ) : (
            <AssetGraph missionId={missionId} />
          )}
        </div>

        {/* Mission Panel (Bottom) */}
        <MissionPanel />
      </div>
    </div>
  );
}
