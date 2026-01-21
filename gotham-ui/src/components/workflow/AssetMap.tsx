"use client";

/**
 * AssetMap
 * Real-time canvas visualization of discovered assets (subdomains, endpoints, vulnerabilities).
 * Assets appear with animations as they are discovered via live events.
 * NO MOCK DATA - populated via live WebSocket events only.
 *
 * Design: Icon per type, risk score coloring, collapsible categories
 */

import React, { useMemo, useRef, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Globe,
  Server,
  Link2,
  AlertTriangle,
  Shield,
  Database,
  Key,
  FileCode,
  Crosshair,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { useGraphStore } from "@/stores";
import { NodeType } from "@/services/types";

// Asset icon mapping - matching mock design
const ASSET_ICONS: Record<string, React.ElementType> = {
  VULNERABILITY: AlertTriangle,
  HYPOTHESIS: Crosshair,
  ATTACK_PATH: Shield,
  ENDPOINT: Link2,
  PARAMETER: Key,
  HTTP_SERVICE: Server,
  SUBDOMAIN: Globe,
  JS_FILE: FileCode,
};

// Asset color mapping
const ASSET_COLORS: Record<string, string> = {
  VULNERABILITY: "text-red-400",
  HYPOTHESIS: "text-orange-400",
  ATTACK_PATH: "text-rose-400",
  ENDPOINT: "text-amber-400",
  PARAMETER: "text-purple-400",
  HTTP_SERVICE: "text-emerald-400",
  SUBDOMAIN: "text-cyan-400",
  JS_FILE: "text-yellow-400",
};

// Asset background colors
const ASSET_BG_COLORS: Record<string, string> = {
  VULNERABILITY: "bg-red-500/10 border-red-500/30",
  HYPOTHESIS: "bg-orange-500/10 border-orange-500/30",
  ATTACK_PATH: "bg-rose-500/10 border-rose-500/30",
  ENDPOINT: "bg-amber-500/10 border-amber-500/30",
  PARAMETER: "bg-purple-500/10 border-purple-500/30",
  HTTP_SERVICE: "bg-emerald-500/10 border-emerald-500/30",
  SUBDOMAIN: "bg-cyan-500/10 border-cyan-500/30",
  JS_FILE: "bg-yellow-500/10 border-yellow-500/30",
};

// Default icon for unknown types
const DEFAULT_ICON = Database;
const DEFAULT_COLOR = "text-slate-400";
const DEFAULT_BG = "bg-slate-500/10 border-slate-500/30";

// Asset category labels
const ASSET_LABELS: Record<string, string> = {
  VULNERABILITY: "Vulnerabilities",
  HYPOTHESIS: "Hypotheses",
  ATTACK_PATH: "Attack Paths",
  ENDPOINT: "Endpoints",
  PARAMETER: "Parameters",
  HTTP_SERVICE: "Services",
  SUBDOMAIN: "Subdomains",
  JS_FILE: "JS Files",
};

// Sort priority (vulnerabilities and hypotheses first)
const ASSET_PRIORITY: Record<string, number> = {
  VULNERABILITY: 0,
  HYPOTHESIS: 1,
  ATTACK_PATH: 2,
  ENDPOINT: 3,
  PARAMETER: 4,
  HTTP_SERVICE: 5,
  SUBDOMAIN: 6,
  JS_FILE: 7,
};

// Asset node animation variants
const assetVariants = {
  hidden: { opacity: 0, scale: 0.8, y: 10 },
  visible: {
    opacity: 1,
    scale: 1,
    y: 0,
    transition: { type: "spring" as const, stiffness: 400, damping: 25 },
  },
  exit: {
    opacity: 0,
    scale: 0.8,
    transition: { duration: 0.15 },
  },
};

interface AssetNodeProps {
  id: string;
  type: string;
  name: string;
  riskScore?: number;
  isNew?: boolean;
  onClick?: () => void;
}

function AssetNode({ id, type, name, riskScore, isNew, onClick }: AssetNodeProps) {
  const Icon = ASSET_ICONS[type] || DEFAULT_ICON;
  const color = ASSET_COLORS[type] || DEFAULT_COLOR;

  // Risk level badge
  const getRiskBadge = () => {
    if (riskScore === undefined || riskScore <= 0) return null;
    const riskClass =
      riskScore >= 80
        ? "bg-red-500/30 text-red-300 border-red-500/50"
        : riskScore >= 60
        ? "bg-orange-500/30 text-orange-300 border-orange-500/50"
        : riskScore >= 40
        ? "bg-yellow-500/30 text-yellow-300 border-yellow-500/50"
        : "bg-slate-500/30 text-slate-300 border-slate-500/50";
    return (
      <span className={`text-[9px] font-mono px-1 py-0.5 rounded border ${riskClass}`}>
        {riskScore}
      </span>
    );
  };

  return (
    <motion.div
      variants={assetVariants}
      initial="hidden"
      animate="visible"
      exit="exit"
      onClick={onClick}
      className="relative flex items-center gap-2 px-2 py-1.5 rounded border bg-slate-800/30 border-slate-700/50 cursor-pointer hover:bg-slate-800/50 transition-colors"
    >
      {/* New indicator */}
      {isNew && (
        <motion.div
          className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 bg-cyan-400 rounded-full"
          animate={{ scale: [1, 1.3, 1], opacity: [1, 0.7, 1] }}
          transition={{ duration: 1, repeat: 3 }}
        />
      )}

      <Icon size={12} className={color} />
      <span className="text-[10px] text-slate-300 truncate flex-1 max-w-[100px]">{name}</span>
      {getRiskBadge()}
    </motion.div>
  );
}

interface AssetCategoryProps {
  type: string;
  assets: Array<{ id: string; name: string; riskScore?: number; createdAt?: string }>;
  isExpanded: boolean;
  onToggle: () => void;
  onAssetClick?: (assetId: string) => void;
  recentIds: Set<string>;
}

function AssetCategory({
  type,
  assets,
  isExpanded,
  onToggle,
  onAssetClick,
  recentIds,
}: AssetCategoryProps) {
  const Icon = ASSET_ICONS[type] || DEFAULT_ICON;
  const color = ASSET_COLORS[type] || DEFAULT_COLOR;
  const bgColor = ASSET_BG_COLORS[type] || DEFAULT_BG;
  const label = ASSET_LABELS[type] || type;

  // Sort by risk score descending
  const sortedAssets = useMemo(() => {
    return [...assets].sort((a, b) => {
      const riskA = a.riskScore || 0;
      const riskB = b.riskScore || 0;
      return riskB - riskA;
    });
  }, [assets]);

  const displayedAssets = isExpanded ? sortedAssets : sortedAssets.slice(0, 4);
  const hasMore = sortedAssets.length > 4;

  return (
    <div className="space-y-1.5">
      {/* Category Header */}
      <button
        onClick={onToggle}
        className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded border transition-colors ${bgColor} hover:bg-opacity-50`}
      >
        <div className="flex items-center gap-2">
          <Icon size={12} className={color} />
          <span className="text-[10px] font-medium text-white">{label}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[9px] font-mono text-slate-400">{assets.length}</span>
          {hasMore && (
            isExpanded ? (
              <ChevronUp size={10} className="text-slate-400" />
            ) : (
              <ChevronDown size={10} className="text-slate-400" />
            )
          )}
        </div>
      </button>

      {/* Assets Grid */}
      <div className="grid grid-cols-2 gap-1 pl-2">
        <AnimatePresence mode="popLayout">
          {displayedAssets.map((asset) => (
            <AssetNode
              key={asset.id}
              id={asset.id}
              type={type}
              name={asset.name}
              riskScore={asset.riskScore}
              isNew={recentIds.has(asset.id)}
              onClick={() => onAssetClick?.(asset.id)}
            />
          ))}
        </AnimatePresence>
      </div>

      {/* Show more */}
      {hasMore && !isExpanded && (
        <button
          onClick={onToggle}
          className="text-[9px] text-slate-500 hover:text-slate-300 pl-2 transition-colors"
        >
          +{sortedAssets.length - 4} more
        </button>
      )}
    </div>
  );
}

interface AssetMapProps {
  className?: string;
  missionId?: string;
  onAssetSelect?: (assetId: string) => void;
}

export default function AssetMap({ className = "", missionId, onAssetSelect }: AssetMapProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());
  const [recentIds, setRecentIds] = useState<Set<string>>(new Set());

  // Get nodes from graph store
  const nodesMap = useGraphStore((state) => state.nodes);

  // Group assets by type
  const assetsByType = useMemo(() => {
    const groups = new Map<string, Array<{ id: string; name: string; riskScore?: number; createdAt?: string }>>();

    Array.from(nodesMap.values()).forEach((node) => {
      // Skip workflow nodes
      if (["AGENT_RUN", "TOOL_CALL", "LLM_REASONING"].includes(node.type)) {
        return;
      }

      const type = node.type;
      if (!groups.has(type)) {
        groups.set(type, []);
      }

      const nodeId = node.id || '';
      groups.get(type)!.push({
        id: nodeId,
        name: node.properties?.name as string || node.properties?.subdomain as string || node.properties?.path as string || nodeId.substring(0, 16) || 'Unknown',
        riskScore: node.properties?.risk_score as number,
        createdAt: node.properties?.created_at as string,
      });
    });

    return groups;
  }, [nodesMap]);

  // Track new assets (added in last 3 seconds)
  useEffect(() => {
    const nodeIds = Array.from(nodesMap.keys());
    const newRecentIds = new Set(nodeIds.slice(-10)); // Mark last 10 as recent
    setRecentIds(newRecentIds);

    // Clear "new" status after 3 seconds
    const timer = setTimeout(() => {
      setRecentIds(new Set());
    }, 3000);

    return () => clearTimeout(timer);
  }, [nodesMap.size]);

  // Toggle category expansion
  const toggleCategory = (type: string) => {
    setExpandedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(type)) {
        next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  };

  // Calculate totals
  const totalAssets = useMemo(() => {
    let total = 0;
    assetsByType.forEach((assets) => {
      total += assets.length;
    });
    return total;
  }, [assetsByType]);

  // Sort types by priority
  const sortedTypes = useMemo(() => {
    return Array.from(assetsByType.entries()).sort(([typeA], [typeB]) => {
      const prioA = ASSET_PRIORITY[typeA] ?? 10;
      const prioB = ASSET_PRIORITY[typeB] ?? 10;
      return prioA - prioB;
    });
  }, [assetsByType]);

  return (
    <div className={`flex flex-col bg-slate-900/30 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800/50 shrink-0">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-md bg-purple-500/10 border border-purple-500/20">
            <Database size={12} className="text-purple-400" />
          </div>
          <span className="text-xs font-semibold text-white">Asset Map</span>
        </div>
        <span className="text-[10px] text-slate-500 font-mono px-2 py-0.5 rounded bg-slate-800/50 border border-slate-700/50">
          {totalAssets} assets
        </span>
      </div>

      {/* Asset Categories */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-3 space-y-3 scrollbar-thin scrollbar-track-slate-800/50 scrollbar-thumb-slate-700"
      >
        {sortedTypes.length === 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex flex-col items-center justify-center h-[120px] text-slate-500"
          >
            <div className="p-4 rounded-lg bg-slate-800/30 border border-slate-800/50">
              <Database size={24} className="mb-2 text-slate-600 mx-auto" />
              <p className="text-[10px] text-slate-400 text-center">No assets discovered yet</p>
              <p className="text-[9px] text-slate-600 mt-1 text-center">Assets will appear as they are found</p>
            </div>
          </motion.div>
        ) : (
          sortedTypes.map(([type, assets]) => (
            <AssetCategory
              key={type}
              type={type}
              assets={assets}
              isExpanded={expandedCategories.has(type)}
              onToggle={() => toggleCategory(type)}
              onAssetClick={onAssetSelect}
              recentIds={recentIds}
            />
          ))
        )}
      </div>

      {/* Summary Footer */}
      {totalAssets > 0 && (
        <div className="px-4 py-2 border-t border-slate-800/50 flex items-center gap-3 text-[10px] shrink-0">
          {assetsByType.has("VULNERABILITY") && (
            <span className="flex items-center gap-1 text-red-400">
              <AlertTriangle size={10} />
              {assetsByType.get("VULNERABILITY")!.length}
            </span>
          )}
          {assetsByType.has("ENDPOINT") && (
            <span className="flex items-center gap-1 text-amber-400">
              <Link2 size={10} />
              {assetsByType.get("ENDPOINT")!.length}
            </span>
          )}
          {assetsByType.has("SUBDOMAIN") && (
            <span className="flex items-center gap-1 text-cyan-400">
              <Globe size={10} />
              {assetsByType.get("SUBDOMAIN")!.length}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
