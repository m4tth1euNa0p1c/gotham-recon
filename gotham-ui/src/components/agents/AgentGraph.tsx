"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
    ReactFlow,
    Background,
    Controls,
    MiniMap,
    useNodesState,
    useEdgesState,
    useReactFlow,
    ReactFlowProvider,
    Node,
    Edge,
    Panel,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { motion, AnimatePresence } from "framer-motion";
import { Wifi, WifiOff, RefreshCw, Play, Pause, Loader2 } from "lucide-react";
import AgentNode from "./AgentNode";
import PipelineHUD from "./PipelineHUD";
import AgentInspector from "./AgentInspector";
import { useMissionStore, useGraphStore, useUIStore } from "@/stores";

interface AgentGraphProps {
    missionId?: string;
}

// Agent workflow phases
const AGENT_PHASES = [
    { id: "pathfinder", name: "Pathfinder", role: "Lead Orchestrator", phase: "INIT" },
    { id: "watchtower", name: "Watchtower", role: "Intel Analyst", phase: "PASSIVE_RECON" },
    { id: "stacktrace", name: "StackTrace", role: "Tech Fingerprinter", phase: "ACTIVE_RECON" },
    { id: "deepscript", name: "DeepScript", role: "JS Miner", phase: "JS_ANALYSIS" },
    { id: "enricher", name: "Enricher", role: "Phase 23 Pipeline", phase: "ENRICHMENT" },
    { id: "verifier", name: "Verifier", role: "Phase 25 Pipeline", phase: "VERIFICATION" },
];

const nodeTypes = {
    agent: AgentNode,
};

// Inner component that uses useReactFlow (must be inside ReactFlowProvider)
function AgentGraphInner({ missionId }: AgentGraphProps) {
    // Get ReactFlow instance for reactive resize
    const { fitView } = useReactFlow();

    // Mission state
    const currentMission = useMissionStore((state) => state.currentMission);
    const logs = useMissionStore((state) => state.logs);
    const connectionStatus = useMissionStore((state) => state.connectionStatus);

    // Graph state (subscription is centralized in page.tsx)
    const graphNodes = useGraphStore((state) => state.nodes);
    const graphEdges = useGraphStore((state) => state.edges);
    const graphConnectionStatus = useGraphStore((state) => state.connectionStatus);
    const fetchGraph = useGraphStore((state) => state.fetchGraph);

    // UI state for reactive resize
    const logPanelExpanded = useUIStore((state) => state.logPanelExpanded);

    // Local state
    const [liveMode, setLiveMode] = useState(true);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [inspectorOpen, setInspectorOpen] = useState(false);
    const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);

    // Derive agent status from logs and mission progress
    const agentStatus = useMemo(() => {
        const status: Record<string, { status: string; progress: number; tool: string | null; stats: Record<string, number> }> = {};

        // Initialize all agents as pending
        AGENT_PHASES.forEach((agent) => {
            status[agent.id] = { status: "pending", progress: 0, tool: null, stats: {} };
        });

        // If no mission, show idle state
        if (!currentMission) return status;

        // Derive status from mission phase
        const currentPhase = currentMission.currentPhase || "";
        const missionStatus = currentMission.status;

        // Calculate stats from graph
        const subdomains = Array.from(graphNodes.values()).filter(n => n.type === "SUBDOMAIN").length;
        const endpoints = Array.from(graphNodes.values()).filter(n => n.type === "ENDPOINT").length;
        const services = Array.from(graphNodes.values()).filter(n => n.type === "HTTP_SERVICE").length;
        const vulns = Array.from(graphNodes.values()).filter(n => n.type === "VULNERABILITY").length;

        // Analyze logs to determine agent progress
        const phaseProgress: Record<string, number> = {};
        const phaseTool: Record<string, string | null> = {};

        logs.forEach((log) => {
            const phase = log.phase?.toUpperCase() || "";
            if (phase) {
                phaseProgress[phase] = (phaseProgress[phase] || 0) + 1;
                if (log.metadata?.tool) {
                    phaseTool[phase] = log.metadata.tool as string;
                }
            }
        });

        // Map phases to agents
        const phaseToAgent: Record<string, string> = {
            "INIT": "pathfinder",
            "PASSIVE_RECON": "watchtower",
            "ACTIVE_RECON": "stacktrace",
            "JS_ANALYSIS": "deepscript",
            "ENRICHMENT": "enricher",
            "VERIFICATION": "verifier",
        };

        // Update agent status based on phase analysis
        Object.entries(phaseToAgent).forEach(([phase, agentId]) => {
            const progress = phaseProgress[phase] || 0;
            const isCurrentPhase = currentPhase.toUpperCase().includes(phase);

            if (missionStatus === "completed") {
                status[agentId] = { status: "completed", progress: 100, tool: null, stats: {} };
            } else if (missionStatus === "failed" || missionStatus === "cancelled") {
                status[agentId] = { status: "error", progress: 0, tool: null, stats: {} };
            } else if (isCurrentPhase) {
                status[agentId] = {
                    status: "running",
                    progress: Math.min(progress * 10, 95),
                    tool: phaseTool[phase] || null,
                    stats: {}
                };
            } else if (progress > 0) {
                status[agentId] = { status: "completed", progress: 100, tool: null, stats: {} };
            }
        });

        // Add stats to relevant agents
        status.watchtower.stats = { found: subdomains, processed: subdomains };
        status.stacktrace.stats = { found: services, processed: services };
        status.deepscript.stats = { found: endpoints };
        status.verifier.stats = { vulns: vulns };

        return status;
    }, [currentMission, logs, graphNodes]);

    // Convert to ReactFlow nodes
    const flowNodes: Node[] = useMemo(() => {
        return AGENT_PHASES.map((agent, index) => {
            const row = Math.floor(index / 2);
            const col = index % 2;
            const xOffset = col === 0 ? 100 : 500;
            const yPos = row * 150;

            const agentState = agentStatus[agent.id] || { status: "pending", progress: 0, tool: null, stats: {} };

            return {
                id: agent.id,
                type: "agent",
                position: { x: xOffset, y: yPos },
                data: {
                    name: agent.name,
                    role: agent.role,
                    status: agentState.status,
                    progress: agentState.progress,
                    tool: agentState.tool,
                    stats: agentState.stats,
                },
                draggable: true,
            };
        });
    }, [agentStatus]);

    // Define edges between agents
    const flowEdges: Edge[] = useMemo(() => {
        const getEdgeStyle = (sourceStatus: string, targetStatus: string) => {
            if (sourceStatus === "completed" && targetStatus === "running") {
                return { stroke: "#00ff41", strokeWidth: 2 };
            }
            if (sourceStatus === "running") {
                return { stroke: "#00ffff", strokeWidth: 2 };
            }
            if (sourceStatus === "completed") {
                return { stroke: "#00ff41", strokeWidth: 1 };
            }
            return { stroke: "#2a2a3a", strokeWidth: 1 };
        };

        return [
            {
                id: "e1",
                source: "pathfinder",
                target: "watchtower",
                animated: agentStatus.pathfinder?.status === "running" || agentStatus.watchtower?.status === "running",
                style: getEdgeStyle(agentStatus.pathfinder?.status || "", agentStatus.watchtower?.status || ""),
            },
            {
                id: "e2",
                source: "pathfinder",
                target: "stacktrace",
                animated: agentStatus.pathfinder?.status === "running" || agentStatus.stacktrace?.status === "running",
                style: getEdgeStyle(agentStatus.pathfinder?.status || "", agentStatus.stacktrace?.status || ""),
            },
            {
                id: "e3",
                source: "watchtower",
                target: "deepscript",
                animated: agentStatus.watchtower?.status === "running" || agentStatus.deepscript?.status === "running",
                style: getEdgeStyle(agentStatus.watchtower?.status || "", agentStatus.deepscript?.status || ""),
            },
            {
                id: "e4",
                source: "stacktrace",
                target: "enricher",
                animated: agentStatus.stacktrace?.status === "running" || agentStatus.enricher?.status === "running",
                style: getEdgeStyle(agentStatus.stacktrace?.status || "", agentStatus.enricher?.status || ""),
            },
            {
                id: "e5",
                source: "deepscript",
                target: "enricher",
                animated: agentStatus.deepscript?.status === "running" || agentStatus.enricher?.status === "running",
                style: getEdgeStyle(agentStatus.deepscript?.status || "", agentStatus.enricher?.status || ""),
            },
            {
                id: "e6",
                source: "enricher",
                target: "verifier",
                animated: agentStatus.enricher?.status === "running" || agentStatus.verifier?.status === "running",
                style: getEdgeStyle(agentStatus.enricher?.status || "", agentStatus.verifier?.status || ""),
            },
        ];
    }, [agentStatus]);

    // ReactFlow state
    const [nodes, setNodes, onNodesChange] = useNodesState(flowNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(flowEdges);

    // Update nodes when status changes
    useEffect(() => {
        setNodes(flowNodes);
    }, [flowNodes, setNodes]);

    // Update edges when status changes
    useEffect(() => {
        setEdges(flowEdges);
    }, [flowEdges, setEdges]);

    // NOTE: Subscription is now centralized in page.tsx
    // This component only handles visualization, not data fetching/subscription
    // liveMode controls whether we animate/react to changes, not whether we're subscribed

    // Reactive resize when log panel opens/closes
    useEffect(() => {
        // Small delay to let the DOM update first
        const timer = setTimeout(() => {
            fitView({ padding: 0.1 });
        }, 100);

        return () => clearTimeout(timer);
    }, [logPanelExpanded, fitView]);

    // Refresh handler
    const handleRefresh = async () => {
        if (!missionId) return;
        setIsRefreshing(true);
        await fetchGraph(missionId);
        setIsRefreshing(false);
    };

    const isConnected = connectionStatus === "connected" || graphConnectionStatus === "connected";
    const isActive = currentMission?.status === "running";

    return (
        <>
            <Background color="#1a1a25" gap={30} size={1} />
            <Controls className="!bg-[#0d0d12] !border-[#1a1a25] !rounded-sm" />
            <MiniMap
                nodeColor={(node) => {
                    const status = node.data?.status as string;
                    if (status === "completed") return "#00ff41";
                    if (status === "running") return "#00ffff";
                    if (status === "error") return "#ff0040";
                    return "#3a3a4a";
                }}
                maskColor="rgba(10, 10, 15, 0.9)"
                className="!bg-[#0d0d12] !border !border-[#1a1a25] !rounded-sm"
                style={{ height: 100 }}
            />

            {/* Pipeline HUD */}
            <Panel position="top-left">
                <PipelineHUD
                    onOpenInspector={() => setInspectorOpen(true)}
                    onRefresh={handleRefresh}
                    isRefreshing={isRefreshing}
                    liveMode={liveMode}
                    onToggleLive={() => setLiveMode(!liveMode)}
                />
            </Panel>

            {/* Agent Inspector Drawer */}
            <AgentInspector
                isOpen={inspectorOpen}
                onClose={() => setInspectorOpen(false)}
                selectedAgentId={selectedAgentId}
            />

            {/* Loading overlay */}
            <AnimatePresence>
                {isRefreshing && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="absolute inset-0 bg-[#0a0a0f]/50 flex items-center justify-center z-50"
                    >
                        <Loader2 className="w-8 h-8 text-[#00ffff] animate-spin" />
                    </motion.div>
                )}
            </AnimatePresence>
        </>
    );
}

// Main exported component with ReactFlowProvider wrapper
export default function AgentGraph({ missionId }: AgentGraphProps) {
    // Mission state for nodes/edges
    const currentMission = useMissionStore((state) => state.currentMission);
    const logs = useMissionStore((state) => state.logs);
    const graphNodes = useGraphStore((state) => state.nodes);

    // Derive agent status (duplicated here for initial nodes/edges)
    const agentStatus = useMemo(() => {
        const status: Record<string, { status: string; progress: number; tool: string | null; stats: Record<string, number> }> = {};

        AGENT_PHASES.forEach((agent) => {
            status[agent.id] = { status: "pending", progress: 0, tool: null, stats: {} };
        });

        if (!currentMission) return status;

        const currentPhase = currentMission.currentPhase || "";
        const missionStatus = currentMission.status;
        const subdomains = Array.from(graphNodes.values()).filter(n => n.type === "SUBDOMAIN").length;
        const endpoints = Array.from(graphNodes.values()).filter(n => n.type === "ENDPOINT").length;
        const services = Array.from(graphNodes.values()).filter(n => n.type === "HTTP_SERVICE").length;
        const vulns = Array.from(graphNodes.values()).filter(n => n.type === "VULNERABILITY").length;

        const phaseProgress: Record<string, number> = {};
        const phaseTool: Record<string, string | null> = {};

        logs.forEach((log) => {
            const phase = log.phase?.toUpperCase() || "";
            if (phase) {
                phaseProgress[phase] = (phaseProgress[phase] || 0) + 1;
                if (log.metadata?.tool) {
                    phaseTool[phase] = log.metadata.tool as string;
                }
            }
        });

        const phaseToAgent: Record<string, string> = {
            "INIT": "pathfinder",
            "PASSIVE_RECON": "watchtower",
            "ACTIVE_RECON": "stacktrace",
            "JS_ANALYSIS": "deepscript",
            "ENRICHMENT": "enricher",
            "VERIFICATION": "verifier",
        };

        Object.entries(phaseToAgent).forEach(([phase, agentId]) => {
            const progress = phaseProgress[phase] || 0;
            const isCurrentPhase = currentPhase.toUpperCase().includes(phase);

            if (missionStatus === "completed") {
                status[agentId] = { status: "completed", progress: 100, tool: null, stats: {} };
            } else if (missionStatus === "failed" || missionStatus === "cancelled") {
                status[agentId] = { status: "error", progress: 0, tool: null, stats: {} };
            } else if (isCurrentPhase) {
                status[agentId] = {
                    status: "running",
                    progress: Math.min(progress * 10, 95),
                    tool: phaseTool[phase] || null,
                    stats: {}
                };
            } else if (progress > 0) {
                status[agentId] = { status: "completed", progress: 100, tool: null, stats: {} };
            }
        });

        status.watchtower.stats = { found: subdomains, processed: subdomains };
        status.stacktrace.stats = { found: services, processed: services };
        status.deepscript.stats = { found: endpoints };
        status.verifier.stats = { vulns: vulns };

        return status;
    }, [currentMission, logs, graphNodes]);

    // Initial nodes for ReactFlow
    const initialNodes: Node[] = useMemo(() => {
        return AGENT_PHASES.map((agent, index) => {
            const row = Math.floor(index / 2);
            const col = index % 2;
            const xOffset = col === 0 ? 100 : 500;
            const yPos = row * 150;

            const agentState = agentStatus[agent.id] || { status: "pending", progress: 0, tool: null, stats: {} };

            return {
                id: agent.id,
                type: "agent",
                position: { x: xOffset, y: yPos },
                data: {
                    name: agent.name,
                    role: agent.role,
                    status: agentState.status,
                    progress: agentState.progress,
                    tool: agentState.tool,
                    stats: agentState.stats,
                },
                draggable: true,
            };
        });
    }, [agentStatus]);

    // Initial edges for ReactFlow
    const initialEdges: Edge[] = useMemo(() => {
        const getEdgeStyle = (sourceStatus: string, targetStatus: string) => {
            if (sourceStatus === "completed" && targetStatus === "running") {
                return { stroke: "#00ff41", strokeWidth: 2 };
            }
            if (sourceStatus === "running") {
                return { stroke: "#00ffff", strokeWidth: 2 };
            }
            if (sourceStatus === "completed") {
                return { stroke: "#00ff41", strokeWidth: 1 };
            }
            return { stroke: "#2a2a3a", strokeWidth: 1 };
        };

        return [
            {
                id: "e1",
                source: "pathfinder",
                target: "watchtower",
                animated: agentStatus.pathfinder?.status === "running" || agentStatus.watchtower?.status === "running",
                style: getEdgeStyle(agentStatus.pathfinder?.status || "", agentStatus.watchtower?.status || ""),
            },
            {
                id: "e2",
                source: "pathfinder",
                target: "stacktrace",
                animated: agentStatus.pathfinder?.status === "running" || agentStatus.stacktrace?.status === "running",
                style: getEdgeStyle(agentStatus.pathfinder?.status || "", agentStatus.stacktrace?.status || ""),
            },
            {
                id: "e3",
                source: "watchtower",
                target: "deepscript",
                animated: agentStatus.watchtower?.status === "running" || agentStatus.deepscript?.status === "running",
                style: getEdgeStyle(agentStatus.watchtower?.status || "", agentStatus.deepscript?.status || ""),
            },
            {
                id: "e4",
                source: "stacktrace",
                target: "enricher",
                animated: agentStatus.stacktrace?.status === "running" || agentStatus.enricher?.status === "running",
                style: getEdgeStyle(agentStatus.stacktrace?.status || "", agentStatus.enricher?.status || ""),
            },
            {
                id: "e5",
                source: "deepscript",
                target: "enricher",
                animated: agentStatus.deepscript?.status === "running" || agentStatus.enricher?.status === "running",
                style: getEdgeStyle(agentStatus.deepscript?.status || "", agentStatus.enricher?.status || ""),
            },
            {
                id: "e6",
                source: "enricher",
                target: "verifier",
                animated: agentStatus.enricher?.status === "running" || agentStatus.verifier?.status === "running",
                style: getEdgeStyle(agentStatus.enricher?.status || "", agentStatus.verifier?.status || ""),
            },
        ];
    }, [agentStatus]);

    return (
        <div className="w-full h-full cyber-grid">
            <ReactFlowProvider>
                <ReactFlow
                    nodes={initialNodes}
                    edges={initialEdges}
                    nodeTypes={nodeTypes}
                    fitView
                    className="bg-transparent"
                    defaultEdgeOptions={{
                        style: { strokeWidth: 2 },
                    }}
                    proOptions={{ hideAttribution: true }}
                >
                    <AgentGraphInner missionId={missionId} />
                </ReactFlow>
            </ReactFlowProvider>
        </div>
    );
}
