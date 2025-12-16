"use client";

/**
 * AIReportDrawer
 * Displays AI-generated mission reports with tabs for Planning, Endpoint Intel, and Raw CrewAI output.
 * Includes copy and download functionality.
 */

import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
    X,
    Copy,
    Download,
    FileText,
    Target,
    Code,
    CheckCircle2,
    Sparkles,
    AlertTriangle,
    Link2,
    ChevronRight,
} from "lucide-react";
import { useMissionStore } from "@/stores";

interface AIReportDrawerProps {
    isOpen: boolean;
    onClose: () => void;
    onHighlightMentions?: (mentions: string[]) => void;
}

type TabId = "planning" | "endpoints" | "raw";

const TABS: { id: TabId; label: string; icon: typeof FileText }[] = [
    { id: "planning", label: "Planning", icon: Target },
    { id: "endpoints", label: "Endpoint Intel", icon: Link2 },
    { id: "raw", label: "Raw CrewAI", icon: Code },
];

export default function AIReportDrawer({ isOpen, onClose, onHighlightMentions }: AIReportDrawerProps) {
    const [activeTab, setActiveTab] = useState<TabId>("planning");
    const [copied, setCopied] = useState(false);

    // Mission state
    const currentMission = useMissionStore((state) => state.currentMission);

    // Extract CrewAI metrics from mission progress
    const crewaiMetrics = useMemo(() => {
        const progress = currentMission?.progress as any;
        return progress?.current_metrics?.crewai || null;
    }, [currentMission]);

    // Parse planning data
    const planningData = useMemo(() => {
        if (!crewaiMetrics) return null;

        // Try to extract planning information from various CrewAI outputs
        const plannerOutput = crewaiMetrics.planner_output || crewaiMetrics.attack_paths || null;
        const phases = crewaiMetrics.phases || [];
        const recommendations = crewaiMetrics.recommendations || [];

        return {
            plannerOutput,
            phases,
            recommendations,
            attackPaths: crewaiMetrics.attack_paths || [],
            highValueTargets: crewaiMetrics.high_value_targets || [],
        };
    }, [crewaiMetrics]);

    // Parse endpoint intel
    const endpointIntel = useMemo(() => {
        if (!crewaiMetrics) return null;

        return {
            endpoints: crewaiMetrics.endpoints || [],
            categories: crewaiMetrics.endpoint_categories || {},
            riskScores: crewaiMetrics.risk_scores || {},
            hypotheses: crewaiMetrics.hypotheses || [],
        };
    }, [crewaiMetrics]);

    // Get raw output string
    const rawOutput = useMemo(() => {
        if (!crewaiMetrics) return "No CrewAI output available.";
        return JSON.stringify(crewaiMetrics, null, 2);
    }, [crewaiMetrics]);

    // Extract mentions (URLs, subdomains) for highlighting
    const extractMentions = useMemo(() => {
        if (!crewaiMetrics) return [];

        const mentions: string[] = [];
        const raw = JSON.stringify(crewaiMetrics);

        // Extract URLs
        const urlRegex = /https?:\/\/[^\s"'<>]+/g;
        const urls = raw.match(urlRegex) || [];
        mentions.push(...urls);

        // Extract subdomains (simple pattern)
        const subdomainRegex = /[a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z]{2,}/g;
        const subdomains = raw.match(subdomainRegex) || [];
        mentions.push(...subdomains);

        return [...new Set(mentions)];
    }, [crewaiMetrics]);

    // Copy to clipboard
    const handleCopy = async () => {
        let content = "";
        switch (activeTab) {
            case "planning":
                content = planningData ? JSON.stringify(planningData, null, 2) : "";
                break;
            case "endpoints":
                content = endpointIntel ? JSON.stringify(endpointIntel, null, 2) : "";
                break;
            case "raw":
                content = rawOutput;
                break;
        }

        try {
            await navigator.clipboard.writeText(content);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch (err) {
            console.error("Failed to copy:", err);
        }
    };

    // Download as markdown
    const handleDownload = () => {
        let content = "";
        let filename = "";

        switch (activeTab) {
            case "planning":
                filename = `${currentMission?.targetDomain || "mission"}_planning.md`;
                content = `# Planning Report\n\n## Target: ${currentMission?.targetDomain}\n\n`;
                if (planningData?.attackPaths?.length) {
                    content += `## Attack Paths\n\n`;
                    planningData.attackPaths.forEach((path: any, i: number) => {
                        content += `### Path ${i + 1}\n${JSON.stringify(path, null, 2)}\n\n`;
                    });
                }
                if (planningData?.recommendations?.length) {
                    content += `## Recommendations\n\n`;
                    planningData.recommendations.forEach((rec: string) => {
                        content += `- ${rec}\n`;
                    });
                }
                break;
            case "endpoints":
                filename = `${currentMission?.targetDomain || "mission"}_endpoints.md`;
                content = `# Endpoint Intelligence\n\n## Target: ${currentMission?.targetDomain}\n\n`;
                if (endpointIntel?.hypotheses?.length) {
                    content += `## Hypotheses\n\n`;
                    endpointIntel.hypotheses.forEach((h: any, i: number) => {
                        content += `### ${i + 1}. ${h.title || "Hypothesis"}\n${h.description || JSON.stringify(h)}\n\n`;
                    });
                }
                break;
            case "raw":
                filename = `${currentMission?.targetDomain || "mission"}_crewai_raw.json`;
                content = rawOutput;
                break;
        }

        const blob = new Blob([content], { type: "text/plain" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    // Highlight mentions handler
    const handleHighlightMentions = () => {
        if (onHighlightMentions && extractMentions.length > 0) {
            onHighlightMentions(extractMentions);
        }
    };

    return (
        <AnimatePresence>
            {isOpen && (
                <>
                    {/* Backdrop */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 bg-black/50 z-40"
                        onClick={onClose}
                    />

                    {/* Drawer */}
                    <motion.div
                        initial={{ x: "100%" }}
                        animate={{ x: 0 }}
                        exit={{ x: "100%" }}
                        transition={{ type: "spring", damping: 30, stiffness: 300 }}
                        className="fixed right-0 top-0 h-full w-[480px] bg-[#0d0d12] border-l border-[#1a1a25] z-50 flex flex-col"
                    >
                        {/* Header */}
                        <div className="flex items-center justify-between px-4 py-3 border-b border-[#1a1a25]">
                            <div className="flex items-center gap-3">
                                <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-gradient-to-br from-purple-500/20 to-cyan-500/20 border border-purple-500/30">
                                    <Sparkles size={16} className="text-purple-400" />
                                </div>
                                <div>
                                    <h3 className="text-sm font-bold text-white">AI Report</h3>
                                    <p className="text-xs text-[#4a4a5a]">
                                        {currentMission?.targetDomain || "No mission selected"}
                                    </p>
                                </div>
                            </div>
                            <button
                                onClick={onClose}
                                className="p-2 rounded-lg hover:bg-[#1a1a25] transition-colors"
                            >
                                <X size={16} className="text-[#4a4a5a]" />
                            </button>
                        </div>

                        {/* Tabs */}
                        <div className="flex border-b border-[#1a1a25]">
                            {TABS.map((tab) => {
                                const Icon = tab.icon;
                                return (
                                    <button
                                        key={tab.id}
                                        onClick={() => setActiveTab(tab.id)}
                                        className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 text-xs font-medium uppercase tracking-wider transition-colors relative ${
                                            activeTab === tab.id
                                                ? "text-[#00ffff]"
                                                : "text-[#4a4a5a] hover:text-[#8a8a9a]"
                                        }`}
                                    >
                                        <Icon size={12} />
                                        {tab.label}
                                        {activeTab === tab.id && (
                                            <motion.div
                                                layoutId="activeReportTab"
                                                className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#00ffff]"
                                            />
                                        )}
                                    </button>
                                );
                            })}
                        </div>

                        {/* Actions Bar */}
                        <div className="flex items-center justify-between px-4 py-2 border-b border-[#1a1a25] bg-[#0a0a0f]">
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={handleCopy}
                                    className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium bg-[#1a1a25] text-[#4a4a5a] hover:bg-[#2a2a3a] hover:text-white transition-colors"
                                >
                                    {copied ? (
                                        <CheckCircle2 size={10} className="text-[#00ff41]" />
                                    ) : (
                                        <Copy size={10} />
                                    )}
                                    {copied ? "Copied!" : "Copy"}
                                </button>
                                <button
                                    onClick={handleDownload}
                                    className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium bg-[#1a1a25] text-[#4a4a5a] hover:bg-[#2a2a3a] hover:text-white transition-colors"
                                >
                                    <Download size={10} />
                                    Download
                                </button>
                            </div>

                            {onHighlightMentions && extractMentions.length > 0 && (
                                <button
                                    onClick={handleHighlightMentions}
                                    className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium bg-[#bf00ff]/20 text-[#bf00ff] hover:bg-[#bf00ff]/30 transition-colors"
                                >
                                    <Target size={10} />
                                    Highlight ({extractMentions.length})
                                </button>
                            )}
                        </div>

                        {/* Content */}
                        <div className="flex-1 overflow-y-auto p-4">
                            {!crewaiMetrics ? (
                                <div className="flex flex-col items-center justify-center h-full text-center">
                                    <FileText size={48} className="text-[#2a2a3a] mb-4" />
                                    <h4 className="text-sm font-medium text-[#4a4a5a] mb-2">
                                        No Report Available
                                    </h4>
                                    <p className="text-xs text-[#3a3a4a] max-w-xs">
                                        Run a mission to generate AI-powered reconnaissance reports.
                                    </p>
                                </div>
                            ) : (
                                <>
                                    {/* Planning Tab */}
                                    {activeTab === "planning" && planningData && (
                                        <div className="space-y-4">
                                            {/* Attack Paths */}
                                            {planningData.attackPaths?.length > 0 && (
                                                <div>
                                                    <h4 className="text-xs font-bold text-white uppercase tracking-wider mb-3 flex items-center gap-2">
                                                        <AlertTriangle size={12} className="text-red-400" />
                                                        Attack Paths
                                                    </h4>
                                                    <div className="space-y-2">
                                                        {planningData.attackPaths.map((path: any, i: number) => (
                                                            <div
                                                                key={i}
                                                                className="bg-[#1a1a25] rounded-lg p-3 border border-red-500/20"
                                                            >
                                                                <div className="text-xs text-[#8a8a9a]">
                                                                    {typeof path === "string"
                                                                        ? path
                                                                        : JSON.stringify(path, null, 2)}
                                                                </div>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}

                                            {/* High Value Targets */}
                                            {planningData.highValueTargets?.length > 0 && (
                                                <div>
                                                    <h4 className="text-xs font-bold text-white uppercase tracking-wider mb-3 flex items-center gap-2">
                                                        <Target size={12} className="text-amber-400" />
                                                        High Value Targets
                                                    </h4>
                                                    <div className="space-y-2">
                                                        {planningData.highValueTargets.map((target: any, i: number) => (
                                                            <div
                                                                key={i}
                                                                className="bg-[#1a1a25] rounded-lg p-3 border border-amber-500/20"
                                                            >
                                                                <div className="text-xs text-[#00ffff] font-mono mb-1">
                                                                    {target.url || target.path || target}
                                                                </div>
                                                                {target.reason && (
                                                                    <div className="text-xs text-[#4a4a5a]">
                                                                        {target.reason}
                                                                    </div>
                                                                )}
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}

                                            {/* Raw Planner Output */}
                                            {planningData.plannerOutput && (
                                                <div>
                                                    <h4 className="text-xs font-bold text-white uppercase tracking-wider mb-3">
                                                        Planner Output
                                                    </h4>
                                                    <pre className="bg-[#1a1a25] rounded-lg p-3 text-xs text-[#8a8a9a] overflow-x-auto whitespace-pre-wrap">
                                                        {typeof planningData.plannerOutput === "string"
                                                            ? planningData.plannerOutput
                                                            : JSON.stringify(planningData.plannerOutput, null, 2)}
                                                    </pre>
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {/* Endpoints Tab */}
                                    {activeTab === "endpoints" && endpointIntel && (
                                        <div className="space-y-4">
                                            {/* Hypotheses */}
                                            {endpointIntel.hypotheses?.length > 0 && (
                                                <div>
                                                    <h4 className="text-xs font-bold text-white uppercase tracking-wider mb-3 flex items-center gap-2">
                                                        <Sparkles size={12} className="text-purple-400" />
                                                        Security Hypotheses
                                                    </h4>
                                                    <div className="space-y-2">
                                                        {endpointIntel.hypotheses.map((h: any, i: number) => (
                                                            <div
                                                                key={i}
                                                                className="bg-[#1a1a25] rounded-lg p-3 border border-purple-500/20"
                                                            >
                                                                <div className="text-xs font-medium text-white mb-1">
                                                                    {h.title || `Hypothesis ${i + 1}`}
                                                                </div>
                                                                <div className="text-xs text-[#4a4a5a]">
                                                                    {h.description || JSON.stringify(h)}
                                                                </div>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}

                                            {/* Categories */}
                                            {Object.keys(endpointIntel.categories || {}).length > 0 && (
                                                <div>
                                                    <h4 className="text-xs font-bold text-white uppercase tracking-wider mb-3">
                                                        Endpoint Categories
                                                    </h4>
                                                    <div className="grid grid-cols-2 gap-2">
                                                        {Object.entries(endpointIntel.categories).map(([category, count]) => (
                                                            <div
                                                                key={category}
                                                                className="bg-[#1a1a25] rounded-lg p-2 flex items-center justify-between"
                                                            >
                                                                <span className="text-xs text-[#8a8a9a] uppercase">
                                                                    {category}
                                                                </span>
                                                                <span className="text-xs font-bold text-[#00ffff] font-mono">
                                                                    {String(count)}
                                                                </span>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {/* Raw Tab */}
                                    {activeTab === "raw" && (
                                        <pre className="bg-[#1a1a25] rounded-lg p-4 text-xs text-[#8a8a9a] overflow-x-auto whitespace-pre-wrap font-mono">
                                            {rawOutput}
                                        </pre>
                                    )}
                                </>
                            )}
                        </div>
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    );
}
