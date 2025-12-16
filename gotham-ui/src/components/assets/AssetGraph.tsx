"use client";

import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import cytoscape, { Core, ElementDefinition, Layouts } from "cytoscape";
import { motion, AnimatePresence } from "framer-motion";
import {
    Wifi,
    WifiOff,
    RefreshCw,
    Pause,
    Play,
    Loader2,
    ZoomIn,
    ZoomOut,
    Maximize2,
    Filter,
    X,
    FileText,
    GitBranch,
    Network,
    Layers,
} from "lucide-react";
import { useGraphStore, useMissionStore, useUIStore } from "@/stores";
import { GraphNode, GraphEdge, NodeType } from "@/services";
import AIReportDrawer from "./AIReportDrawer";

interface AssetGraphProps {
    missionId?: string;
}

// Node colors with cyber theme
const nodeColors: Record<string, { bg: string; border: string; glow: string }> = {
    DOMAIN: { bg: "#3b82f6", border: "#60a5fa", glow: "rgba(59, 130, 246, 0.5)" },
    SUBDOMAIN: { bg: "#06b6d4", border: "#22d3ee", glow: "rgba(6, 182, 212, 0.5)" },
    IP: { bg: "#6366f1", border: "#818cf8", glow: "rgba(99, 102, 241, 0.5)" },
    HTTP_SERVICE: { bg: "#8b5cf6", border: "#a78bfa", glow: "rgba(139, 92, 246, 0.5)" },
    ENDPOINT: { bg: "#f59e0b", border: "#fbbf24", glow: "rgba(245, 158, 11, 0.5)" },
    TECHNOLOGY: { bg: "#10b981", border: "#34d399", glow: "rgba(16, 185, 129, 0.5)" },
    VULNERABILITY: { bg: "#ef4444", border: "#ff6b6b", glow: "rgba(239, 68, 68, 0.6)" },
    HYPOTHESIS: { bg: "#ec4899", border: "#f472b6", glow: "rgba(236, 72, 153, 0.5)" },
    CREDENTIAL: { bg: "#f97316", border: "#fb923c", glow: "rgba(249, 115, 22, 0.5)" },
    FINDING: { bg: "#a855f7", border: "#c084fc", glow: "rgba(168, 85, 247, 0.5)" },
    // Workflow/Agent nodes
    AGENT_RUN: { bg: "#14b8a6", border: "#2dd4bf", glow: "rgba(20, 184, 166, 0.5)" },
    TOOL_CALL: { bg: "#0ea5e9", border: "#38bdf8", glow: "rgba(14, 165, 233, 0.5)" },
    DNS_RECORD: { bg: "#84cc16", border: "#a3e635", glow: "rgba(132, 204, 22, 0.5)" },
};

const nodeLabels: Record<string, string> = {
    DOMAIN: "Domain",
    SUBDOMAIN: "Subdomain",
    IP: "IP Address",
    HTTP_SERVICE: "HTTP Service",
    ENDPOINT: "Endpoint",
    TECHNOLOGY: "Technology",
    VULNERABILITY: "Vulnerability",
    HYPOTHESIS: "Hypothesis",
    CREDENTIAL: "Credential",
    FINDING: "Finding",
    // Workflow/Agent nodes
    AGENT_RUN: "Agent Run",
    TOOL_CALL: "Tool Call",
    DNS_RECORD: "DNS Record",
};

// Node shapes for different types
const nodeShapes: Record<string, string> = {
    DOMAIN: "hexagon",
    SUBDOMAIN: "ellipse",
    IP: "diamond",
    HTTP_SERVICE: "octagon",
    ENDPOINT: "round-rectangle",
    TECHNOLOGY: "triangle",
    VULNERABILITY: "star",
    HYPOTHESIS: "vee",
    CREDENTIAL: "pentagon",
    FINDING: "tag",
    // Workflow/Agent nodes
    AGENT_RUN: "round-rectangle",
    TOOL_CALL: "barrel",
    DNS_RECORD: "round-diamond",
};

// Node sizes based on importance
const nodeSizes: Record<string, number> = {
    DOMAIN: 60,
    SUBDOMAIN: 45,
    IP: 35,
    HTTP_SERVICE: 40,
    ENDPOINT: 32,
    TECHNOLOGY: 28,
    VULNERABILITY: 42,
    HYPOTHESIS: 35,
    CREDENTIAL: 30,
    FINDING: 30,
    // Workflow/Agent nodes
    AGENT_RUN: 50,
    TOOL_CALL: 38,
    DNS_RECORD: 30,
};

// Layout types
type LayoutType = "hierarchical" | "cose" | "circle" | "grid";

export default function AssetGraph({ missionId }: AssetGraphProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const cyRef = useRef<Core | null>(null);
    const layoutRef = useRef<Layouts | null>(null);
    const isMountedRef = useRef(true);

    // Store state
    const nodes = useGraphStore((state) => state.nodes);
    const edges = useGraphStore((state) => state.edges);
    const connectionStatus = useGraphStore((state) => state.connectionStatus);
    const isLoading = useGraphStore((state) => state.isLoading);
    const fetchGraph = useGraphStore((state) => state.fetchGraph);
    const visibleNodeTypes = useGraphStore((state) => state.visibleNodeTypes);
    const setVisibleNodeTypes = useGraphStore((state) => state.setVisibleNodeTypes);

    const currentMission = useMissionStore((state) => state.currentMission);
    const logPanelExpanded = useUIStore((state) => state.logPanelExpanded);

    // Local state
    const [liveMode, setLiveMode] = useState(true);
    const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
    const [showFilters, setShowFilters] = useState(false);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [reportDrawerOpen, setReportDrawerOpen] = useState(false);
    const [highlightedMentions, setHighlightedMentions] = useState<string[]>([]);
    const [layoutType, setLayoutType] = useState<LayoutType>("hierarchical");

    // Generate logical edges based on node relationships
    const generateLogicalEdges = useCallback((nodesMap: Map<string, GraphNode>): GraphEdge[] => {
        const generatedEdges: GraphEdge[] = [];
        const nodesArray = Array.from(nodesMap.values());
        const targetDomain = currentMission?.targetDomain || "";

        // Create a domain root node edge
        const domainNodeId = `domain:${targetDomain}`;

        nodesArray.forEach((node) => {
            const props = node.properties as Record<string, unknown>;

            // SUBDOMAIN → connects to DOMAIN
            if (node.type === "SUBDOMAIN") {
                const subdomainName = (props.name as string) || (props.subdomain as string) || node.id.split(":").pop() || "";

                // Check if there's a parent subdomain
                const parts = subdomainName.split(".");
                if (parts.length > 2) {
                    // Has parent subdomain (e.g., api.www.example.com → www.example.com)
                    const parentSubdomain = parts.slice(1).join(".");
                    const parentId = `subdomain:${parentSubdomain}`;
                    if (nodesMap.has(parentId)) {
                        generatedEdges.push({
                            fromNode: parentId,
                            toNode: node.id,
                            relation: "HAS_CHILD",
                        });
                    } else {
                        // Connect to domain root
                        generatedEdges.push({
                            fromNode: domainNodeId,
                            toNode: node.id,
                            relation: "CONTAINS",
                        });
                    }
                } else {
                    // Direct child of domain
                    generatedEdges.push({
                        fromNode: domainNodeId,
                        toNode: node.id,
                        relation: "CONTAINS",
                    });
                }
            }

            // HTTP_SERVICE → connects to SUBDOMAIN
            if (node.type === "HTTP_SERVICE") {
                const url = (props.url as string) || "";
                try {
                    const hostname = new URL(url).hostname;
                    const subdomainId = `subdomain:${hostname}`;
                    if (nodesMap.has(subdomainId)) {
                        generatedEdges.push({
                            fromNode: subdomainId,
                            toNode: node.id,
                            relation: "SERVES",
                        });
                    }
                } catch {
                    // Invalid URL, try to extract hostname from id
                    const parts = node.id.split(":");
                    if (parts.length > 1) {
                        const urlPart = parts.slice(1).join(":");
                        try {
                            const hostname = new URL(urlPart).hostname;
                            const subdomainId = `subdomain:${hostname}`;
                            if (nodesMap.has(subdomainId)) {
                                generatedEdges.push({
                                    fromNode: subdomainId,
                                    toNode: node.id,
                                    relation: "SERVES",
                                });
                            }
                        } catch {
                            // Ignore
                        }
                    }
                }
            }

            // ENDPOINT → connects to HTTP_SERVICE or SUBDOMAIN
            if (node.type === "ENDPOINT") {
                const path = (props.path as string) || (props.name as string) || "";
                const origin = (props.origin as string) || "";

                // Try to find parent HTTP service
                let foundParent = false;
                nodesArray.forEach((parentNode) => {
                    if (parentNode.type === "HTTP_SERVICE") {
                        const parentUrl = (parentNode.properties as Record<string, unknown>).url as string;
                        if (parentUrl && origin && origin.includes(new URL(parentUrl).hostname)) {
                            generatedEdges.push({
                                fromNode: parentNode.id,
                                toNode: node.id,
                                relation: "EXPOSES",
                            });
                            foundParent = true;
                        }
                    }
                });

                // If no HTTP service found, connect to subdomain
                if (!foundParent && origin) {
                    try {
                        const hostname = new URL(origin).hostname;
                        const subdomainId = `subdomain:${hostname}`;
                        if (nodesMap.has(subdomainId)) {
                            generatedEdges.push({
                                fromNode: subdomainId,
                                toNode: node.id,
                                relation: "HAS_ENDPOINT",
                            });
                        }
                    } catch {
                        // Ignore
                    }
                }
            }

            // HYPOTHESIS → connects to ENDPOINT or HTTP_SERVICE
            if (node.type === "HYPOTHESIS") {
                const targetId = (props.target_id as string) || (props.endpoint_id as string) || "";
                if (targetId) {
                    // Try to find the target node
                    const possibleIds = [
                        targetId,
                        `endpoint:${targetId}`,
                        `http_service:${targetId}`,
                    ];
                    for (const pid of possibleIds) {
                        if (nodesMap.has(pid)) {
                            generatedEdges.push({
                                fromNode: pid,
                                toNode: node.id,
                                relation: "SUGGESTS",
                            });
                            break;
                        }
                    }
                }
            }

            // VULNERABILITY → connects to target
            if (node.type === "VULNERABILITY") {
                const targetId = (props.target_id as string) || (props.node_id as string) || "";
                if (targetId && nodesMap.has(targetId)) {
                    generatedEdges.push({
                        fromNode: targetId,
                        toNode: node.id,
                        relation: "HAS_VULN",
                    });
                }
            }

            // IP → connects to SUBDOMAIN (reverse DNS)
            if (node.type === "IP") {
                const hostname = (props.hostname as string) || (props.subdomain as string) || "";
                if (hostname) {
                    const subdomainId = `subdomain:${hostname}`;
                    if (nodesMap.has(subdomainId)) {
                        generatedEdges.push({
                            fromNode: subdomainId,
                            toNode: node.id,
                            relation: "RESOLVES_TO",
                        });
                    }
                }
            }

            // TECHNOLOGY → connects to HTTP_SERVICE
            if (node.type === "TECHNOLOGY") {
                const serviceUrl = (props.service_url as string) || (props.url as string) || "";
                if (serviceUrl) {
                    const serviceId = `http_service:${serviceUrl}`;
                    if (nodesMap.has(serviceId)) {
                        generatedEdges.push({
                            fromNode: serviceId,
                            toNode: node.id,
                            relation: "USES",
                        });
                    }
                }
            }

            // AGENT_RUN → connects to DOMAIN (workflow root)
            if (node.type === "AGENT_RUN") {
                // Connect agents to the domain root
                generatedEdges.push({
                    fromNode: domainNodeId,
                    toNode: node.id,
                    relation: "RUNS",
                });
            }

            // TOOL_CALL → connects to AGENT_RUN
            if (node.type === "TOOL_CALL") {
                const agentId = (props.agent_id as string) || (props.run_id as string) || "";
                // Try to find the agent that called this tool
                let foundAgent = false;
                nodesArray.forEach((agentNode) => {
                    if (agentNode.type === "AGENT_RUN") {
                        const agentRunId = agentNode.id;
                        // Check if IDs match or are related
                        if (agentId && (agentRunId.includes(agentId) || agentId.includes(agentRunId.split(":").pop() || ""))) {
                            generatedEdges.push({
                                fromNode: agentNode.id,
                                toNode: node.id,
                                relation: "INVOKES",
                            });
                            foundAgent = true;
                        }
                    }
                });

                // If no specific agent found, connect to domain
                if (!foundAgent) {
                    generatedEdges.push({
                        fromNode: domainNodeId,
                        toNode: node.id,
                        relation: "USES_TOOL",
                    });
                }
            }

            // DNS_RECORD → connects to SUBDOMAIN
            if (node.type === "DNS_RECORD") {
                const hostname = (props.hostname as string) || (props.name as string) || (props.subdomain as string) || "";
                if (hostname) {
                    const subdomainId = `subdomain:${hostname}`;
                    if (nodesMap.has(subdomainId)) {
                        generatedEdges.push({
                            fromNode: subdomainId,
                            toNode: node.id,
                            relation: "HAS_DNS",
                        });
                    } else {
                        // Connect to domain if subdomain not found
                        generatedEdges.push({
                            fromNode: domainNodeId,
                            toNode: node.id,
                            relation: "HAS_DNS",
                        });
                    }
                } else {
                    // Fallback: connect to domain
                    generatedEdges.push({
                        fromNode: domainNodeId,
                        toNode: node.id,
                        relation: "HAS_DNS",
                    });
                }
            }
        });

        return generatedEdges;
    }, [currentMission?.targetDomain]);

    // Convert store data to Cytoscape elements with auto-generated edges
    const elements = useMemo((): ElementDefinition[] => {
        const els: ElementDefinition[] = [];
        const targetDomain = currentMission?.targetDomain || "";

        // Add root domain node if we have subdomains
        const hasSubdomains = Array.from(nodes.values()).some(n => n.type === "SUBDOMAIN");
        if (hasSubdomains && targetDomain && visibleNodeTypes.includes("DOMAIN" as NodeType)) {
            els.push({
                data: {
                    id: `domain:${targetDomain}`,
                    label: targetDomain,
                    fullLabel: targetDomain,
                    type: "DOMAIN",
                    risk: 0,
                },
            });
        }

        // Add nodes
        nodes.forEach((node) => {
            if (!visibleNodeTypes.includes(node.type)) return;

            const props = node.properties as Record<string, unknown>;
            const label = (props.label as string) ||
                (props.url as string) ||
                (props.name as string) ||
                (props.domain as string) ||
                (props.path as string) ||
                (props.title as string) ||
                node.id.split(":").pop() ||
                node.id;

            els.push({
                data: {
                    id: node.id,
                    label: label.length > 25 ? label.substring(0, 25) + "..." : label,
                    fullLabel: label,
                    type: node.type,
                    risk: (props.risk_score as number) || 0,
                    severity: props.severity,
                    ...props,
                },
            });
        });

        // Generate logical edges automatically
        const logicalEdges = generateLogicalEdges(nodes);

        // Combine with existing edges from store
        const allEdges = [...edges, ...logicalEdges];

        // Deduplicate edges
        const edgeSet = new Set<string>();
        allEdges.forEach((edge) => {
            const fromNode = nodes.get(edge.fromNode);
            const toNode = nodes.get(edge.toNode);

            // Special handling for domain node
            const fromExists = fromNode || edge.fromNode.startsWith("domain:");
            const toExists = toNode;

            if (fromExists && toExists) {
                const fromVisible = fromNode ? visibleNodeTypes.includes(fromNode.type) : visibleNodeTypes.includes("DOMAIN" as NodeType);
                const toVisible = visibleNodeTypes.includes(toNode.type);

                if (fromVisible && toVisible) {
                    const edgeKey = `${edge.fromNode}::${edge.toNode}`;
                    if (!edgeSet.has(edgeKey)) {
                        edgeSet.add(edgeKey);
                        els.push({
                            data: {
                                id: `${edge.fromNode}::${edge.relation || "CONNECTS"}::${edge.toNode}`,
                                source: edge.fromNode,
                                target: edge.toNode,
                                label: edge.relation || "",
                            },
                        });
                    }
                }
            }
        });

        return els;
    }, [nodes, edges, visibleNodeTypes, currentMission?.targetDomain, generateLogicalEdges]);

    // Generate cytoscape stylesheet
    const getStylesheet = useCallback(() => {
        const styles: cytoscape.StylesheetStyle[] = [
            // Base node style
            {
                selector: "node",
                style: {
                    "background-color": "#64748b",
                    "background-opacity": 0.9,
                    label: "data(label)",
                    color: "#e2e8f0",
                    "font-size": 10,
                    "font-weight": "bold" as const,
                    "text-valign": "bottom",
                    "text-halign": "center",
                    "text-margin-y": 8,
                    "text-outline-color": "#0a0a0f",
                    "text-outline-width": 2,
                    width: 30,
                    height: 30,
                    "border-width": 2,
                    "border-color": "#94a3b8",
                    "border-opacity": 0.6,
                    "overlay-padding": 6,
                },
            },
            // Edge style - animated dashed lines
            {
                selector: "edge",
                style: {
                    width: 2,
                    "line-color": "#475569",
                    "line-style": "solid",
                    "target-arrow-color": "#475569",
                    "target-arrow-shape": "triangle",
                    "arrow-scale": 1,
                    "curve-style": "bezier",
                    opacity: 0.7,
                    label: "data(label)",
                    "font-size": 8,
                    color: "#64748b",
                    "text-rotation": "autorotate",
                    "text-margin-y": -8,
                    "text-background-color": "#0f172a",
                    "text-background-opacity": 0.9,
                    "text-background-padding": "3px",
                },
            },
            // Selected node
            {
                selector: "node:selected",
                style: {
                    "border-width": 4,
                    "border-color": "#00ffff",
                    "border-opacity": 1,
                    "background-opacity": 1,
                },
            },
            // Highlighted nodes and edges
            {
                selector: ".highlighted",
                style: {
                    "border-width": 3,
                    "border-color": "#00ffff",
                    "background-opacity": 1,
                },
            },
            {
                selector: "edge.highlighted",
                style: {
                    "line-color": "#00ffff",
                    "target-arrow-color": "#00ffff",
                    width: 3,
                    opacity: 1,
                },
            },
            // Flash animation for new nodes
            {
                selector: ".flash-new",
                style: {
                    "background-color": "#22c55e",
                    "border-width": 4,
                    "border-color": "#4ade80",
                },
            },
            // Report highlight
            {
                selector: ".report-highlight",
                style: {
                    "background-color": "#d946ef",
                    "border-width": 4,
                    "border-color": "#f0abfc",
                },
            },
        ];

        // Add type-specific styles
        Object.entries(nodeColors).forEach(([type, colors]) => {
            styles.push({
                selector: `node[type="${type}"]`,
                style: {
                    "background-color": colors.bg,
                    "border-color": colors.border,
                    width: nodeSizes[type] || 30,
                    height: nodeSizes[type] || 30,
                    shape: (nodeShapes[type] || "ellipse") as cytoscape.Css.NodeShape,
                },
            });

            // Edge colors based on source type
            styles.push({
                selector: `edge[source ^= "${type.toLowerCase()}"]`,
                style: {
                    "line-color": colors.bg,
                    "target-arrow-color": colors.bg,
                },
            });
        });

        // Risk-based node sizing for endpoints
        styles.push({
            selector: 'node[type="ENDPOINT"][risk > 50]',
            style: {
                width: 40,
                height: 40,
                "border-width": 3,
                "border-color": "#ef4444",
            },
        });

        styles.push({
            selector: 'node[type="VULNERABILITY"]',
            style: {
                "border-width": 3,
                "background-opacity": 0.9,
            },
        });

        return styles;
    }, []);

    // Get layout options based on type
    const getLayoutOptions = useCallback((type: LayoutType) => {
        const baseOptions = {
            animate: true,
            animationDuration: 500,
            fit: true,
            padding: 50,
        };

        switch (type) {
            case "hierarchical":
                return {
                    name: "breadthfirst",
                    ...baseOptions,
                    directed: true,
                    spacingFactor: 1.5,
                    avoidOverlap: true,
                    roots: `[type="DOMAIN"]`,
                    maximal: false,
                    grid: false,
                };
            case "cose":
                return {
                    name: "cose",
                    ...baseOptions,
                    nodeRepulsion: () => 8000,
                    idealEdgeLength: () => 100,
                    edgeElasticity: () => 100,
                    gravity: 0.25,
                    numIter: 1000,
                };
            case "circle":
                return {
                    name: "circle",
                    ...baseOptions,
                    avoidOverlap: true,
                    spacingFactor: 1.5,
                };
            case "grid":
                return {
                    name: "grid",
                    ...baseOptions,
                    avoidOverlap: true,
                    spacingFactor: 1.2,
                    condense: true,
                };
            default:
                return {
                    name: "cose",
                    ...baseOptions,
                };
        }
    }, []);

    // Initialize Cytoscape
    useEffect(() => {
        if (!containerRef.current) return;

        isMountedRef.current = true;

        const cy = cytoscape({
            container: containerRef.current,
            headless: false,
            elements: [],
            style: getStylesheet(),
            layout: { name: "preset" },
            minZoom: 0.1,
            maxZoom: 4,
            wheelSensitivity: 0.3,
        });

        cyRef.current = cy;

        // Handle node selection
        cy.on("tap", "node", (evt) => {
            if (!isMountedRef.current || cy.destroyed()) return;
            const node = evt.target;
            const nodeData = nodes.get(node.id()) ||
                (node.id().startsWith("domain:") ? {
                    id: node.id(),
                    type: "DOMAIN" as NodeType,
                    properties: { name: node.data("label") },
                } : null);

            if (nodeData) {
                setSelectedNode(nodeData);
                cy.elements().removeClass("highlighted");
                node.addClass("highlighted");
                node.connectedEdges().addClass("highlighted");
                node.neighborhood("node").addClass("highlighted");
            }
        });

        // Clear selection on background tap
        cy.on("tap", (evt) => {
            if (!isMountedRef.current || cy.destroyed()) return;
            if (evt.target === cy) {
                setSelectedNode(null);
                cy.elements().removeClass("highlighted");
            }
        });

        return () => {
            isMountedRef.current = false;
            if (layoutRef.current) {
                try { layoutRef.current.stop(); } catch { /* ignore */ }
                layoutRef.current = null;
            }
            if (cy && !cy.destroyed()) {
                try {
                    cy.stop(true, true);
                    cy.elements().stop(true, true);
                } catch { /* ignore */ }
                cy.removeAllListeners();
                cy.destroy();
            }
            cyRef.current = null;
        };
    }, []);

    // Update elements when data changes
    useEffect(() => {
        const cy = cyRef.current;
        if (!cy || cy.destroyed() || !isMountedRef.current) return;

        const currentIds = new Set(cy.nodes().map((n) => n.id()));
        const newNodeIds = new Set(elements.filter((e) => !e.data.source).map((e) => e.data.id as string));

        if (layoutRef.current) {
            try { layoutRef.current.stop(); } catch { /* ignore */ }
            layoutRef.current = null;
        }

        // Remove nodes that no longer exist
        cy.nodes().forEach((node) => {
            if (!newNodeIds.has(node.id())) {
                node.remove();
            }
        });

        // Add/update nodes
        elements.forEach((ele) => {
            if (cy.destroyed() || !isMountedRef.current) return;
            if (!ele.data.source && !currentIds.has(ele.data.id as string)) {
                const newNode = cy.add(ele);
                newNode.flashClass("flash-new", 1500);
            } else if (!ele.data.source) {
                const existingNode = cy.getElementById(ele.data.id as string);
                if (existingNode.length) {
                    existingNode.data(ele.data);
                }
            }
        });

        if (cy.destroyed() || !isMountedRef.current) return;

        // Update edges
        const currentEdgeIds = new Set(cy.edges().map((e) => e.id()));
        const newEdgeIds = new Set(elements.filter((e) => e.data.source).map((e) => e.data.id as string));

        cy.edges().forEach((edge) => {
            if (!newEdgeIds.has(edge.id())) edge.remove();
        });

        elements.forEach((ele) => {
            if (cy.destroyed() || !isMountedRef.current) return;
            if (ele.data.source && !currentEdgeIds.has(ele.data.id as string)) {
                cy.add(ele);
            }
        });

        // Run layout
        if (!cy.destroyed() && isMountedRef.current && cy.nodes().length > 0) {
            const layout = cy.layout(getLayoutOptions(layoutType) as cytoscape.LayoutOptions);
            layoutRef.current = layout;
            layout.run();
        }
    }, [elements, layoutType, getLayoutOptions]);

    // Resize handler
    useEffect(() => {
        const cy = cyRef.current;
        if (!cy || cy.destroyed() || !isMountedRef.current) return;

        const timer = setTimeout(() => {
            if (cy && !cy.destroyed() && isMountedRef.current) {
                cy.resize();
                cy.fit(undefined, 50);
            }
        }, 100);

        return () => clearTimeout(timer);
    }, [logPanelExpanded]);

    // Handlers
    const handleRefresh = async () => {
        if (!missionId) return;
        setIsRefreshing(true);
        await fetchGraph(missionId);
        setIsRefreshing(false);
    };

    const handleZoomIn = () => {
        const cy = cyRef.current;
        if (cy && !cy.destroyed()) cy.zoom(cy.zoom() * 1.3);
    };

    const handleZoomOut = () => {
        const cy = cyRef.current;
        if (cy && !cy.destroyed()) cy.zoom(cy.zoom() / 1.3);
    };

    const handleFit = () => {
        const cy = cyRef.current;
        if (cy && !cy.destroyed()) cy.fit(undefined, 50);
    };

    const handleRelayout = () => {
        const cy = cyRef.current;
        if (cy && !cy.destroyed() && cy.nodes().length > 0) {
            if (layoutRef.current) {
                try { layoutRef.current.stop(); } catch { /* ignore */ }
            }
            const layout = cy.layout(getLayoutOptions(layoutType) as cytoscape.LayoutOptions);
            layoutRef.current = layout;
            layout.run();
        }
    };

    const toggleNodeType = (type: NodeType) => {
        if (visibleNodeTypes.includes(type)) {
            setVisibleNodeTypes(visibleNodeTypes.filter((t) => t !== type));
        } else {
            setVisibleNodeTypes([...visibleNodeTypes, type]);
        }
    };

    const handleHighlightMentions = useCallback((mentions: string[]) => {
        setHighlightedMentions(mentions);
        const cy = cyRef.current;
        if (!cy || cy.destroyed()) return;

        cy.elements().removeClass("report-highlight");
        cy.nodes().forEach((node) => {
            const nodeData = node.data();
            const label = nodeData.fullLabel || nodeData.label || "";
            const id = nodeData.id || "";

            const isMatch = mentions.some((mention) => {
                const mentionLower = mention.toLowerCase();
                return label.toLowerCase().includes(mentionLower) || id.toLowerCase().includes(mentionLower);
            });

            if (isMatch) node.addClass("report-highlight");
        });
    }, []);

    const clearHighlights = useCallback(() => {
        setHighlightedMentions([]);
        const cy = cyRef.current;
        if (cy && !cy.destroyed()) cy.elements().removeClass("report-highlight");
    }, []);

    const isConnected = connectionStatus === "connected";
    const isActive = currentMission?.status === "running";
    const nodesArray = Array.from(nodes.values());

    // Node type stats
    const nodeStats = useMemo(() => {
        const stats: Record<string, number> = {};
        nodesArray.forEach((node) => {
            stats[node.type] = (stats[node.type] || 0) + 1;
        });
        return stats;
    }, [nodesArray]);

    const edgeCount = elements.filter(e => e.data.source).length;

    return (
        <div className="w-full h-full relative bg-[#0a0a0f] overflow-hidden">
            {/* Cyber grid background */}
            <div className="absolute inset-0 opacity-5" style={{
                backgroundImage: `
                    linear-gradient(rgba(0, 255, 255, 0.3) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(0, 255, 255, 0.3) 1px, transparent 1px)
                `,
                backgroundSize: '50px 50px'
            }} />
            <div className="absolute inset-0 bg-gradient-radial from-cyan-950/10 via-transparent to-purple-950/10" />

            {/* Graph container */}
            <div ref={containerRef} className="w-full h-full" />

            {/* Top Controls */}
            <div className="absolute top-4 right-4 flex items-center gap-2 flex-wrap justify-end">
                {/* Connection status */}
                <motion.div
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium backdrop-blur-sm ${
                        isConnected
                            ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                            : "bg-slate-800/80 text-slate-500 border border-slate-700"
                    }`}
                >
                    {isConnected ? <Wifi size={12} /> : <WifiOff size={12} />}
                    {isConnected ? "LIVE" : "OFFLINE"}
                </motion.div>

                {/* Layout selector */}
                <div className="flex items-center gap-1 bg-slate-800/80 backdrop-blur-sm rounded-lg border border-slate-700 p-1">
                    <button
                        onClick={() => setLayoutType("hierarchical")}
                        className={`p-1.5 rounded ${layoutType === "hierarchical" ? "bg-cyan-500/30 text-cyan-400" : "text-slate-500 hover:text-slate-300"}`}
                        title="Hierarchical Layout"
                    >
                        <GitBranch size={14} />
                    </button>
                    <button
                        onClick={() => setLayoutType("cose")}
                        className={`p-1.5 rounded ${layoutType === "cose" ? "bg-cyan-500/30 text-cyan-400" : "text-slate-500 hover:text-slate-300"}`}
                        title="Force Layout"
                    >
                        <Network size={14} />
                    </button>
                    <button
                        onClick={() => setLayoutType("circle")}
                        className={`p-1.5 rounded ${layoutType === "circle" ? "bg-cyan-500/30 text-cyan-400" : "text-slate-500 hover:text-slate-300"}`}
                        title="Circle Layout"
                    >
                        <Layers size={14} />
                    </button>
                </div>

                {/* Live toggle */}
                <button
                    onClick={() => setLiveMode(!liveMode)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors backdrop-blur-sm ${
                        liveMode
                            ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
                            : "bg-slate-800/80 text-slate-500 border border-slate-700"
                    }`}
                >
                    {liveMode ? <Pause size={12} /> : <Play size={12} />}
                </button>

                {/* Filter toggle */}
                <button
                    onClick={() => setShowFilters(!showFilters)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors backdrop-blur-sm ${
                        showFilters
                            ? "bg-purple-500/20 text-purple-400 border border-purple-500/30"
                            : "bg-slate-800/80 text-slate-500 border border-slate-700"
                    }`}
                >
                    <Filter size={12} />
                </button>

                {/* Refresh */}
                <button
                    onClick={handleRefresh}
                    disabled={isRefreshing || isLoading}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800/80 text-slate-400 border border-slate-700 hover:bg-slate-700/80 transition-colors backdrop-blur-sm disabled:opacity-50"
                >
                    <RefreshCw size={12} className={isRefreshing || isLoading ? "animate-spin" : ""} />
                </button>

                {/* Re-layout */}
                <button
                    onClick={handleRelayout}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800/80 text-slate-400 border border-slate-700 hover:bg-slate-700/80 transition-colors backdrop-blur-sm"
                    title="Re-layout Graph"
                >
                    <Maximize2 size={12} />
                </button>

                {/* AI Report */}
                <button
                    onClick={() => setReportDrawerOpen(true)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-gradient-to-r from-purple-500/20 to-cyan-500/20 text-purple-400 border border-purple-500/30 hover:from-purple-500/30 hover:to-cyan-500/30 transition-colors backdrop-blur-sm"
                >
                    <FileText size={12} />
                    AI REPORT
                </button>

                {highlightedMentions.length > 0 && (
                    <button
                        onClick={clearHighlights}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-fuchsia-500/20 text-fuchsia-400 border border-fuchsia-500/30 hover:bg-fuchsia-500/30 transition-colors backdrop-blur-sm"
                    >
                        <X size={12} />
                        {highlightedMentions.length}
                    </button>
                )}
            </div>

            {/* Zoom Controls */}
            <div className="absolute bottom-4 right-4 flex flex-col gap-1">
                <button onClick={handleZoomIn} className="p-2 rounded-lg bg-slate-800/80 text-slate-400 border border-slate-700 hover:bg-slate-700 transition-colors backdrop-blur-sm">
                    <ZoomIn size={16} />
                </button>
                <button onClick={handleZoomOut} className="p-2 rounded-lg bg-slate-800/80 text-slate-400 border border-slate-700 hover:bg-slate-700 transition-colors backdrop-blur-sm">
                    <ZoomOut size={16} />
                </button>
                <button onClick={handleFit} className="p-2 rounded-lg bg-slate-800/80 text-slate-400 border border-slate-700 hover:bg-slate-700 transition-colors backdrop-blur-sm">
                    <Maximize2 size={16} />
                </button>
            </div>

            {/* Stats Panel */}
            <motion.div
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                className="absolute top-4 left-4 bg-slate-900/90 backdrop-blur-md rounded-xl p-4 border border-cyan-500/20 shadow-lg shadow-cyan-500/5"
            >
                <div className="text-xs text-slate-500 mb-3 font-semibold uppercase tracking-wider flex items-center gap-2">
                    <Network size={14} className="text-cyan-400" />
                    Asset Graph
                </div>
                <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs">
                    <span className="text-slate-500">Nodes:</span>
                    <span className="text-cyan-400 font-mono font-bold">{nodesArray.length + (currentMission?.targetDomain ? 1 : 0)}</span>
                    <span className="text-slate-500">Edges:</span>
                    <span className="text-cyan-400 font-mono font-bold">{edgeCount}</span>
                    <span className="text-slate-500">Status:</span>
                    <span className={`font-mono font-bold ${isActive ? "text-emerald-400" : "text-slate-500"}`}>
                        {currentMission?.status?.toUpperCase() || "IDLE"}
                    </span>
                </div>
            </motion.div>

            {/* Filters Panel */}
            <AnimatePresence>
                {showFilters && (
                    <motion.div
                        initial={{ opacity: 0, y: -20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -20 }}
                        className="absolute top-16 right-4 bg-slate-900/95 backdrop-blur-md rounded-xl p-4 border border-slate-700 w-72 shadow-xl"
                    >
                        <div className="flex items-center justify-between mb-4">
                            <span className="text-xs text-slate-400 font-semibold uppercase tracking-wider">
                                Node Filters
                            </span>
                            <button onClick={() => setShowFilters(false)} className="text-slate-500 hover:text-white">
                                <X size={14} />
                            </button>
                        </div>
                        <div className="space-y-2">
                            {Object.entries(nodeColors).map(([type, colors]) => (
                                <label key={type} className="flex items-center gap-3 cursor-pointer group py-1">
                                    <input
                                        type="checkbox"
                                        checked={visibleNodeTypes.includes(type as NodeType)}
                                        onChange={() => toggleNodeType(type as NodeType)}
                                        className="w-4 h-4 rounded border-slate-600 bg-slate-800 text-cyan-500 focus:ring-cyan-500 focus:ring-offset-0"
                                    />
                                    <div className="w-4 h-4 rounded-full" style={{ backgroundColor: colors.bg }} />
                                    <span className="text-xs text-slate-400 group-hover:text-white flex-1">
                                        {nodeLabels[type]}
                                    </span>
                                    <span className="text-xs text-slate-600 font-mono bg-slate-800 px-2 py-0.5 rounded">
                                        {nodeStats[type] || 0}
                                    </span>
                                </label>
                            ))}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Legend */}
            <div className="absolute bottom-4 left-4 bg-slate-900/90 backdrop-blur-md rounded-xl p-4 border border-purple-500/20 shadow-lg shadow-purple-500/5 max-w-xs">
                <div className="text-xs text-slate-500 mb-3 font-semibold uppercase tracking-wider">
                    Node Types
                </div>
                <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                    {Object.entries(nodeColors).slice(0, 8).map(([type, colors]) => (
                        <div key={type} className="flex items-center gap-2 text-xs">
                            <div
                                className="w-3 h-3 rounded-full border-2"
                                style={{ backgroundColor: colors.bg, borderColor: colors.border }}
                            />
                            <span className="text-slate-400">{nodeLabels[type]}</span>
                        </div>
                    ))}
                </div>
            </div>

            {/* Selected Node Info - Enhanced Panel */}
            <AnimatePresence>
                {selectedNode && (
                    <motion.div
                        initial={{ opacity: 0, x: 20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: 20 }}
                        className="absolute top-4 right-[320px] bg-slate-900/95 backdrop-blur-md rounded-xl border border-slate-700 w-80 shadow-xl max-h-[calc(100%-32px)] overflow-hidden flex flex-col"
                    >
                        {/* Header */}
                        <div className="p-4 border-b border-slate-800 shrink-0">
                            <div className="flex items-center justify-between mb-2">
                                <div className="flex items-center gap-2">
                                    <div
                                        className="w-5 h-5 rounded-full border-2"
                                        style={{
                                            backgroundColor: nodeColors[selectedNode.type]?.bg || "#64748b",
                                            borderColor: nodeColors[selectedNode.type]?.border || "#94a3b8",
                                        }}
                                    />
                                    <span className="text-sm font-bold text-white">
                                        {nodeLabels[selectedNode.type] || selectedNode.type}
                                    </span>
                                </div>
                                <button onClick={() => setSelectedNode(null)} className="text-slate-500 hover:text-white p-1 rounded hover:bg-slate-800">
                                    <X size={16} />
                                </button>
                            </div>
                            <div className="text-xs text-cyan-400 font-mono break-all bg-slate-800/50 p-2 rounded">
                                {selectedNode.id.split(":").slice(1).join(":") || selectedNode.id}
                            </div>
                        </div>

                        {/* Content - Scrollable */}
                        <div className="flex-1 overflow-y-auto p-4">
                            {(() => {
                                const props = selectedNode.properties as Record<string, unknown>;

                                // Type-specific rendering
                                switch (selectedNode.type) {
                                    case "SUBDOMAIN":
                                        return (
                                            <div className="space-y-4">
                                                <div>
                                                    <div className="text-xs text-slate-500 uppercase mb-1">Name</div>
                                                    <div className="text-sm text-white font-mono">{props.name as string || props.subdomain as string}</div>
                                                </div>
                                                <div>
                                                    <div className="text-xs text-slate-500 uppercase mb-1">Source</div>
                                                    <span className="px-2 py-1 bg-cyan-500/20 text-cyan-400 rounded text-xs">{props.source as string}</span>
                                                </div>
                                            </div>
                                        );

                                    case "HTTP_SERVICE":
                                        return (
                                            <div className="space-y-4">
                                                <div>
                                                    <div className="text-xs text-slate-500 uppercase mb-1">URL</div>
                                                    <a href={props.url as string} target="_blank" rel="noopener noreferrer" className="text-sm text-cyan-400 hover:underline break-all">
                                                        {props.url as string}
                                                    </a>
                                                </div>
                                                {typeof props.status_code === "number" && (
                                                    <div>
                                                        <div className="text-xs text-slate-500 uppercase mb-1">Status Code</div>
                                                        <span className={`px-2 py-1 rounded text-xs font-bold ${
                                                            props.status_code >= 200 && props.status_code < 300 ? "bg-emerald-500/20 text-emerald-400" :
                                                            props.status_code >= 300 && props.status_code < 400 ? "bg-blue-500/20 text-blue-400" :
                                                            props.status_code >= 400 && props.status_code < 500 ? "bg-amber-500/20 text-amber-400" :
                                                            "bg-red-500/20 text-red-400"
                                                        }`}>
                                                            {props.status_code}
                                                        </span>
                                                    </div>
                                                )}
                                                {(props.technology !== undefined || props.technologies !== undefined) ? (
                                                    <div>
                                                        <div className="text-xs text-slate-500 uppercase mb-1">Technologies</div>
                                                        <div className="flex flex-wrap gap-1">
                                                            {(() => {
                                                                let techs: string[] = [];
                                                                const techValue = props.technology || props.technologies;
                                                                try {
                                                                    if (typeof techValue === "string") {
                                                                        techs = JSON.parse(techValue.replace(/'/g, '"'));
                                                                    } else if (Array.isArray(techValue)) {
                                                                        techs = techValue as string[];
                                                                    } else if (techValue) {
                                                                        techs = [String(techValue)];
                                                                    }
                                                                } catch {
                                                                    if (techValue) techs = [String(techValue)];
                                                                }
                                                                return techs.map((tech: string, idx: number) => (
                                                                    <span key={`${tech}-${idx}`} className="px-2 py-0.5 bg-slate-800 rounded text-xs text-slate-300">{tech}</span>
                                                                ));
                                                            })()}
                                                        </div>
                                                    </div>
                                                ) : null}
                                            </div>
                                        );

                                    case "ENDPOINT":
                                        return (
                                            <div className="space-y-4">
                                                <div>
                                                    <div className="text-xs text-slate-500 uppercase mb-1">Path</div>
                                                    <div className="text-sm text-white font-mono">{props.path as string}</div>
                                                </div>
                                                <div className="grid grid-cols-2 gap-4">
                                                    <div>
                                                        <div className="text-xs text-slate-500 uppercase mb-1">Method</div>
                                                        <span className="px-2 py-1 bg-slate-800 rounded text-xs font-bold text-slate-300">
                                                            {(props.method as string) || "GET"}
                                                        </span>
                                                    </div>
                                                    {typeof props.risk_score === "number" && props.risk_score > 0 && (
                                                        <div>
                                                            <div className="text-xs text-slate-500 uppercase mb-1">Risk Score</div>
                                                            <span className={`px-2 py-1 rounded text-xs font-bold ${
                                                                props.risk_score >= 80 ? "bg-red-500/20 text-red-400" :
                                                                props.risk_score >= 60 ? "bg-amber-500/20 text-amber-400" :
                                                                "bg-slate-500/20 text-slate-400"
                                                            }`}>
                                                                {props.risk_score}
                                                            </span>
                                                        </div>
                                                    )}
                                                </div>
                                                {typeof props.category === "string" && (
                                                    <div>
                                                        <div className="text-xs text-slate-500 uppercase mb-1">Category</div>
                                                        <span className="px-2 py-1 bg-purple-500/20 text-purple-400 rounded text-xs">{props.category}</span>
                                                    </div>
                                                )}
                                            </div>
                                        );

                                    case "HYPOTHESIS":
                                        return (
                                            <div className="space-y-4">
                                                <div>
                                                    <div className="text-xs text-slate-500 uppercase mb-1">Title</div>
                                                    <div className="text-sm text-white font-medium">{props.title as string}</div>
                                                </div>
                                                <div>
                                                    <div className="text-xs text-slate-500 uppercase mb-1">Attack Type</div>
                                                    <span className="px-2 py-1 bg-red-500/20 text-red-400 rounded text-xs font-bold">{props.attack_type as string}</span>
                                                </div>
                                                {typeof props.confidence === "number" && (
                                                    <div>
                                                        <div className="text-xs text-slate-500 uppercase mb-1">Confidence</div>
                                                        <div className="flex items-center gap-2">
                                                            <div className="flex-1 bg-slate-800 rounded-full h-2 overflow-hidden">
                                                                <div
                                                                    className={`h-full rounded-full ${
                                                                        props.confidence >= 0.7 ? "bg-red-500" :
                                                                        props.confidence >= 0.4 ? "bg-amber-500" : "bg-slate-500"
                                                                    }`}
                                                                    style={{ width: `${props.confidence * 100}%` }}
                                                                />
                                                            </div>
                                                            <span className="text-xs text-white font-bold">{(props.confidence * 100).toFixed(0)}%</span>
                                                        </div>
                                                    </div>
                                                )}
                                                {typeof props.target_id === "string" && (
                                                    <div>
                                                        <div className="text-xs text-slate-500 uppercase mb-1">Target</div>
                                                        <div className="text-xs text-slate-400 font-mono break-all bg-slate-800/50 p-2 rounded">{props.target_id}</div>
                                                    </div>
                                                )}
                                            </div>
                                        );

                                    case "VULNERABILITY":
                                        return (
                                            <div className="space-y-4">
                                                <div>
                                                    <div className="text-xs text-slate-500 uppercase mb-1">Title</div>
                                                    <div className="text-sm text-white font-medium">{props.title as string}</div>
                                                </div>
                                                {/* Deep Verification Status Badge */}
                                                {typeof props.status === "string" && (
                                                    <div>
                                                        <div className="text-xs text-slate-500 uppercase mb-1">Verification Status</div>
                                                        <span className={`px-2 py-1 rounded text-xs font-bold ${
                                                            props.status === "CONFIRMED" ? "bg-red-600/30 text-red-400 border border-red-500/50" :
                                                            props.status === "LIKELY" ? "bg-amber-500/20 text-amber-400 border border-amber-500/50" :
                                                            props.status === "THEORETICAL" ? "bg-purple-500/20 text-purple-400 border border-purple-500/50" :
                                                            props.status === "FALSE_POSITIVE" ? "bg-slate-500/20 text-slate-400 border border-slate-500/50" :
                                                            props.status === "MITIGATED" ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/50" :
                                                            "bg-slate-500/20 text-slate-400"
                                                        }`}>
                                                            {props.status === "CONFIRMED" ? "✓ CONFIRMED" :
                                                             props.status === "LIKELY" ? "⚠ LIKELY" :
                                                             props.status === "THEORETICAL" ? "? THEORETICAL" :
                                                             props.status === "FALSE_POSITIVE" ? "✗ FALSE POSITIVE" :
                                                             props.status === "MITIGATED" ? "⬡ MITIGATED" :
                                                             props.status}
                                                        </span>
                                                    </div>
                                                )}
                                                {typeof props.attack_type === "string" && (
                                                    <div>
                                                        <div className="text-xs text-slate-500 uppercase mb-1">Attack Type</div>
                                                        <span className="px-2 py-1 bg-red-500/20 text-red-400 rounded text-xs font-bold">{props.attack_type}</span>
                                                    </div>
                                                )}
                                                {typeof props.severity === "string" && (
                                                    <div>
                                                        <div className="text-xs text-slate-500 uppercase mb-1">Severity</div>
                                                        <span className={`px-2 py-1 rounded text-xs font-bold ${
                                                            props.severity === "CRITICAL" ? "bg-red-600/30 text-red-400" :
                                                            props.severity === "HIGH" ? "bg-red-500/20 text-red-400" :
                                                            props.severity === "MEDIUM" ? "bg-amber-500/20 text-amber-400" :
                                                            "bg-slate-500/20 text-slate-400"
                                                        }`}>
                                                            {props.severity}
                                                        </span>
                                                    </div>
                                                )}
                                                {typeof props.risk_score === "number" && (
                                                    <div>
                                                        <div className="text-xs text-slate-500 uppercase mb-1">Risk Score</div>
                                                        <div className="flex items-center gap-2">
                                                            <div className="flex-1 bg-slate-800 rounded-full h-2 overflow-hidden">
                                                                <div
                                                                    className={`h-full rounded-full ${
                                                                        props.risk_score >= 80 ? "bg-red-500" :
                                                                        props.risk_score >= 60 ? "bg-amber-500" :
                                                                        props.risk_score >= 40 ? "bg-yellow-500" : "bg-slate-500"
                                                                    }`}
                                                                    style={{ width: `${props.risk_score}%` }}
                                                                />
                                                            </div>
                                                            <span className="text-xs text-white font-bold">{props.risk_score}</span>
                                                        </div>
                                                    </div>
                                                )}
                                                {typeof props.cve_id === "string" && (
                                                    <div>
                                                        <div className="text-xs text-slate-500 uppercase mb-1">CVE</div>
                                                        <span className="text-sm text-cyan-400 font-mono">{props.cve_id}</span>
                                                    </div>
                                                )}
                                                {/* Deep Verification Evidence Array */}
                                                {Array.isArray(props.evidence) && props.evidence.length > 0 && (
                                                    <div>
                                                        <div className="text-xs text-slate-500 uppercase mb-2">Evidence ({props.evidence.length})</div>
                                                        <div className="space-y-2 max-h-48 overflow-y-auto">
                                                            {(props.evidence as Array<{kind?: string; summary?: string; hash?: string}>).map((ev, idx) => (
                                                                <div key={idx} className="bg-slate-800/50 p-2 rounded border border-slate-700/50">
                                                                    <div className="flex items-center gap-2 mb-1">
                                                                        <span className="px-1.5 py-0.5 bg-cyan-500/20 text-cyan-400 rounded text-[10px] font-medium">
                                                                            {ev.kind || "evidence"}
                                                                        </span>
                                                                        {ev.hash && (
                                                                            <span className="text-[10px] text-slate-600 font-mono">
                                                                                #{ev.hash.slice(0, 8)}
                                                                            </span>
                                                                        )}
                                                                    </div>
                                                                    <div className="text-xs text-slate-300">{ev.summary}</div>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}
                                                {/* Legacy string evidence */}
                                                {typeof props.evidence === "string" && (
                                                    <div>
                                                        <div className="text-xs text-slate-500 uppercase mb-1">Evidence</div>
                                                        <div className="text-xs text-slate-300 bg-slate-800/50 p-2 rounded font-mono">{props.evidence}</div>
                                                    </div>
                                                )}
                                                {/* Tool Call ID for idempotency tracking */}
                                                {typeof props.tool_call_id === "string" && (
                                                    <div>
                                                        <div className="text-xs text-slate-500 uppercase mb-1">Tool Call ID</div>
                                                        <div className="text-[10px] text-slate-500 font-mono bg-slate-800/50 p-1.5 rounded break-all">{props.tool_call_id}</div>
                                                    </div>
                                                )}
                                                {props.verified === true && (
                                                    <div className="flex items-center gap-2 text-xs text-emerald-400 bg-emerald-500/10 p-2 rounded border border-emerald-500/20">
                                                        <span>✓</span>
                                                        <span>Verified by Deep Verification</span>
                                                    </div>
                                                )}
                                            </div>
                                        );

                                    default:
                                        // Generic property display
                                        return (
                                            <div className="space-y-2">
                                                {Object.entries(props)
                                                    .filter(([key]) => !["mission_id", "id"].includes(key))
                                                    .slice(0, 12)
                                                    .map(([key, value]) => (
                                                        <div key={key}>
                                                            <div className="text-xs text-slate-500 uppercase mb-0.5">{key.replace(/_/g, " ")}</div>
                                                            <div className="text-sm text-slate-300 break-all">
                                                                {typeof value === "object" ? JSON.stringify(value) : String(value)}
                                                            </div>
                                                        </div>
                                                    ))
                                                }
                                            </div>
                                        );
                                }
                            })()}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Loading Overlay */}
            <AnimatePresence>
                {(isLoading || isRefreshing) && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center z-50"
                    >
                        <div className="flex flex-col items-center gap-4">
                            <Loader2 className="w-12 h-12 text-cyan-400 animate-spin" />
                            <span className="text-sm text-slate-400 uppercase tracking-wider">
                                Loading Graph...
                            </span>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Empty State */}
            {!isLoading && nodesArray.length === 0 && (
                <div className="absolute inset-0 flex items-center justify-center">
                    <div className="text-center">
                        <Network className="w-16 h-16 text-slate-700 mx-auto mb-4" />
                        <div className="text-slate-500 text-sm mb-2">No assets discovered yet</div>
                        <div className="text-slate-600 text-xs">
                            Start a mission to begin reconnaissance
                        </div>
                    </div>
                </div>
            )}

            {/* AI Report Drawer */}
            <AIReportDrawer
                isOpen={reportDrawerOpen}
                onClose={() => setReportDrawerOpen(false)}
                onHighlightMentions={handleHighlightMentions}
            />
        </div>
    );
}
