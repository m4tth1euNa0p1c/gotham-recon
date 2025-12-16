"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { BarChart3, TrendingUp, Clock, Target, Shield, Bug, Cpu, Activity, Loader2 } from "lucide-react";
import Sidebar from "@/components/dashboard/Sidebar";
import { graphqlFetch, Mission } from "@/lib/api";

interface AnalyticsData {
  totalMissions: number;
  completedMissions: number;
  failedMissions: number;
  totalSubdomains: number;
  totalServices: number;
  totalEndpoints: number;
  totalVulnerabilities: number;
  totalHypotheses: number;
  avgDuration: number;
  topTechnologies: { name: string; count: number }[];
  missionsByStatus: { status: string; count: number }[];
}

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAnalytics = async () => {
      try {
        // Fetch all missions
        const missionsData = await graphqlFetch<{ missions: { items: Mission[], total: number } }>(
          `query GetMissions {
            missions(limit: 100) {
              items {
                id
                status
                createdAt
              }
              total
            }
          }`
        );

        const missions = missionsData.missions.items;
        const completed = missions.filter(m => m.status === "completed");
        const failed = missions.filter(m => m.status === "failed");

        // Aggregate stats from all missions
        let totalSubdomains = 0;
        let totalServices = 0;
        let totalEndpoints = 0;
        let totalVulnerabilities = 0;
        let totalHypotheses = 0;

        for (const mission of completed.slice(0, 20)) {
          try {
            const statsData = await graphqlFetch<{ graphStats: { nodesByType: Record<string, number> } }>(
              `query GetStats($missionId: String!) {
                graphStats(missionId: $missionId) {
                  nodesByType
                }
              }`,
              { missionId: mission.id }
            );

            const nodesByType = statsData?.graphStats?.nodesByType || {};
            totalSubdomains += nodesByType.SUBDOMAIN || 0;
            totalServices += nodesByType.HTTP_SERVICE || 0;
            totalEndpoints += nodesByType.ENDPOINT || 0;
            totalVulnerabilities += nodesByType.VULNERABILITY || 0;
            totalHypotheses += nodesByType.HYPOTHESIS || 0;
          } catch {
            // Continue on error
          }
        }

        // Calculate mission status distribution
        const statusCounts = new Map<string, number>();
        missions.forEach(m => {
          statusCounts.set(m.status, (statusCounts.get(m.status) || 0) + 1);
        });

        setData({
          totalMissions: missionsData.missions.total,
          completedMissions: completed.length,
          failedMissions: failed.length,
          totalSubdomains,
          totalServices,
          totalEndpoints,
          totalVulnerabilities,
          totalHypotheses,
          avgDuration: 0, // Would need duration data
          topTechnologies: [], // Would need aggregation
          missionsByStatus: Array.from(statusCounts.entries()).map(([status, count]) => ({ status, count })),
        });
      } catch (e) {
        console.error("Failed to fetch analytics:", e);
      } finally {
        setLoading(false);
      }
    };

    fetchAnalytics();
  }, []);

  const StatCard = ({ icon: Icon, label, value, color, subtext }: { icon: typeof Activity; label: string; value: number | string; color: string; subtext?: string }) => (
    <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6">
      <div className="flex items-center gap-3 mb-3">
        <div className={`p-2 rounded-lg ${color}`}>
          <Icon size={20} />
        </div>
        <span className="text-slate-400 text-sm">{label}</span>
      </div>
      <p className="text-3xl font-bold text-white">{value}</p>
      {subtext && <p className="text-xs text-slate-500 mt-1">{subtext}</p>}
    </div>
  );

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
            <BarChart3 className="text-cyan-500" />
            Analytics
          </h1>
          <p className="text-slate-400">
            Overview of your reconnaissance activities and discovered assets.
          </p>
        </motion.div>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 text-cyan-500 animate-spin" />
          </div>
        ) : data ? (
          <>
            {/* Mission Stats */}
            <h2 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
              <Target className="text-cyan-400" size={20} />
              Mission Statistics
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
              <StatCard
                icon={Shield}
                label="Total Missions"
                value={data.totalMissions}
                color="bg-cyan-500/20 text-cyan-400"
              />
              <StatCard
                icon={Activity}
                label="Completed"
                value={data.completedMissions}
                color="bg-emerald-500/20 text-emerald-400"
                subtext={`${((data.completedMissions / data.totalMissions) * 100).toFixed(0)}% success rate`}
              />
              <StatCard
                icon={Bug}
                label="Failed"
                value={data.failedMissions}
                color="bg-red-500/20 text-red-400"
              />
              <StatCard
                icon={Clock}
                label="Avg Duration"
                value="N/A"
                color="bg-purple-500/20 text-purple-400"
              />
            </div>

            {/* Asset Stats */}
            <h2 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
              <Cpu className="text-cyan-400" size={20} />
              Discovered Assets (Aggregated)
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
              <StatCard
                icon={Target}
                label="Subdomains"
                value={data.totalSubdomains}
                color="bg-cyan-500/20 text-cyan-400"
              />
              <StatCard
                icon={Shield}
                label="HTTP Services"
                value={data.totalServices}
                color="bg-emerald-500/20 text-emerald-400"
              />
              <StatCard
                icon={Activity}
                label="Endpoints"
                value={data.totalEndpoints}
                color="bg-amber-500/20 text-amber-400"
              />
              <StatCard
                icon={TrendingUp}
                label="Hypotheses"
                value={data.totalHypotheses}
                color="bg-purple-500/20 text-purple-400"
              />
              <StatCard
                icon={Bug}
                label="Vulnerabilities"
                value={data.totalVulnerabilities}
                color="bg-red-500/20 text-red-400"
              />
            </div>

            {/* Mission Status Distribution */}
            <h2 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
              <BarChart3 className="text-cyan-400" size={20} />
              Mission Status Distribution
            </h2>
            <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6">
              <div className="flex gap-4">
                {data.missionsByStatus.map((item) => {
                  const total = data.totalMissions;
                  const percentage = total > 0 ? (item.count / total) * 100 : 0;
                  const colors: Record<string, string> = {
                    completed: "bg-emerald-500",
                    running: "bg-amber-500",
                    failed: "bg-red-500",
                    cancelled: "bg-slate-500",
                    pending: "bg-blue-500",
                  };

                  return (
                    <div key={item.status} className="flex-1">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-slate-400 text-sm capitalize">{item.status}</span>
                        <span className="text-white font-bold">{item.count}</span>
                      </div>
                      <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${colors[item.status] || "bg-slate-500"} rounded-full`}
                          style={{ width: `${percentage}%` }}
                        />
                      </div>
                      <p className="text-xs text-slate-500 mt-1">{percentage.toFixed(1)}%</p>
                    </div>
                  );
                })}
              </div>
            </div>
          </>
        ) : (
          <div className="text-center py-20 text-slate-500">
            <BarChart3 size={48} className="mx-auto mb-4 opacity-50" />
            <p>No analytics data available</p>
          </div>
        )}
      </div>
    </div>
  );
}
