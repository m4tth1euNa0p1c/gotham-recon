"use client";

import { useEffect, useMemo, useRef } from "react";
import CytoscapeComponent from "react-cytoscapejs";
import cytoscape, { Core, ElementDefinition } from "cytoscape";
import dagre from "cytoscape-dagre";
import { useWorkflowStore } from "@/stores/workflowStore";

// Register dagre layout
cytoscape.use(dagre);

// ============================================================================
// STYLES
// ============================================================================

const cyStyles: any[] = [
  // --- GLOBAL NODE STYLE ---
  {
    selector: 'node',
    style: {
      'background-color': '#0f172a', // Slate 900
      'border-width': 2,
      'border-color': '#334155',     // Slate 700
      'label': 'data(label)',
      'color': '#e2e8f0',            // Slate 200
      'font-size': 12,
      'font-family': 'monospace',
      'text-valign': 'bottom',
      'text-margin-y': 8,
      'text-background-opacity': 0,
      'transition-property': 'background-color, border-color, border-width',
      'transition-duration': 300
    }
  },

  // --- 1. PHASE NODES (Backbone) ---
  {
    selector: 'node[type="phase"]',
    style: {
      'shape': 'ellipse', // Explicitly requested Circle/Octagon-ish backbone
      'width': 70,
      'height': 70,
      'text-valign': 'center',
      'text-margin-y': 0,
      'font-weight': 'bold',
      'font-size': 12,
      'color': '#fff'
    }
  },
  // Phase Specific Colors
  {
    selector: 'node[type="phase"][phase="OSINT"]',
    style: { 'border-color': '#06b6d4', 'color': '#22d3ee' }
  },
  {
    selector: 'node[type="phase"][phase="ACTIVE"]',
    style: { 'border-color': '#f59e0b', 'color': '#fbbf24' }
  },
  {
    selector: 'node[type="phase"][phase="INTEL"]',
    style: { 'border-color': '#c084fc', 'color': '#d8b4fe' }
  },
  {
    selector: 'node[type="phase"][phase="VERIF"]',
    style: { 'border-color': '#34d399', 'color': '#6ee7b7' }
  },
  {
    selector: 'node[type="phase"][phase="PLANNER"]',
    style: { 'border-color': '#f43f5e', 'color': '#fda4af' }
  },
  {
    selector: 'node[type="phase"][phase="REPORT"]',
    style: { 'border-color': '#3b82f6', 'color': '#93c5fd' }
  },


  // --- 2. AGENTS ---
  {
    selector: 'node[type="agent"]',
    style: {
      'shape': 'hexagon',
      'width': 50,
      'height': 50,
      'font-size': 10,
      'text-valign': 'center',
      'text-margin-y': 0
    }
  },
  {
    selector: 'node[type="agent"][phase="OSINT"]',
    style: { 'border-color': '#06b6d4', 'color': '#22d3ee' }
  },
  {
    selector: 'node[type="agent"][phase="ACTIVE"]',
    style: { 'border-color': '#f59e0b', 'color': '#fbbf24' }
  },


  // --- 3. TOOLS ---
  {
    selector: 'node[type="tool"]',
    style: {
      'shape': 'round-rectangle',
      'width': 60,
      'height': 30,
      'font-size': 9,
      'border-color': '#10b981',
      'color': '#34d399'
    }
  },

  // --- 4. ASSETS (Discovered items) ---
  {
    selector: 'node[type="asset"]',
    style: {
      'shape': 'diamond',
      'width': 35,
      'height': 35,
      'font-size': 8,
      'border-color': '#8b5cf6', // Purple
      'color': '#a78bfa'
    }
  },
  // Asset Type Specific Colors
  {
    selector: 'node[type="asset"][assetType="ENDPOINT"]',
    style: { 'border-color': '#f59e0b', 'color': '#fbbf24' } // Amber
  },
  {
    selector: 'node[type="asset"][assetType="VULNERABILITY"]',
    style: { 'border-color': '#ef4444', 'color': '#f87171' } // Red
  },
  {
    selector: 'node[type="asset"][assetType="HYPOTHESIS"]',
    style: { 'border-color': '#f97316', 'color': '#fb923c' } // Orange
  },
  {
    selector: 'node[type="asset"][assetType="SUBDOMAIN"]',
    style: { 'border-color': '#06b6d4', 'color': '#22d3ee' } // Cyan
  },
  {
    selector: 'node[type="asset"][assetType="HTTP_SERVICE"]',
    style: { 'border-color': '#22c55e', 'color': '#4ade80' } // Green
  },

  // --- 5. EDGES ---
  {
    selector: 'edge',
    style: {
      'width': 2,
      'curve-style': 'bezier',
      'line-color': '#334155',
      'target-arrow-color': '#334155',
      'target-arrow-shape': 'triangle',
      'arrow-scale': 1
    }
  },
  // Phase Chain (Solid, Thick)
  {
    selector: 'edge[relation="PHASE_FLOW"]',
    style: {
      'width': 3,
      'line-color': '#475569',
      'target-arrow-color': '#475569'
    }
  },
  // Agent -> Tool (Dashed, Colored)
  {
    selector: 'edge[relation="USES_TOOL"]',
    style: {
      'line-style': 'dashed',
      'line-dash-pattern': [6, 4],
      'width': 2,
      'line-color': '#f59e0b', // Amber/Orange as seen in screenshot
      'target-arrow-color': '#f59e0b'
    }
  },
  // Tool -> Asset (PRODUCES - Dotted, Purple)
  {
    selector: 'edge[relation="PRODUCES"]',
    style: {
      'line-style': 'dotted',
      'line-dash-pattern': [3, 3],
      'width': 1.5,
      'line-color': '#8b5cf6', // Purple
      'target-arrow-color': '#8b5cf6',
      'arrow-scale': 0.8
    }
  },
  // Phase -> Agent (Solid, Colored)
  {
    selector: 'edge[relation="PHASE_AGENT"]',
    style: {
      'width': 2,
      'line-color': '#06b6d4', // Cyan default
      'target-arrow-color': '#06b6d4'
    }
  },
  // Phase Specific Edges
  {
    selector: 'edge[sourcePhase="OSINT"]',
    style: { 'line-color': '#06b6d4', 'target-arrow-color': '#06b6d4' }
  },
  {
    selector: 'edge[sourcePhase="ACTIVE"]',
    style: { 'line-color': '#f59e0b', 'target-arrow-color': '#f59e0b' }
  }
];

// ============================================================================
// COMPONENT
// ============================================================================

interface WorkflowHierarchyProps {
  missionId?: string;
  onNodeSelect?: (nodeId: string | null) => void;
  className?: string;
}

export default function WorkflowHierarchy({
  missionId,
  onNodeSelect,
  className = "",
}: WorkflowHierarchyProps) {
  const cyRef = useRef<Core | null>(null);

  // Store
  const agentRunsMap = useWorkflowStore((state) => state.agentRuns);
  const toolCallsMap = useWorkflowStore((state) => state.toolCalls);
  const producedAssetsMap = useWorkflowStore((state) => state.producedAssets);
  const storeEdges = useWorkflowStore((state) => state.edges);
  const selectNode = useWorkflowStore((state) => state.selectNode);

  // Convert Store Maps to Arrays
  const agentRuns = useMemo(() => Array.from(agentRunsMap.values()), [agentRunsMap]);
  const toolCalls = useMemo(() => Array.from(toolCallsMap.values()), [toolCallsMap]);
  const producedAssets = useMemo(() => Array.from(producedAssetsMap.values()), [producedAssetsMap]);

  // ============================================================================
  // DATA TRANSFORMATION
  // ============================================================================

  const elements = useMemo(() => {
    const els: ElementDefinition[] = [];

    // Track active phases
    const activePhases = new Set<string>();
    agentRuns.forEach(a => activePhases.add(a.data.phase || "OSINT"));

    // Build agent lookup maps (by ID and by name)
    const agentIdSet = new Set(agentRuns.map(a => a.id));
    const agentNameToId = new Map<string, string>();
    agentRuns.forEach(a => {
      const name = a.data.agentName || a.label;
      if (name) {
        // Store multiple variations of the name for matching
        agentNameToId.set(name, a.id);
        agentNameToId.set(name.toLowerCase(), a.id);
        agentNameToId.set(name.replace(/_/g, ''), a.id);
        agentNameToId.set(name.replace(/_agent$/, ''), a.id);
      }
    });

    // Sort phases to create backbone
    const phaseOrder = ["OSINT", "ACTIVE", "INTEL", "VERIF", "PLANNER", "REPORT"];
    const phasesPresent = phaseOrder.filter(p => activePhases.has(p));

    // 1. PHASE NODES (Backbone)
    phasesPresent.forEach((phase, index) => {
      els.push({
        group: 'nodes',
        data: {
          id: `phase_${phase}`,
          label: phase,
          type: 'phase',
          phase: phase
        },
        classes: 'phase'
      });

      // Link Phases sequentially
      if (index > 0) {
        const prevPhase = phasesPresent[index - 1];
        els.push({
          group: 'edges',
          data: {
            id: `flow_${prevPhase}_${phase}`,
            source: `phase_${prevPhase}`,
            target: `phase_${phase}`,
            relation: 'PHASE_FLOW'
          }
        });
      }
    });

    // 2. AGENTS (Linked to their Phase)
    agentRuns.forEach((agent) => {
      const phase = agent.data.phase || "OSINT";

      els.push({
        group: 'nodes',
        data: {
          id: agent.id,
          label: agent.data.agentName || agent.label || "Agent",
          type: 'agent',
          phase: phase,
          status: agent.status
        },
        classes: `agent ${phase}`
      });

      // Edge: Phase -> Agent
      if (activePhases.has(phase)) {
        els.push({
          group: 'edges',
          data: {
            id: `link_phase_${phase}_${agent.id}`,
            source: `phase_${phase}`,
            target: agent.id,
            relation: 'PHASE_AGENT',
            sourcePhase: phase
          }
        });
      }
    });

    // 3. TOOLS (Link to agent by ID or by name)
    toolCalls.forEach((tool) => {
      const toolAgentRef = tool.data.agentId || "";

      // Try to find matching agent: by ID first, then by name variations
      let matchedAgentId: string | null = null;

      if (agentIdSet.has(toolAgentRef)) {
        matchedAgentId = toolAgentRef;
      } else if (agentNameToId.has(toolAgentRef)) {
        matchedAgentId = agentNameToId.get(toolAgentRef)!;
      } else if (agentNameToId.has(toolAgentRef.toLowerCase())) {
        matchedAgentId = agentNameToId.get(toolAgentRef.toLowerCase())!;
      } else if (agentNameToId.has(toolAgentRef.replace(/_/g, ''))) {
        matchedAgentId = agentNameToId.get(toolAgentRef.replace(/_/g, ''))!;
      }

      // Add tool node
      els.push({
        group: 'nodes',
        data: {
          id: tool.id,
          label: tool.data.toolName || tool.label || "Tool",
          type: 'tool',
          status: tool.status
        }
      });

      // Link to agent if found
      if (matchedAgentId) {
        els.push({
          group: 'edges',
          data: {
            id: `${matchedAgentId}_uses_${tool.id}`,
            source: matchedAgentId,
            target: tool.id,
            relation: 'USES_TOOL'
          }
        });
      }
    });

    // 4. ASSETS (Produced by tools/agents - only show key types)
    const importantAssetTypes = ['ENDPOINT', 'VULNERABILITY', 'HYPOTHESIS', 'SUBDOMAIN', 'HTTP_SERVICE', 'ATTACK_PATH'];
    const toolIdSet = new Set(toolCalls.map(t => t.id));

    producedAssets.forEach((asset) => {
      // Only show important asset types to avoid clutter
      if (!importantAssetTypes.includes(asset.type)) return;

      // Limit to assets with known origins
      const originId = asset.originToolId || asset.originAgentId;
      if (!originId) return;

      // Check if origin exists
      const originExists = toolIdSet.has(originId) || agentIdSet.has(originId) ||
        agentNameToId.has(originId) || agentNameToId.has(originId.toLowerCase());

      if (!originExists) return;

      const assetLabel = asset.label || asset.id || 'Asset';
      els.push({
        group: 'nodes',
        data: {
          id: asset.id,
          label: assetLabel.substring(0, 15) + (assetLabel.length > 15 ? '...' : ''),
          type: 'asset',
          assetType: asset.type
        }
      });

      // Create PRODUCES edge
      let resolvedOriginId = originId;
      if (!toolIdSet.has(originId) && !agentIdSet.has(originId)) {
        // Try to resolve agent name to ID
        if (agentNameToId.has(originId)) {
          resolvedOriginId = agentNameToId.get(originId)!;
        } else if (agentNameToId.has(originId.toLowerCase())) {
          resolvedOriginId = agentNameToId.get(originId.toLowerCase())!;
        }
      }

      els.push({
        group: 'edges',
        data: {
          id: `${resolvedOriginId}_produces_${asset.id}`,
          source: resolvedOriginId,
          target: asset.id,
          relation: 'PRODUCES'
        }
      });
    });

    // 5. Add any additional PRODUCES edges from store
    storeEdges.forEach((edge) => {
      if (edge.type === 'PRODUCES') {
        const edgeExists = els.some(
          e => e.group === 'edges' && e.data.source === edge.source && e.data.target === edge.target
        );
        if (!edgeExists) {
          // Check if both source and target exist
          const sourceExists = toolIdSet.has(edge.source) || agentIdSet.has(edge.source);
          const targetExists = els.some(e => e.group === 'nodes' && e.data.id === edge.target);
          if (sourceExists && targetExists) {
            els.push({
              group: 'edges',
              data: {
                id: edge.id,
                source: edge.source,
                target: edge.target,
                relation: 'PRODUCES'
              }
            });
          }
        }
      }
    });

    return els;
  }, [agentRuns, toolCalls, producedAssets, storeEdges]);

  // ============================================================================
  // EFFECTS
  // ============================================================================

  // Fit view & Layout on change
  useEffect(() => {
    if (cyRef.current) {
      // Dagre Layout Settings
      const layoutConfig = {
        name: 'dagre',
        rankDir: 'TB',     // Top to Bottom: Phases at top, Agents/Tools below
        ranker: 'network-simplex',
        nodeSep: 80,
        rankSep: 80,
        spacingFactor: 1.2,
        animate: true,
        animationDuration: 500,
        fit: true,
        padding: 50
      };

      try {
        cyRef.current.layout(layoutConfig as any).run();
      } catch (e) {
        console.error("Layout error:", e);
      }
    }
  }, [elements]);

  // Animation for "Running" nodes
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    const runPulse = () => {
      const runningNodes = cy.nodes('[status="running"]');

      runningNodes.forEach(node => {
        const start = { style: { 'border-width': 4, 'overlay-opacity': 0.3 } };
        const end = { style: { 'border-width': 2, 'overlay-opacity': 0 } };

        node.animation({
          style: start.style,
          duration: 800
        } as any).play().promise('complete').then(() => {
          node.animation({
            style: end.style,
            duration: 800
          } as any).play();
        });
      });
    };

    const interval = setInterval(runPulse, 2000);
    return () => clearInterval(interval);
  }, [elements]);

  return (
    <div className={`relative w-full h-full bg-slate-950 ${className}`}>
      {elements.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center text-slate-500 text-sm">
          Waiting for mission events...
        </div>
      )}

      <CytoscapeComponent
        elements={elements}
        style={{ width: "100%", height: "100%" }}
        stylesheet={cyStyles}
        cy={(cy) => {
          cyRef.current = cy;

          cy.on('tap', 'node', (evt) => {
            const node = evt.target;
            const id = node.id();
            if (onNodeSelect) onNodeSelect(id);
            selectNode(id);
          });

          cy.on('tap', (evt) => {
            if (evt.target === cy) {
              if (onNodeSelect) onNodeSelect(null);
              selectNode(null);
            }
          });
        }}
        layout={{ name: 'preset' }}
      />
    </div>
  );
}
