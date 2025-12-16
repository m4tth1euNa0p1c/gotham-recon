"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { Loader2, Network, Filter, ZoomIn, ZoomOut, Maximize2 } from "lucide-react";
import Sidebar from "@/components/dashboard/Sidebar";
import { useMissionStore, useGraphStore } from "@/stores";

// Dynamic import for AssetGraph to prevent SSR issues
const AssetGraph = dynamic(() => import("@/components/assets/AssetGraph"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center bg-slate-950">
      <Loader2 className="w-8 h-8 text-cyan-500 animate-spin" />
    </div>
  ),
});

export default function MissionGraphPage() {
  const params = useParams();
  const missionId = params.id as string;
  const [isFullscreen, setIsFullscreen] = useState(false);

  const currentMission = useMissionStore((state) => state.currentMission);
  const fetchMission = useMissionStore((state) => state.fetchMission);
  const fetchGraph = useGraphStore((state) => state.fetchGraph);
  const subscribeGraph = useGraphStore((state) => state.subscribe);
  const unsubscribeGraph = useGraphStore((state) => state.unsubscribe);
  const nodeCount = useGraphStore((state) => state.nodes.size);
  const edgeCount = useGraphStore((state) => state.edges.length);

  useEffect(() => {
    if (missionId) {
      fetchMission(missionId);
      fetchGraph(missionId);
      subscribeGraph(missionId);
    }

    return () => {
      unsubscribeGraph();
    };
  }, [missionId, fetchMission, fetchGraph, subscribeGraph, unsubscribeGraph]);

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  };

  return (
    <div className="flex h-screen bg-slate-950">
      {!isFullscreen && <Sidebar />}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="h-14 border-b border-slate-800 px-4 flex items-center justify-between bg-slate-900/90 backdrop-blur-md shrink-0">
          <div className="flex items-center gap-4">
            <Network className="text-cyan-400" size={20} />
            <div>
              <h1 className="text-white font-bold">Asset Graph</h1>
              {currentMission && (
                <p className="text-slate-500 text-xs">{currentMission.targetDomain}</p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-4">
            {/* Stats */}
            <div className="flex items-center gap-4 text-sm">
              <div className="flex items-center gap-2">
                <span className="text-slate-500">Nodes:</span>
                <span className="text-white font-mono">{nodeCount}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-slate-500">Edges:</span>
                <span className="text-white font-mono">{edgeCount}</span>
              </div>
            </div>

            {/* Controls */}
            <div className="flex items-center gap-2">
              <button
                onClick={toggleFullscreen}
                className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
                title="Fullscreen"
              >
                <Maximize2 size={16} />
              </button>
            </div>
          </div>
        </header>

        {/* Graph */}
        <div className="flex-1 relative">
          <AssetGraph missionId={missionId} />
        </div>
      </div>
    </div>
  );
}
