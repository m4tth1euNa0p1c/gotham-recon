"use client";

import { useEffect, useRef, useCallback, useState, useMemo } from "react";
import cytoscape, { Core, NodeSingular, Layouts } from "cytoscape";
import { motion, AnimatePresence } from "framer-motion";
import {
  Pause,
  Play,
  RefreshCw,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Filter,
  X
} from "lucide-react";
import { useWorkflowStore } from "@/stores/workflowStore";
import { useMissionStore } from "@/stores/missionStore";
import { useGraphStore } from "@/stores";
import { WorkflowService } from "@/services/WorkflowService";
import { LayoutService } from "@/services/LayoutService";

// Node colors by type and status
const NODE_COLORS = {
  phase: { bg: "#6366f1", border: "#818cf8" },
  agent: {
    pending: { bg: "#64748b", border: "#94a3b8" },
    running: { bg: "#06b6d4", border: "#22d3ee" },
    completed: { bg: "#10b981", border: "#34d399" },
    error: { bg: "#ef4444", border: "#f87171" },
  },
  tool: {
    pending: { bg: "#64748b", border: "#94a3b8" },
    running: { bg: "#f59e0b", border: "#fbbf24" },
    completed: { bg: "#10b981", border: "#34d399" },
    error: { bg: "#ef4444", border: "#f87171" },
  },
  asset: { bg: "#8b5cf6", border: "#a78bfa" },
};

// Edge colors by type
const EDGE_COLORS = {
  TRIGGERS: "#06b6d4",
  USES_TOOL: "#f59e0b",
  PRODUCES: "#10b981",
  REFINES: "#8b5cf6",
  LINKS_TO: "#64748b",
};

// Edge style helpers
const getEdgeStyle = (active: boolean, color: string) => active ? {
  "line-color": color,
  "target-arrow-color": color,
  "width": 3,
  "line-style": "solid",
  "opacity": 1,
} : {
  "line-color": color,
  "target-arrow-color": color,
  "line-style": "solid",
  "opacity": 0.5,
};

interface WorkflowHierarchyProps {
  missionId: string;
  onNodeSelect?: (nodeId: string | null) => void;
  className?: string;
}

export default function WorkflowHierarchy({
  missionId,
  onNodeSelect,
  className = "",
}: WorkflowHierarchyProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const layoutRef = useRef<Layouts | null>(null);
  const isMountedRef = useRef(true);
  const [isReady, setIsReady] = useState(false);

  // Store state - select primitive values or stable references
  const agentRunsMap = useWorkflowStore((state) => state.agentRuns);
  const toolCallsMap = useWorkflowStore((state) => state.toolCalls);
  const workflowEdges = useWorkflowStore((state) => state.edges);
  const showAgents = useWorkflowStore((state) => state.showAgents);
  const showTools = useWorkflowStore((state) => state.showTools);
  const showAssets = useWorkflowStore((state) => state.showAssets);
  const layout = useWorkflowStore((state) => state.layout);

  // Memoize array conversions to prevent recreation on every render
  const agentRuns = useMemo(() => Array.from(agentRunsMap.values()), [agentRunsMap]);
  const toolCalls = useMemo(() => Array.from(toolCallsMap.values()), [toolCallsMap]);

  // Store actions (these don't need useShallow as they're stable)
  // Store actions
  const setLayout = useWorkflowStore((state) => state.setLayout);
  const updateNodePosition = useWorkflowStore((state) => state.updateNodePosition);
  const selectNode = useWorkflowStore((state) => state.selectNode);
  const setConnectionStatus = useWorkflowStore((state) => state.setConnectionStatus);
  const toggleAgents = useWorkflowStore((state) => state.toggleAgents);
  const toggleTools = useWorkflowStore((state) => state.toggleTools);
  const toggleAssets = useWorkflowStore((state) => state.toggleAssets);

  // Mission Store
  const currentMission = useMissionStore((state) => state.currentMission);

  // Local UI state
  const [liveMode, setLiveMode] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [showFilters, setShowFilters] = useState(false);

  const toggleLayer = (layer: 'agents' | 'tools' | 'assets') => {
    if (layer === 'agents') toggleAgents();
    else if (layer === 'tools') toggleTools();
    else if (layer === 'assets') toggleAssets();
  };

  // Graph store for assets
  const graphNodes = useGraphStore((state) => state.nodes);

  // Build elements for Cytoscape
  const buildElements = useCallback(() => {
    const elements: cytoscape.ElementDefinition[] = [];

    // Add phase nodes (group agents by phase)
    const PHASE_ORDER = [
      "OSINT",
      "ACTIVE",
      "INTEL",
      "VERIF",
      "PLANNER",
      "REPORT"
    ];

    // Calculate phase positions (Horizontal Layout)
    const phases = new Set(agentRuns.map((a) => a.data.phase));

    // Determine explicitly strictly ordered phases
    PHASE_ORDER.forEach((phase, index) => {
      if (phases.has(phase as any)) { // Cast as any because string vs Enum
        elements.push({
          data: {
            id: `phase-${phase}`,
            label: phase.toUpperCase(),
            type: "phase",
          },
          // Fix position for L-R layout
          position: { x: index * 600, y: 0 },
          locked: true, // Lock phase nodes so they don't move during layout
          grabbable: false
        });
      }
    });

    // Add any remaining phases not in strict order (fallback)
    phases.forEach((phase) => {
      if (phase && !PHASE_ORDER.includes(phase)) {
        elements.push({
          data: { id: `phase-${phase}`, label: phase.toUpperCase(), type: "phase" },
          position: { x: PHASE_ORDER.length * 600, y: 0 }, // Place at end
          locked: true
        });
      }
    });

    // Add agent nodes with minimal data
    if (showAgents) {
      agentRuns.forEach((agent) => {
        elements.push({
          data: {
            id: agent.id,
            label: agent.data.agentName,
            type: "agent",
            status: agent.status,
            parent: agent.data.phase ? `phase-${agent.data.phase}` : undefined,
          },
        });
      });
    }

    // Add tool nodes with minimal data
    if (showTools) {
      toolCalls.forEach((tool) => {
        elements.push({
          data: {
            id: tool.id,
            label: tool.data.toolName,
            type: "tool",
            status: tool.status,
          },
        });
      });
    }

    // Add asset nodes (limited to those linked by workflow)
    if (showAssets) {
      const linkedAssetIds = new Set<string>();
      workflowEdges
        .filter((e) => e.type === "PRODUCES" || e.type === "REFINES")
        .forEach((e) => linkedAssetIds.add(e.target));

      linkedAssetIds.forEach((assetId) => {
        const asset = graphNodes.get(assetId);
        if (asset) {
          elements.push({
            data: {
              id: asset.id,
              label: asset.properties?.name as string || asset.id.substring(0, 12),
              type: "asset",
              assetType: asset.type,
            },
          });
        }
      });
    }

    // Add edges
    // Pre-index existing node ids to avoid optional chaining noise
    const elementIds = new Set(
      elements
        .map((e) => e.data?.id)
        .filter((id): id is string => Boolean(id))
    );

    workflowEdges.forEach((edge) => {
      // Check if both nodes are visible
      // Note: WorkflowEdge now uses source/target, not fromNode/toNode (DomainEdge)
      const fromExists = elementIds.has(edge.source);
      const toExists = elementIds.has(edge.target);

      if (fromExists && toExists) {
        // Determine edge activity
        const fromNode = elements.find(e => e.data.id === edge.source);
        const active = fromNode?.data.status === "running";

        const edgeId = edge.id || `edge-${edge.source}-${edge.target}-${edge.type}`;
        elements.push({
          data: {
            id: edgeId,
            source: edge.source,
            target: edge.target,
            relation: edge.type, // Using 'type' (EdgeType) instead of 'relation'
            active: active, // For styling
          },
        });
      }
    });

    // Add USES_TOOL edges (agent -> tool)
    if (showAgents && showTools) {
      toolCalls.forEach((tool) => {
        if (tool.data.agentId && elementIds.has(tool.data.agentId)) {
          elements.push({
            data: {
              id: `edge-${tool.data.agentId}-${tool.id}`,
              source: tool.data.agentId,
              target: tool.id,
              relation: "USES_TOOL",
            },
          });
        }
      });
    }

    return elements;
  }, [agentRuns, toolCalls, workflowEdges, graphNodes, showAgents, showTools, showAssets]);

  // Build stylesheet
  const getStylesheet = useCallback(() => {
    return [
      // Phase nodes (compound)
      {
        selector: 'node[type="phase"]',
        style: {
          "background-color": NODE_COLORS.phase.bg,
          "border-color": NODE_COLORS.phase.border,
          "border-width": 2,
          label: "data(label)",
          "text-valign": "top",
          "text-halign": "center",
          "font-size": "14px",
          "font-weight": "bold",
          color: "#ffffff",
          "text-margin-y": -10,
          "compound-sizing-wrt-labels": "include",
          "padding": "20px",
        },
      },
      // Agent nodes with enhanced visual design
      {
        selector: 'node[type="agent"]',
        style: {
          "background-color": NODE_COLORS.agent.pending.bg,
          "border-color": NODE_COLORS.agent.pending.border,
          "border-width": 3,
          "border-opacity": 0.8,
          width: 70,
          height: 70,
          label: "data(label)",
          "text-valign": "bottom",
          "text-halign": "center",
          "font-size": "12px",
          "font-weight": "600",
          color: "#f1f5f9",
          "text-margin-y": 12,
          "text-outline-color": "#0a0a0f",
          "text-outline-width": 2,
          shape: "hexagon",
          "text-wrap": "wrap",
          "text-max-width": "90px",
          "box-shadow": "0 0 15px rgba(100, 116, 139, 0.5)"
        },
      },
      {
        selector: 'node[type="agent"][status="running"]',
        style: {
          "background-color": NODE_COLORS.agent.running.bg,
          "border-color": NODE_COLORS.agent.running.border,
          "border-width": 4,
          "border-opacity": 1,
          "box-shadow": "0 0 25px #00ffff, 0 0 50px rgba(0, 255, 255, 0.3)",
          "transition-property": "box-shadow, border-width",
          "transition-duration": "300ms"
        },
      },
      // ... statuses (completed/error) kept same logic, just updated above selectors implied ...
      {
        selector: 'node[type="agent"][status="completed"]',
        style: {
          "background-color": NODE_COLORS.agent.completed.bg,
          "border-color": NODE_COLORS.agent.completed.border,
          "border-width": 3,
          "box-shadow": "0 0 15px #22c55e",
          opacity: 0.9,
        },
      },
      {
        selector: 'node[type="agent"][status="error"]',
        style: {
          "background-color": NODE_COLORS.agent.error.bg,
          "border-color": NODE_COLORS.agent.error.border,
          "border-width": 4,
          "box-shadow": "0 0 20px #ef4444",
        },
      },
      // Tool nodes with enhanced styling
      {
        selector: 'node[type="tool"]',
        style: {
          "background-color": NODE_COLORS.tool.pending.bg,
          "border-color": NODE_COLORS.tool.pending.border,
          "border-width": 2,
          "border-opacity": 0.7,
          width: 45,
          height: 45,
          label: "data(label)",
          "text-halign": "center",
          "text-valign": "bottom",
          "font-size": "10px",
          "font-weight": "500",
          color: "#cbd5e1",
          "text-margin-y": 6,
          "text-outline-color": "#0a0a0f",
          "text-outline-width": 1.5,
          shape: "round-rectangle",
          "box-shadow": "0 0 10px rgba(148, 163, 184, 0.3)"
        },
      },
      // ... tool statuses ...
      {
        selector: 'node[type="tool"][status="running"]',
        style: {
          "background-color": NODE_COLORS.tool.running.bg,
          "border-color": NODE_COLORS.tool.running.border,
          "border-width": 3,
          "box-shadow": "0 0 12px #f59e0b",
        },
      },
      {
        selector: 'node[type="tool"][status="completed"]',
        style: {
          "background-color": NODE_COLORS.tool.completed.bg,
          "border-color": NODE_COLORS.tool.completed.border,
        },
      },
      {
        selector: 'node[type="tool"][status="error"]',
        style: {
          "background-color": NODE_COLORS.tool.error.bg,
          "border-color": NODE_COLORS.tool.error.border,
        },
      },
      // Asset nodes (Generic)
      {
        selector: 'node[type="asset"]',
        style: {
          "background-color": NODE_COLORS.asset.bg,
          "border-color": NODE_COLORS.asset.border,
          "border-width": 1,
          width: 25,
          height: 25,
          label: "data(label)",
          "text-valign": "bottom",
          "text-halign": "center",
          "font-size": "8px",
          color: "#64748b",
          "text-margin-y": 3,
          shape: "ellipse", // Default
        },
      },
      // Asset Specifics
      {
        selector: 'node[type="asset"][assetType="VULNERABILITY"]',
        style: {
          shape: "triangle",
          "background-color": "#ef4444", // Red
          "border-color": "#b91c1c",
          width: 30,
          height: 30
        }
      },
      {
        selector: 'node[type="asset"][assetType="ENDPOINT"]',
        style: {
          shape: "tag",
          "background-color": "#f59e0b", // Amber
          "border-color": "#d97706",
          width: 30,
          height: 30
        }
      },
      {
        selector: 'node[type="asset"][assetType="SUBDOMAIN"]',
        style: {
          shape: "diamond",
          "background-color": "#06b6d4", // Cyan
          "border-color": "#0891b2",
        }
      },
      // Selected node
      {
        selector: "node:selected",
        style: {
          "border-color": "#00ffff",
          "border-width": 4,
          "box-shadow": "0 0 10px #00ffff",
        },
      },
      // Edges
      {
        selector: "edge",
        style: {
          width: 2,
          "line-color": "#64748b",
          "target-arrow-color": "#64748b",
          "target-arrow-shape": "triangle",
          "curve-style": "bezier",
          opacity: 0.7,
        },
      },
      {
        selector: 'edge[relation="TRIGGERS"]',
        style: {
          "line-color": EDGE_COLORS.TRIGGERS,
          "target-arrow-color": EDGE_COLORS.TRIGGERS,
          width: 3,
        },
      },
      {
        selector: 'edge[relation="USES_TOOL"]',
        style: {
          "line-color": EDGE_COLORS.USES_TOOL,
          "target-arrow-color": EDGE_COLORS.USES_TOOL,
          "line-style": "dashed",
        },
      },
      {
        selector: 'edge[relation="PRODUCES"]',
        style: {
          "line-color": EDGE_COLORS.PRODUCES,
          "target-arrow-color": EDGE_COLORS.PRODUCES,
        },
      },
      {
        selector: 'edge[relation="REFINES"]',
        style: {
          "line-color": EDGE_COLORS.REFINES,
          "target-arrow-color": EDGE_COLORS.REFINES,
          "line-style": "dotted",
        },
      },
      {
        selector: 'edge[relation="TRIGGERS"][active="true"]',
        style: {
          "line-color": EDGE_COLORS.TRIGGERS,
          "target-arrow-color": EDGE_COLORS.TRIGGERS,
          width: 4,
          "shadow-blur": 10,
          "shadow-color": EDGE_COLORS.TRIGGERS,
          "line-style": "solid",
        },
      },
      {
        selector: 'edge[relation="PRODUCES"][active="true"]',
        style: {
          "line-color": EDGE_COLORS.PRODUCES,
          "target-arrow-color": EDGE_COLORS.PRODUCES,
          width: 4,
          "line-style": "dashed",
          "line-dash-pattern": [6, 3],
        },
      },
      // Flash effect for new nodes
      {
        selector: '.flash-effect',
        style: {
          "background-color": "#22c55e",
          "border-color": "#22c55e",
          "border-width": 5,
          "box-shadow": "0 0 30px #22c55e",
          "transition-duration": "0ms"
        },
      },
    ];
  }, []);

  // Initialize Cytoscape
  useEffect(() => {
    if (!containerRef.current) return;

    isMountedRef.current = true;

    const cy = cytoscape({
      container: containerRef.current,
      headless: false,
      elements: [],
      style: getStylesheet() as cytoscape.StylesheetStyle[],
      layout: { name: "preset" },
      minZoom: 0.2,
      maxZoom: 3,
      // Remove custom wheelSensitivity to use default
    });

    cyRef.current = cy;

    // Handle node selection
    cy.on("tap", "node", (evt) => {
      if (!isMountedRef.current || cy.destroyed()) return;
      const node = evt.target as NodeSingular;
      if (node && typeof node.id === 'function') {
        const nodeId = node.id();
        selectNode(nodeId);
        onNodeSelect?.(nodeId);
      }
    });

    // Handle background click (deselect)
    cy.on("tap", (evt) => {
      if (!isMountedRef.current || cy.destroyed()) return;
      if (evt.target === cy) {
        selectNode(null);
        onNodeSelect?.(null);
      }
    });

    // Handle node drag for layout persistence
    cy.on("dragfree", "node", (evt) => {
      if (!isMountedRef.current || cy.destroyed()) return;
      const node = evt.target as NodeSingular;
      const pos = node.position();
      updateNodePosition(node.id(), pos.x, pos.y);
    });

    setIsReady(true);

    return () => {
      isMountedRef.current = false;
      // Stop any running layout first
      if (layoutRef.current) {
        try {
          layoutRef.current.stop();
        } catch {
          // Ignore
        }
        layoutRef.current = null;
      }
      if (cy && !cy.destroyed()) {
        try {
          cy.stop(true, true);
          cy.elements().stop(true, true);
        } catch {
          // Ignore errors during cleanup
        }
        cy.removeAllListeners();
        cy.destroy();
      }
      cyRef.current = null;
    };
  }, [getStylesheet, selectNode, onNodeSelect, updateNodePosition]);

  // Handle toolbar actions
  const handleFit = () => {
    const cy = cyRef.current;
    if (cy && !cy.destroyed()) cy.fit();
  };
  const handleZoomIn = () => {
    const cy = cyRef.current;
    if (cy && !cy.destroyed()) cy.zoom((cy.zoom() || 1) * 1.2);
  };
  const handleZoomOut = () => {
    const cy = cyRef.current;
    if (cy && !cy.destroyed()) cy.zoom((cy.zoom() || 1) * 0.8);
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    // Simulate refresh or re-fetch
    setTimeout(() => setIsRefreshing(false), 800);
  };

  // Update connection status
  useEffect(() => {
    // Check WS connectivity logic here if available, or rely on store
    setIsConnected(true); // Placeholder, ideally derived from store
  }, []);

  // Update elements when data changes
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || cy.destroyed() || !isReady || !isMountedRef.current) return;

    // Stop any running layout before making changes
    if (layoutRef.current) {
      try {
        layoutRef.current.stop();
      } catch {
        // Ignore
      }
      layoutRef.current = null;
    }

    const elements = buildElements();

    // Batch update with Diffing
    cy.batch(() => {
      if (cy.destroyed() || !isMountedRef.current) return;

      const newIds = new Set(elements.map((e) => e.data.id as string));
      const currentElements = cy.elements();

      // IMPORTANT: Do NOT remove old nodes - keep agents visible permanently
      // Only remove edges that are no longer valid
      currentElements.edges().forEach((edge) => {
        if (!newIds.has(edge.id())) {
          edge.remove();
        }
      });

      // 2. Add or Update elements
      elements.forEach((eleDef) => {
        const id = eleDef.data.id as string;
        const existing = cy.getElementById(id);

        if (existing.length > 0) {
          // Update data for existing elements
          existing.data(eleDef.data);

          // Update position if specified and not a phase node
          if (eleDef.position && eleDef.data.type !== 'phase') {
            const currentPos = existing.position();
            // Only update if position actually changed (avoid unnecessary updates)
            if (Math.abs(currentPos.x - eleDef.position.x) > 1 ||
              Math.abs(currentPos.y - eleDef.position.y) > 1) {
              existing.position(eleDef.position);
            }
          }

          // Check for parent changes (compound node structure)
          if (eleDef.data.parent) {
            const currentParent = existing.parent();
            const currentParentId = currentParent.length > 0 ? (currentParent as any).id() : undefined;

            if (currentParentId !== eleDef.data.parent) {
              existing.move({ parent: eleDef.data.parent });
            }
          }
        } else {
          // Add new element with animation
          const newEle = cy.add(eleDef);

          // Flash effect for new nodes (not phases)
          if (eleDef.data.type !== 'phase') {
            newEle.flashClass('flash-effect', 1200);
          }
        }
      });

      // Apply saved positions (only to existing nodes)
      if (layout?.positions) {
        cy.nodes().forEach((node) => {
          if (cy.destroyed() || !isMountedRef.current) return;
          const savedPos = layout.positions[node.id()];
          if (savedPos && !node.grabbed()) {
            node.position(savedPos);
          }
        });
      }
    });

    // Run layout if no saved positions (with safety check)
    if (!cy.destroyed() && isMountedRef.current && (!layout?.positions || Object.keys(layout.positions).length === 0)) {
      const newLayout = cy.layout({
        name: "cose",
        animate: true,
        animationDuration: 500,
        nodeRepulsion: () => 8000,
        idealEdgeLength: () => 100,
        gravity: 0.25,
        numIter: 100,
        stop: () => {
          // Clear layout ref when done
          if (layoutRef.current === newLayout) {
            layoutRef.current = null;
          }
        },
      } as cytoscape.CoseLayoutOptions);
      layoutRef.current = newLayout;
      newLayout.run();
    }

    // Apply zoom and pan if saved
    if (!cy.destroyed() && isMountedRef.current) {
      if (layout?.zoom) {
        cy.zoom(layout.zoom);
      }
      if (layout?.pan) {
        cy.pan(layout.pan);
      }
    }
  }, [buildElements, layout, isReady]);

  // Subscribe to workflow events and load initial data
  useEffect(() => {
    if (!missionId) return;

    // Subscribe store to mission events
    useWorkflowStore.getState().subscribe(missionId);

    // Load saved layout
    LayoutService.loadLayout(missionId).then((savedLayout) => {
      if (savedLayout && isMountedRef.current) {
        setLayout(savedLayout);
      }
    });

    return () => {
      useWorkflowStore.getState().unsubscribe();
    };
  }, [missionId, setLayout]);

  // Save layout periodically
  useEffect(() => {
    if (!missionId || !layout) return;

    const saveTimeout = setTimeout(() => {
      LayoutService.saveLayout(missionId, layout);
    }, 2000); // Debounce 2 seconds

    return () => clearTimeout(saveTimeout);
  }, [missionId, layout]);

  return (
    <div
      ref={containerRef}
      className={`w-full h-full bg-[#0a0a0f] ${className}`}
      style={{ minHeight: "400px" }}
    >
      {/* Cyber Toolbar Overlay (Top Right) */}
      <div className="absolute top-4 right-4 flex flex-col gap-2 z-10 pointer-events-auto">
        {/* Live Status Card */}
        <div className="bg-[#0d0d12]/90 backdrop-blur-md border border-white/10 rounded-lg shadow-lg shadow-black/30 p-2 flex items-center gap-3">
          <div className={`flex items-center gap-2 px-2 py-1 rounded text-xs font-mono font-bold ${liveMode ? "text-[#00ff41] bg-[#00ff41]/10 border border-[#00ff41]/20" : "text-gray-400 bg-white/5 border border-white/10"
            }`}>
            <div className={`w-2 h-2 rounded-full ${liveMode ? "bg-[#00ff41] animate-pulse" : "bg-gray-500"}`} />
            {liveMode ? "LIVE STREAM" : "PAUSED"}
          </div>

          <div className="h-4 w-px bg-white/10" />

          <div className="flex gap-1">
            <button
              onClick={() => setLiveMode(!liveMode)}
              className="p-1.5 hover:bg-white/10 rounded text-cyan-400 transition-colors"
              title={liveMode ? "Pause Stream" : "Resume Stream"}
            >
              {liveMode ? (
                <Pause size={14} />
              ) : (
                <Play size={14} />
              )}
            </button>
            <button
              onClick={handleRefresh}
              className={`p-1.5 hover:bg-white/10 rounded text-cyan-400 transition-colors ${isRefreshing ? "animate-spin" : ""}`}
              title="Refresh Graph"
            >
              <RefreshCw size={14} />
            </button>
          </div>
        </div>

        {/* Graph Controls */}
        <div className="bg-[#0d0d12]/90 backdrop-blur-md border border-white/10 rounded-lg shadow-lg shadow-black/30 p-2 flex flex-col gap-1 items-center">
          <button onClick={handleZoomIn} className="p-1.5 hover:bg-white/10 rounded text-gray-400 hover:text-white transition-colors" title="Zoom In"><ZoomIn size={16} /></button>
          <button onClick={handleZoomOut} className="p-1.5 hover:bg-white/10 rounded text-gray-400 hover:text-white transition-colors" title="Zoom Out"><ZoomOut size={16} /></button>
          <button onClick={handleFit} className="p-1.5 hover:bg-white/10 rounded text-gray-400 hover:text-white transition-colors" title="Fit to Screen"><Maximize2 size={16} /></button>
          <div className="h-px w-full bg-white/10 my-1" />
          <button onClick={() => setShowFilters(!showFilters)} className={`p-1.5 hover:bg-white/10 rounded transition-colors ${showFilters ? "text-cyan-400" : "text-gray-400 hover:text-white"}`} title="Toggle Filters"><Filter size={16} /></button>
        </div>
      </div>



      {/* Timeline / Slider (Bottom) */}
      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 w-1/2 z-10 pointer-events-none">
        <div className="bg-[#0d0d12]/90 backdrop-blur border border-white/10 rounded-full px-4 py-2 flex items-center gap-4 shadow-lg pointer-events-auto">
          <span className="text-[10px] font-mono text-gray-500">START</span>
          <div className="flex-1 h-1 bg-gray-800 rounded-full overflow-hidden relative group cursor-pointer">
            <div className="absolute top-0 left-0 h-full bg-cyan-500 w-full" />
            {/* Replay handle would go here */}
          </div>
          <span className="text-[10px] font-mono text-gray-500">NOW</span>
        </div>
      </div>

      {/* Filters Panel (Conditional) */}
      <AnimatePresence>
        {showFilters && (
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            className="absolute top-4 right-16 z-10 bg-[#0d0d12]/95 backdrop-blur border border-white/10 rounded-lg p-4 shadow-xl w-64 pointer-events-auto"
          >
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-xs font-bold uppercase text-gray-400 tracking-wider">View Filters</h3>
              <button onClick={() => setShowFilters(false)} className="text-gray-500 hover:text-white"><X size={14} /></button>
            </div>

            <div className="space-y-3">
              <label className="flex items-center justify-between text-sm text-gray-300 cursor-pointer">
                <span>Show Agents</span>
                <input type="checkbox" checked={showAgents} onChange={() => toggleLayer('agents')} className="accent-cyan-500" />
              </label>
              <label className="flex items-center justify-between text-sm text-gray-300 cursor-pointer">
                <span>Show Tools</span>
                <input type="checkbox" checked={showTools} onChange={() => toggleLayer('tools')} className="accent-cyan-500" />
              </label>
              <label className="flex items-center justify-between text-sm text-gray-300 cursor-pointer">
                <span>Show Assets</span>
                <input type="checkbox" checked={showAssets} onChange={() => toggleLayer('assets')} className="accent-cyan-500" />
              </label>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
