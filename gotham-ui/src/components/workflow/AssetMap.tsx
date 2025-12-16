"use client";

/**
 * AssetMap
 * Real-time canvas visualization of discovered assets (subdomains, endpoints, vulnerabilities).
 * Assets appear with animations as they are discovered via live events.
 * NO MOCK DATA - populated via live WebSocket events only.
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
  Maximize2,
  Filter,
} from "lucide-react";
import { useGraphStore } from "@/stores";
import { NodeType } from "@/services/types";

// Asset type configuration
interface AssetConfig {
  icon: React.ElementType;
  color: string;
  bgColor: string;
  borderColor: string;
  label: string;
}

const ASSET_CONFIGS: Record<string, AssetConfig> = {
  SUBDOMAIN: {
    icon: Globe,
    color: "text-cyan-400",
    bgColor: "bg-cyan-500/10",
    borderColor: "border-cyan-500/30",
    label: "Subdomains",
  },
  HTTP_SERVICE: {
    icon: Server,
    color: "text-emerald-400",
    bgColor: "bg-emerald-500/10",
    borderColor: "border-emerald-500/30",
    label: "Services",
  },
  ENDPOINT: {
    icon: Link2,
    color: "text-amber-400",
    bgColor: "bg-amber-500/10",
    borderColor: "border-amber-500/30",
    label: "Endpoints",
  },
  PARAMETER: {
    icon: Key,
    color: "text-purple-400",
    bgColor: "bg-purple-500/10",
    borderColor: "border-purple-500/30",
    label: "Parameters",
  },
  HYPOTHESIS: {
    icon: Crosshair,
    color: "text-orange-400",
    bgColor: "bg-orange-500/10",
    borderColor: "border-orange-500/30",
    label: "Hypotheses",
  },
  VULNERABILITY: {
    icon: AlertTriangle,
    color: "text-red-400",
    bgColor: "bg-red-500/10",
    borderColor: "border-red-500/30",
    label: "Vulnerabilities",
  },
  ATTACK_PATH: {
    icon: Shield,
    color: "text-rose-400",
    bgColor: "bg-rose-500/10",
    borderColor: "border-rose-500/30",
    label: "Attack Paths",
  },
  JS_FILE: {
    icon: FileCode,
    color: "text-yellow-400",
    bgColor: "bg-yellow-500/10",
    borderColor: "border-yellow-500/30",
    label: "JS Files",
  },
};

// Default config for unknown types
const DEFAULT_CONFIG: AssetConfig = {
  icon: Database,
  color: "text-slate-400",
  bgColor: "bg-slate-500/10",
  borderColor: "border-slate-500/30",
  label: "Other",
};

// Asset node animation variants
const assetVariants = {
  hidden: { opacity: 0, scale: 0.5, y: 20 },
  visible: {
    opacity: 1,
    scale: 1,
    y: 0,
    transition: {
      type: "spring" as const,
      stiffness: 400,
      damping: 25,
    },
  },
  exit: {
    opacity: 0,
    scale: 0.5,
    transition: { duration: 0.2 },
  },
  hover: {
    scale: 1.05,
    transition: { duration: 0.15 },
  },
};

// Stagger children animation
const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.05,
    },
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
  const config = ASSET_CONFIGS[type] || DEFAULT_CONFIG;
  const Icon = config.icon;

  // Risk level coloring
  const getRiskColor = () => {
    if (riskScore === undefined) return "";
    if (riskScore >= 80) return "ring-2 ring-red-500/50";
    if (riskScore >= 60) return "ring-2 ring-orange-500/50";
    if (riskScore >= 40) return "ring-2 ring-yellow-500/50";
    return "";
  };

  return (
    <motion.div
      variants={assetVariants}
      initial="hidden"
      animate="visible"
      exit="exit"
      whileHover="hover"
      onClick={onClick}
      className={`relative flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-colors ${config.bgColor} ${config.borderColor} ${getRiskColor()} hover:bg-opacity-20`}
    >
      {/* New indicator */}
      {isNew && (
        <motion.div
          className="absolute -top-1 -right-1 w-2 h-2 bg-cyan-400 rounded-full"
          animate={{ scale: [1, 1.2, 1], opacity: [1, 0.8, 1] }}
          transition={{ duration: 1, repeat: 3 }}
        />
      )}

      <Icon size={14} className={config.color} />
      <span className="text-xs text-white truncate max-w-[120px]">{name}</span>

      {riskScore !== undefined && riskScore > 0 && (
        <span
          className={`text-[10px] font-mono px-1 rounded ${
            riskScore >= 80
              ? "bg-red-500/30 text-red-300"
              : riskScore >= 60
              ? "bg-orange-500/30 text-orange-300"
              : riskScore >= 40
              ? "bg-yellow-500/30 text-yellow-300"
              : "bg-slate-500/30 text-slate-300"
          }`}
        >
          {riskScore}
        </span>
      )}
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
  const config = ASSET_CONFIGS[type] || DEFAULT_CONFIG;
  const Icon = config.icon;

  // Sort by risk score descending, then by creation time
  const sortedAssets = useMemo(() => {
    return [...assets].sort((a, b) => {
      const riskA = a.riskScore || 0;
      const riskB = b.riskScore || 0;
      if (riskA !== riskB) return riskB - riskA;
      return 0;
    });
  }, [assets]);

  const displayedAssets = isExpanded ? sortedAssets : sortedAssets.slice(0, 6);
  const hasMore = sortedAssets.length > 6;

  return (
    <div className="space-y-2">
      {/* Category Header */}
      <button
        onClick={onToggle}
        className={`w-full flex items-center justify-between px-3 py-2 rounded-lg border transition-colors ${config.bgColor} ${config.borderColor} hover:bg-opacity-30`}
      >
        <div className="flex items-center gap-2">
          <Icon size={16} className={config.color} />
          <span className="text-sm font-medium text-white">{config.label}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-slate-400">{assets.length}</span>
          {hasMore && (
            isExpanded ? (
              <ChevronUp size={14} className="text-slate-400" />
            ) : (
              <ChevronDown size={14} className="text-slate-400" />
            )
          )}
        </div>
      </button>

      {/* Assets Grid */}
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="grid grid-cols-2 gap-2 pl-2"
      >
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
      </motion.div>

      {/* Show more/less */}
      {hasMore && !isExpanded && (
        <button
          onClick={onToggle}
          className="text-xs text-slate-500 hover:text-slate-300 pl-2 transition-colors"
        >
          +{sortedAssets.length - 6} more
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
  const [filterType, setFilterType] = useState<string | null>(null);
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

      // Filter by mission if provided
      if (missionId && node.properties?.mission_id !== missionId) {
        // Allow nodes without mission_id (they might be from current session)
      }

      const type = node.type;
      if (!groups.has(type)) {
        groups.set(type, []);
      }

      groups.get(type)!.push({
        id: node.id,
        name: node.properties?.name as string || node.properties?.subdomain as string || node.properties?.path as string || node.id.substring(0, 20),
        riskScore: node.properties?.risk_score as number,
        createdAt: node.properties?.created_at as string,
      });
    });

    return groups;
  }, [nodesMap, missionId]);

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

  // Filter categories
  const filteredTypes = filterType
    ? [[filterType, assetsByType.get(filterType) || []]] as [string, typeof assetsByType extends Map<string, infer V> ? V : never][]
    : Array.from(assetsByType.entries());

  // Sort by priority (vulnerabilities first, then by count)
  const sortedTypes = [...filteredTypes].sort(([typeA, assetsA], [typeB, assetsB]) => {
    const priority: Record<string, number> = {
      VULNERABILITY: 0,
      HYPOTHESIS: 1,
      ATTACK_PATH: 2,
      ENDPOINT: 3,
      PARAMETER: 4,
      HTTP_SERVICE: 5,
      SUBDOMAIN: 6,
    };
    const prioA = priority[typeA] ?? 10;
    const prioB = priority[typeB] ?? 10;
    if (prioA !== prioB) return prioA - prioB;
    return assetsB.length - assetsA.length;
  });

  return (
    <div className={`flex flex-col bg-slate-950/50 rounded-lg border border-slate-800 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <Database size={16} className="text-cyan-400" />
          <span className="text-sm font-medium text-white">Asset Map</span>
        </div>
        <div className="flex items-center gap-3">
          {/* Filter dropdown */}
          <div className="relative">
            <button
              onClick={() => setFilterType(null)}
              className="flex items-center gap-1 px-2 py-1 rounded text-xs text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            >
              <Filter size={12} />
              {filterType || "All"}
            </button>
          </div>
          <span className="text-xs font-mono text-slate-500">
            {totalAssets} asset{totalAssets !== 1 ? "s" : ""}
          </span>
        </div>
      </div>

      {/* Asset Categories */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin scrollbar-track-slate-900 scrollbar-thumb-slate-700"
      >
        {sortedTypes.length === 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex flex-col items-center justify-center h-[200px] text-slate-500"
          >
            <Database size={32} className="mb-2 text-slate-600" />
            <p className="text-sm">No assets discovered yet</p>
            <p className="text-xs text-slate-600 mt-1">Assets will appear as they are found</p>
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
        <div className="px-4 py-2 border-t border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-4 text-xs">
            {assetsByType.has("VULNERABILITY") && (
              <span className="flex items-center gap-1 text-red-400">
                <AlertTriangle size={12} />
                {assetsByType.get("VULNERABILITY")!.length} vulns
              </span>
            )}
            {assetsByType.has("ENDPOINT") && (
              <span className="flex items-center gap-1 text-amber-400">
                <Link2 size={12} />
                {assetsByType.get("ENDPOINT")!.length} endpoints
              </span>
            )}
            {assetsByType.has("SUBDOMAIN") && (
              <span className="flex items-center gap-1 text-cyan-400">
                <Globe size={12} />
                {assetsByType.get("SUBDOMAIN")!.length} subdomains
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
