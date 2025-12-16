"use client";

import { useParams } from "next/navigation";
import { useEffect, useState, useMemo } from "react";
import { motion } from "framer-motion";
import {
  Bug,
  AlertTriangle,
  Shield,
  ExternalLink,
  ChevronRight,
  Loader2,
  Target,
  Lightbulb,
  CheckCircle,
  XCircle,
  Clock,
  Filter,
} from "lucide-react";
import Sidebar from "@/components/dashboard/Sidebar";
import { graphqlFetch, Mission } from "@/lib/api";
import Link from "next/link";

interface VulnerabilityNode {
  id: string;
  type: string;
  properties: {
    title?: string;
    severity?: string;
    cve_id?: string;
    description?: string;
    target_id?: string;
    evidence?: string;
    status?: string;
    cvss_score?: number;
  };
}

interface HypothesisNode {
  id: string;
  type: string;
  properties: {
    title?: string;
    attack_type?: string;
    target_id?: string;
    confidence?: number;
    rationale?: string;
    status?: string;
  };
}

type TabId = "vulnerabilities" | "hypotheses";

export default function VulnerabilitiesPage() {
  const params = useParams();
  const missionId = params.id as string;
  const [mission, setMission] = useState<Mission | null>(null);
  const [vulnerabilities, setVulnerabilities] = useState<VulnerabilityNode[]>([]);
  const [hypotheses, setHypotheses] = useState<HypothesisNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabId>("vulnerabilities");
  const [severityFilter, setSeverityFilter] = useState<string>("all");

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch mission
        const missionData = await graphqlFetch<{ mission: Mission }>(
          `query GetMission($id: String!) {
            mission(id: $id) {
              id
              targetDomain
              status
            }
          }`,
          { id: missionId }
        );
        setMission(missionData.mission);

        // Fetch vulnerabilities
        const vulnData = await graphqlFetch<{ nodes: VulnerabilityNode[] }>(
          `query GetVulnerabilities($missionId: String!) {
            nodes(missionId: $missionId, types: [VULNERABILITY], limit: 100) {
              id
              type
              properties
            }
          }`,
          { missionId }
        );
        setVulnerabilities(vulnData.nodes || []);

        // Fetch hypotheses
        const hypoData = await graphqlFetch<{ nodes: HypothesisNode[] }>(
          `query GetHypotheses($missionId: String!) {
            nodes(missionId: $missionId, types: [HYPOTHESIS], limit: 100) {
              id
              type
              properties
            }
          }`,
          { missionId }
        );
        setHypotheses(hypoData.nodes || []);
      } catch (e) {
        console.error("Failed to fetch data:", e);
      } finally {
        setLoading(false);
      }
    };

    if (missionId) {
      fetchData();
    }
  }, [missionId]);

  const filteredVulnerabilities = useMemo(() => {
    if (severityFilter === "all") return vulnerabilities;
    return vulnerabilities.filter(
      (v) => v.properties.severity?.toLowerCase() === severityFilter
    );
  }, [vulnerabilities, severityFilter]);

  const getSeverityConfig = (severity?: string) => {
    switch (severity?.toLowerCase()) {
      case "critical":
        return { color: "text-red-500", bg: "bg-red-500/20", border: "border-red-500/30" };
      case "high":
        return { color: "text-orange-500", bg: "bg-orange-500/20", border: "border-orange-500/30" };
      case "medium":
        return { color: "text-amber-500", bg: "bg-amber-500/20", border: "border-amber-500/30" };
      case "low":
        return { color: "text-blue-500", bg: "bg-blue-500/20", border: "border-blue-500/30" };
      default:
        return { color: "text-slate-400", bg: "bg-slate-500/20", border: "border-slate-500/30" };
    }
  };

  const getConfidenceColor = (confidence?: number) => {
    if (!confidence) return "text-slate-400";
    if (confidence >= 0.8) return "text-red-400";
    if (confidence >= 0.6) return "text-amber-400";
    if (confidence >= 0.4) return "text-yellow-400";
    return "text-slate-400";
  };

  if (loading) {
    return (
      <div className="flex h-screen bg-slate-950">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center">
          <Loader2 className="w-8 h-8 text-cyan-500 animate-spin" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-slate-950">
      <Sidebar />
      <div className="flex-1 overflow-y-auto p-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <Bug className="text-red-500" size={28} />
            <h1 className="text-2xl font-bold text-white">Security Findings</h1>
          </div>
          {mission && (
            <p className="text-slate-400">
              Vulnerabilities and hypotheses for <span className="text-cyan-400 font-mono">{mission.targetDomain}</span>
            </p>
          )}
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-red-500/20 rounded-lg">
                <Bug className="text-red-400" size={20} />
              </div>
              <div>
                <p className="text-2xl font-bold text-white">{vulnerabilities.length}</p>
                <p className="text-xs text-slate-500">Vulnerabilities</p>
              </div>
            </div>
          </div>
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-amber-500/20 rounded-lg">
                <Lightbulb className="text-amber-400" size={20} />
              </div>
              <div>
                <p className="text-2xl font-bold text-white">{hypotheses.length}</p>
                <p className="text-xs text-slate-500">Hypotheses</p>
              </div>
            </div>
          </div>
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-red-500/20 rounded-lg">
                <AlertTriangle className="text-red-400" size={20} />
              </div>
              <div>
                <p className="text-2xl font-bold text-white">
                  {vulnerabilities.filter(v => ["critical", "high"].includes(v.properties.severity?.toLowerCase() || "")).length}
                </p>
                <p className="text-xs text-slate-500">Critical/High</p>
              </div>
            </div>
          </div>
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-emerald-500/20 rounded-lg">
                <CheckCircle className="text-emerald-400" size={20} />
              </div>
              <div>
                <p className="text-2xl font-bold text-white">
                  {hypotheses.filter(h => (h.properties.confidence || 0) >= 0.7).length}
                </p>
                <p className="text-xs text-slate-500">High Confidence</p>
              </div>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-4 mb-6 border-b border-slate-800 pb-2">
          <button
            onClick={() => setActiveTab("vulnerabilities")}
            className={`flex items-center gap-2 px-4 py-2 rounded-t-lg transition-colors ${
              activeTab === "vulnerabilities"
                ? "bg-slate-800 text-red-400 border-b-2 border-red-400"
                : "text-slate-400 hover:text-white hover:bg-slate-800/50"
            }`}
          >
            <Bug size={16} />
            Vulnerabilities ({vulnerabilities.length})
          </button>
          <button
            onClick={() => setActiveTab("hypotheses")}
            className={`flex items-center gap-2 px-4 py-2 rounded-t-lg transition-colors ${
              activeTab === "hypotheses"
                ? "bg-slate-800 text-amber-400 border-b-2 border-amber-400"
                : "text-slate-400 hover:text-white hover:bg-slate-800/50"
            }`}
          >
            <Lightbulb size={16} />
            Hypotheses ({hypotheses.length})
          </button>
        </div>

        {/* Vulnerabilities Tab */}
        {activeTab === "vulnerabilities" && (
          <>
            {/* Filter */}
            <div className="flex items-center gap-4 mb-4">
              <Filter size={16} className="text-slate-500" />
              <span className="text-slate-500 text-sm">Severity:</span>
              {["all", "critical", "high", "medium", "low"].map((sev) => (
                <button
                  key={sev}
                  onClick={() => setSeverityFilter(sev)}
                  className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                    severityFilter === sev
                      ? "bg-cyan-500/20 text-cyan-400"
                      : "bg-slate-800 text-slate-400 hover:text-white"
                  }`}
                >
                  {sev.charAt(0).toUpperCase() + sev.slice(1)}
                </button>
              ))}
            </div>

            {filteredVulnerabilities.length === 0 ? (
              <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-8 text-center">
                <Bug size={48} className="mx-auto mb-4 text-slate-600" />
                <p className="text-slate-400">No vulnerabilities found</p>
                <p className="text-sm text-slate-500 mt-2">
                  {severityFilter !== "all" ? "Try adjusting the filter" : "Run verification pipeline to detect vulnerabilities"}
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {filteredVulnerabilities.map((vuln, idx) => {
                  const severityConfig = getSeverityConfig(vuln.properties.severity);

                  return (
                    <motion.div
                      key={vuln.id}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: idx * 0.05 }}
                      className={`bg-slate-900/50 border rounded-xl p-4 ${severityConfig.border}`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex items-start gap-3">
                          <div className={`p-2 rounded-lg ${severityConfig.bg}`}>
                            <Bug className={severityConfig.color} size={18} />
                          </div>
                          <div>
                            <h3 className="text-white font-medium">{vuln.properties.title || "Unnamed Vulnerability"}</h3>
                            {vuln.properties.cve_id && (
                              <a
                                href={`https://nvd.nist.gov/vuln/detail/${vuln.properties.cve_id}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-cyan-400 hover:underline text-sm flex items-center gap-1 mt-1"
                              >
                                {vuln.properties.cve_id}
                                <ExternalLink size={12} />
                              </a>
                            )}
                            {vuln.properties.target_id && (
                              <p className="text-slate-500 text-sm mt-1">
                                Target: <span className="font-mono text-slate-400">{vuln.properties.target_id}</span>
                              </p>
                            )}
                          </div>
                        </div>
                        <div className="text-right">
                          <span className={`px-3 py-1 rounded text-xs font-bold ${severityConfig.bg} ${severityConfig.color}`}>
                            {vuln.properties.severity?.toUpperCase() || "UNKNOWN"}
                          </span>
                          {vuln.properties.cvss_score && (
                            <p className="text-slate-500 text-xs mt-1">CVSS: {vuln.properties.cvss_score}</p>
                          )}
                        </div>
                      </div>
                      {vuln.properties.description && (
                        <p className="text-slate-400 text-sm mt-3 ml-11">{vuln.properties.description}</p>
                      )}
                      {vuln.properties.evidence && (
                        <div className="mt-3 ml-11 p-3 bg-slate-800/50 rounded-lg">
                          <p className="text-xs text-slate-500 mb-1">Evidence:</p>
                          <code className="text-xs text-slate-300 font-mono">{vuln.properties.evidence}</code>
                        </div>
                      )}
                    </motion.div>
                  );
                })}
              </div>
            )}
          </>
        )}

        {/* Hypotheses Tab */}
        {activeTab === "hypotheses" && (
          <>
            {hypotheses.length === 0 ? (
              <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-8 text-center">
                <Lightbulb size={48} className="mx-auto mb-4 text-slate-600" />
                <p className="text-slate-400">No hypotheses generated</p>
                <p className="text-sm text-slate-500 mt-2">Hypotheses are generated during the intel phase</p>
              </div>
            ) : (
              <div className="space-y-4">
                {hypotheses.map((hypo, idx) => {
                  const confidence = hypo.properties.confidence || 0;
                  const confidenceColor = getConfidenceColor(confidence);

                  return (
                    <motion.div
                      key={hypo.id}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: idx * 0.05 }}
                      className="bg-slate-900/50 border border-slate-800 rounded-xl p-4 hover:border-slate-700 transition-colors"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex items-start gap-3">
                          <div className="p-2 bg-amber-500/20 rounded-lg">
                            <Lightbulb className="text-amber-400" size={18} />
                          </div>
                          <div>
                            <h3 className="text-white font-medium">{hypo.properties.title || "Unnamed Hypothesis"}</h3>
                            <div className="flex items-center gap-3 mt-2">
                              <span className="px-2 py-1 bg-slate-800 rounded text-xs text-slate-300">
                                {hypo.properties.attack_type}
                              </span>
                              {hypo.properties.target_id && (
                                <span className="text-slate-500 text-sm">
                                  Target: <span className="font-mono text-slate-400">{hypo.properties.target_id}</span>
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                        <div className="text-right">
                          <span className={`text-xl font-bold ${confidenceColor}`}>
                            {(confidence * 100).toFixed(0)}%
                          </span>
                          <p className="text-xs text-slate-500">Confidence</p>
                        </div>
                      </div>
                      {hypo.properties.rationale && (
                        <p className="text-slate-400 text-sm mt-3 ml-11">{hypo.properties.rationale}</p>
                      )}
                    </motion.div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
