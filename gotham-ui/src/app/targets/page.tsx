"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Target, Plus, Trash2, Globe, Clock, CheckCircle, AlertTriangle, Loader2 } from "lucide-react";
import Sidebar from "@/components/dashboard/Sidebar";
import { graphqlFetch, Mission } from "@/lib/api";

interface TargetDomain {
  domain: string;
  lastScanned: string | null;
  missionsCount: number;
  status: "idle" | "scanning" | "completed" | "failed";
}

export default function TargetsPage() {
  const [targets, setTargets] = useState<TargetDomain[]>([]);
  const [loading, setLoading] = useState(true);
  const [newDomain, setNewDomain] = useState("");

  useEffect(() => {
    const fetchTargets = async () => {
      try {
        const data = await graphqlFetch<{ missions: { items: Mission[] } }>(
          `query GetMissions {
            missions(limit: 100) {
              items {
                id
                targetDomain
                status
                createdAt
              }
            }
          }`
        );

        // Group by domain
        const domainMap = new Map<string, TargetDomain>();
        data.missions.items.forEach((m) => {
          const existing = domainMap.get(m.targetDomain);
          if (existing) {
            existing.missionsCount++;
            if (!existing.lastScanned || m.createdAt > existing.lastScanned) {
              existing.lastScanned = m.createdAt;
              existing.status = m.status === "running" ? "scanning" : m.status === "completed" ? "completed" : "failed";
            }
          } else {
            domainMap.set(m.targetDomain, {
              domain: m.targetDomain,
              lastScanned: m.createdAt,
              missionsCount: 1,
              status: m.status === "running" ? "scanning" : m.status === "completed" ? "completed" : "failed",
            });
          }
        });

        setTargets(Array.from(domainMap.values()));
      } catch (e) {
        console.error("Failed to fetch targets:", e);
      } finally {
        setLoading(false);
      }
    };

    fetchTargets();
  }, []);

  const handleAddTarget = () => {
    if (!newDomain.trim()) return;
    // In a real app, this would call an API
    setTargets([
      ...targets,
      {
        domain: newDomain.trim(),
        lastScanned: null,
        missionsCount: 0,
        status: "idle",
      },
    ]);
    setNewDomain("");
  };

  const getStatusConfig = (status: TargetDomain["status"]) => {
    switch (status) {
      case "scanning":
        return { icon: Loader2, color: "text-amber-400", bg: "bg-amber-500/20", label: "Scanning", animate: true };
      case "completed":
        return { icon: CheckCircle, color: "text-emerald-400", bg: "bg-emerald-500/20", label: "Completed", animate: false };
      case "failed":
        return { icon: AlertTriangle, color: "text-red-400", bg: "bg-red-500/20", label: "Failed", animate: false };
      default:
        return { icon: Clock, color: "text-slate-400", bg: "bg-slate-500/20", label: "Idle", animate: false };
    }
  };

  return (
    <div className="flex h-screen bg-[#0a0a0f]">
      <Sidebar />
      <div className="flex-1 overflow-y-auto p-8">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <h1 className="text-2xl font-bold text-white flex items-center gap-3 mb-2">
            <Target className="text-cyan-500" />
            Target Domains
          </h1>
          <p className="text-slate-400">
            Manage your reconnaissance targets and track their scan status.
          </p>
        </motion.div>

        {/* Add Target */}
        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 mb-6">
          <div className="flex gap-4">
            <div className="flex-1 relative">
              <Globe className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={18} />
              <input
                type="text"
                placeholder="Enter domain (e.g., example.com)"
                value={newDomain}
                onChange={(e) => setNewDomain(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAddTarget()}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg pl-10 pr-4 py-3 text-white placeholder:text-slate-500 focus:border-cyan-500 focus:outline-none"
              />
            </div>
            <button
              onClick={handleAddTarget}
              className="px-6 py-3 bg-cyan-500 hover:bg-cyan-600 text-black font-bold rounded-lg flex items-center gap-2 transition-colors"
            >
              <Plus size={18} />
              Add Target
            </button>
          </div>
        </div>

        {/* Targets List */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 text-cyan-500 animate-spin" />
          </div>
        ) : targets.length === 0 ? (
          <div className="text-center py-20 text-slate-500">
            <Target size={48} className="mx-auto mb-4 opacity-50" />
            <p>No targets yet</p>
            <p className="text-sm mt-2">Add a domain to start reconnaissance</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {targets.map((target, idx) => {
              const statusConfig = getStatusConfig(target.status);
              const StatusIcon = statusConfig.icon;

              return (
                <motion.div
                  key={target.domain}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.05 }}
                  className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 hover:border-slate-700 transition-colors"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <Globe className="text-cyan-400" size={18} />
                      <span className="text-white font-mono font-medium">{target.domain}</span>
                    </div>
                    <button className="text-slate-500 hover:text-red-400 transition-colors">
                      <Trash2 size={16} />
                    </button>
                  </div>

                  <div className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <StatusIcon size={14} className={`${statusConfig.color} ${statusConfig.animate ? "animate-spin" : ""}`} />
                      <span className={statusConfig.color}>{statusConfig.label}</span>
                    </div>
                    <span className="text-slate-500">
                      {target.missionsCount} mission{target.missionsCount !== 1 ? "s" : ""}
                    </span>
                  </div>

                  {target.lastScanned && (
                    <div className="mt-3 pt-3 border-t border-slate-800 text-xs text-slate-500">
                      Last scanned: {new Date(target.lastScanned).toLocaleDateString()}
                    </div>
                  )}
                </motion.div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
