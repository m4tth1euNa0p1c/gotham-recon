"use client";

import { useParams } from "next/navigation";
import { useEffect, useState, useMemo } from "react";
import { graphqlFetch, QUERIES, Mission, API_CONFIG } from "@/lib/api";
import {
  Loader2,
  ArrowLeft,
  Activity,
  Eye,
  Globe,
  Server,
  AlertTriangle,
  Link2,
  Clock,
  Target,
  Play,
  CheckCircle,
  XCircle,
  Pause,
  Shield,
  Code,
  Database,
  Network,
  FileCode,
  Lightbulb,
  ExternalLink,
  ChevronRight,
  Cpu,
  Timer,
  Zap,
} from "lucide-react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import Sidebar from "@/components/dashboard/Sidebar";

// Types
interface GraphNode {
  id: string;
  type: string;
  properties: Record<string, unknown>;
}

interface GraphStats {
  totalNodes: number;
  totalEdges: number;
  nodesByType: Record<string, number>;
}

interface MissionProgress {
  phases_completed?: string[];
  current_metrics?: {
    crewai?: {
      duration?: number;
      summary?: {
        subdomains: number;
        http_services: number;
        endpoints: number;
        dns_records: number;
      };
      phases?: {
        passive?: { duration: number; result?: { subdomains?: string[]; dns?: DnsRecord[] } };
        active?: { duration: number; result?: { http_services?: HttpService[] } };
        intel?: { duration: number };
        planning?: { duration: number };
      };
    };
  };
}

interface DnsRecord {
  subdomain: string;
  ips: string[];
  records: {
    A?: string[];
    CNAME?: string[];
    TXT?: string[];
    NS?: string[];
    MX?: string[];
  };
}

interface HttpService {
  host: string;
  url: string;
  status_code: number;
  title: string | null;
  technologies: string[];
  ip: string;
}

// Tab definitions
type TabId = "overview" | "subdomains" | "services" | "endpoints" | "hypotheses" | "technologies";

const tabs: { id: TabId; label: string; icon: typeof Globe }[] = [
  { id: "overview", label: "Overview", icon: Activity },
  { id: "subdomains", label: "Subdomains", icon: Globe },
  { id: "services", label: "HTTP Services", icon: Server },
  { id: "endpoints", label: "Endpoints", icon: Link2 },
  { id: "hypotheses", label: "Hypotheses", icon: Lightbulb },
  { id: "technologies", label: "Technologies", icon: Cpu },
];

export default function MissionDetailPage() {
  const params = useParams();
  const missionId = params.id as string;
  const [mission, setMission] = useState<Mission | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const [stats, setStats] = useState<GraphStats | null>(null);
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [missionDetails, setMissionDetails] = useState<MissionProgress | null>(null);

  // Fetch all data
  useEffect(() => {
    const fetchAll = async () => {
      try {
        // Fetch mission from GraphQL
        const missionData = await graphqlFetch<{ mission: Mission }>(
          QUERIES.GET_MISSION,
          { id: missionId }
        );
        setMission(missionData.mission);

        // Fetch stats
        const statsData = await graphqlFetch<{ graphStats: GraphStats }>(
          `query GetGraphStats($missionId: String!) {
            graphStats(missionId: $missionId) {
              totalNodes
              totalEdges
              nodesByType
            }
          }`,
          { missionId }
        );
        if (statsData?.graphStats) {
          setStats(statsData.graphStats);
        }

        // Fetch all nodes
        const nodesData = await graphqlFetch<{ nodes: GraphNode[] }>(
          `query GetNodes($missionId: String!) {
            nodes(missionId: $missionId, limit: 1000) {
              id
              type
              properties
            }
          }`,
          { missionId }
        );
        if (nodesData?.nodes) {
          setNodes(nodesData.nodes);
        }

        // Fetch full mission details from orchestrator REST API
        try {
          const orchestratorUrl = API_CONFIG.BFF_GATEWAY.replace(':8080', ':8000');
          const res = await fetch(`${orchestratorUrl}/api/v1/missions/${missionId}`);
          if (res.ok) {
            const details = await res.json();
            setMissionDetails(details.progress);
          }
        } catch {
          // REST fetch failed, continue with GraphQL data
        }
      } catch (e) {
        console.error("Failed to fetch mission:", e);
      } finally {
        setLoading(false);
      }
    };

    if (missionId) {
      fetchAll();
    }
  }, [missionId]);

  // Derived data
  const subdomainNodes = useMemo(() =>
    nodes.filter(n => n.type === "SUBDOMAIN"), [nodes]);
  const httpServiceNodes = useMemo(() =>
    nodes.filter(n => n.type === "HTTP_SERVICE"), [nodes]);
  const endpointNodes = useMemo(() =>
    nodes.filter(n => n.type === "ENDPOINT"), [nodes]);
  const hypothesisNodes = useMemo(() =>
    nodes.filter(n => n.type === "HYPOTHESIS"), [nodes]);
  const techNodes = useMemo(() =>
    nodes.filter(n => n.type === "TECHNOLOGY"), [nodes]);

  // Extract technologies from HTTP services
  const allTechnologies = useMemo(() => {
    const techMap = new Map<string, { name: string; count: number; services: string[] }>();

    httpServiceNodes.forEach(node => {
      const props = node.properties;
      let techs: string[] = [];

      if (typeof props.technology === "string") {
        try {
          techs = JSON.parse(props.technology.replace(/'/g, '"'));
        } catch {
          techs = [props.technology as string];
        }
      } else if (Array.isArray(props.technologies)) {
        techs = props.technologies;
      }

      techs.forEach(tech => {
        const existing = techMap.get(tech) || { name: tech, count: 0, services: [] };
        existing.count++;
        existing.services.push(props.url as string);
        techMap.set(tech, existing);
      });
    });

    return Array.from(techMap.values()).sort((a, b) => b.count - a.count);
  }, [httpServiceNodes]);

  // DNS records from mission details
  const dnsRecords = useMemo(() =>
    missionDetails?.current_metrics?.crewai?.phases?.passive?.result?.dns || [],
    [missionDetails]);

  // HTTP services from mission details (richer data)
  const httpServices = useMemo(() =>
    missionDetails?.current_metrics?.crewai?.phases?.active?.result?.http_services || [],
    [missionDetails]);

  // Phase timings
  const phaseDurations = useMemo(() => {
    const phases = missionDetails?.current_metrics?.crewai?.phases;
    if (!phases) return null;
    return {
      passive: phases.passive?.duration || 0,
      active: phases.active?.duration || 0,
      intel: phases.intel?.duration || 0,
      planning: phases.planning?.duration || 0,
      total: missionDetails?.current_metrics?.crewai?.duration || 0,
    };
  }, [missionDetails]);

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

  if (!mission) {
    return (
      <div className="flex h-screen bg-slate-950">
        <Sidebar />
        <div className="flex-1 flex flex-col items-center justify-center gap-4">
          <p className="text-red-400">Mission not found</p>
          <Link href="/" className="text-cyan-400 hover:underline flex items-center gap-2">
            <ArrowLeft size={16} />
            Back to Dashboard
          </Link>
        </div>
      </div>
    );
  }

  const getStatusConfig = () => {
    switch (mission.status) {
      case "running":
        return { icon: Play, color: "text-amber-400", bg: "bg-amber-500/20", border: "border-amber-500/30" };
      case "completed":
        return { icon: CheckCircle, color: "text-emerald-400", bg: "bg-emerald-500/20", border: "border-emerald-500/30" };
      case "failed":
        return { icon: XCircle, color: "text-red-400", bg: "bg-red-500/20", border: "border-red-500/30" };
      case "cancelled":
        return { icon: Pause, color: "text-blue-400", bg: "bg-blue-500/20", border: "border-blue-500/30" };
      default:
        return { icon: Clock, color: "text-slate-400", bg: "bg-slate-500/20", border: "border-slate-500/30" };
    }
  };

  const statusConfig = getStatusConfig();
  const StatusIcon = statusConfig.icon;

  const formatDuration = (seconds: number) => {
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs.toFixed(0)}s`;
  };

  return (
    <div className="flex h-screen bg-slate-950">
      <Sidebar />
      <div className="flex-1 overflow-y-auto p-8">
      {/* Header Card */}
      <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6 mb-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <Target className="text-cyan-400" size={24} />
              <h1 className="text-2xl font-bold text-white">{mission.targetDomain}</h1>
            </div>
            <p className="text-slate-500 font-mono text-sm">ID: {mission.id}</p>
          </div>

          <div className="flex items-center gap-4">
            {/* Duration badge */}
            {phaseDurations && (
              <div className="flex items-center gap-2 px-3 py-2 bg-slate-800/50 rounded-lg">
                <Timer size={16} className="text-slate-400" />
                <span className="text-white font-medium">{formatDuration(phaseDurations.total)}</span>
              </div>
            )}

            {/* Status Badge */}
            <div className={`flex items-center gap-2 px-4 py-2 rounded-lg border ${statusConfig.bg} ${statusConfig.border}`}>
              <StatusIcon size={18} className={statusConfig.color} />
              <span className={`font-bold ${statusConfig.color}`}>{mission.status.toUpperCase()}</span>
            </div>
          </div>
        </div>

        {/* Quick Stats Row */}
        {stats && (
          <div className="grid grid-cols-6 gap-3 mt-6">
            <div className="bg-slate-800/50 rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-cyan-400">{stats.nodesByType?.SUBDOMAIN || 0}</p>
              <p className="text-slate-500 text-xs">Subdomains</p>
            </div>
            <div className="bg-slate-800/50 rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-emerald-400">{stats.nodesByType?.HTTP_SERVICE || 0}</p>
              <p className="text-slate-500 text-xs">Services</p>
            </div>
            <div className="bg-slate-800/50 rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-amber-400">{stats.nodesByType?.ENDPOINT || 0}</p>
              <p className="text-slate-500 text-xs">Endpoints</p>
            </div>
            <div className="bg-slate-800/50 rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-purple-400">{stats.nodesByType?.HYPOTHESIS || 0}</p>
              <p className="text-slate-500 text-xs">Hypotheses</p>
            </div>
            <div className="bg-slate-800/50 rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-red-400">{stats.nodesByType?.VULNERABILITY || 0}</p>
              <p className="text-slate-500 text-xs">Vulnerabilities</p>
            </div>
            <div className="bg-slate-800/50 rounded-lg p-3 text-center">
              <p className="text-2xl font-bold text-blue-400">{allTechnologies.length}</p>
              <p className="text-slate-500 text-xs">Technologies</p>
            </div>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 border-b border-slate-800 pb-2">
        {tabs.map(tab => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-t-lg transition-colors ${
                isActive
                  ? "bg-slate-800 text-cyan-400 border-b-2 border-cyan-400"
                  : "text-slate-400 hover:text-white hover:bg-slate-800/50"
              }`}
            >
              <Icon size={16} />
              <span className="text-sm font-medium">{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.2 }}
        >
          {/* Overview Tab */}
          {activeTab === "overview" && (
            <div className="grid grid-cols-2 gap-6">
              {/* Phase Timings */}
              {phaseDurations && (
                <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6">
                  <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                    <Timer className="text-cyan-400" size={20} />
                    Phase Durations
                  </h3>
                  <div className="space-y-3">
                    {[
                      { name: "Passive Recon", duration: phaseDurations.passive, color: "bg-cyan-500" },
                      { name: "Active Recon", duration: phaseDurations.active, color: "bg-emerald-500" },
                      { name: "Endpoint Intel", duration: phaseDurations.intel, color: "bg-amber-500" },
                      { name: "Planning", duration: phaseDurations.planning, color: "bg-purple-500" },
                    ].map(phase => (
                      <div key={phase.name} className="flex items-center gap-4">
                        <div className="w-32 text-slate-400 text-sm">{phase.name}</div>
                        <div className="flex-1 bg-slate-800 rounded-full h-2 overflow-hidden">
                          <div
                            className={`h-full ${phase.color} rounded-full`}
                            style={{ width: `${Math.min((phase.duration / phaseDurations.total) * 100, 100)}%` }}
                          />
                        </div>
                        <div className="w-20 text-right text-white font-mono text-sm">
                          {formatDuration(phase.duration)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Quick Actions */}
              <div className="space-y-4">
                <Link href={`/mission/${missionId}/workflow`}>
                  <div className="bg-slate-900/50 border border-cyan-500/30 rounded-xl p-4 hover:border-cyan-500/60 transition-colors cursor-pointer group">
                    <div className="flex items-center gap-4">
                      <div className="p-3 bg-cyan-500/20 rounded-lg">
                        <Activity size={24} className="text-cyan-400" />
                      </div>
                      <div className="flex-1">
                        <h3 className="text-white font-bold">Workflow Visualization</h3>
                        <p className="text-slate-500 text-sm">View agent pipeline and tool calls</p>
                      </div>
                      <ChevronRight className="text-cyan-400 group-hover:translate-x-1 transition-transform" />
                    </div>
                  </div>
                </Link>

                <Link href="/">
                  <div className="bg-slate-900/50 border border-purple-500/30 rounded-xl p-4 hover:border-purple-500/60 transition-colors cursor-pointer group">
                    <div className="flex items-center gap-4">
                      <div className="p-3 bg-purple-500/20 rounded-lg">
                        <Network size={24} className="text-purple-400" />
                      </div>
                      <div className="flex-1">
                        <h3 className="text-white font-bold">Asset Graph</h3>
                        <p className="text-slate-500 text-sm">Explore node relationships</p>
                      </div>
                      <ChevronRight className="text-purple-400 group-hover:translate-x-1 transition-transform" />
                    </div>
                  </div>
                </Link>
              </div>

              {/* Top Technologies */}
              <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6 col-span-2">
                <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                  <Cpu className="text-blue-400" size={20} />
                  Detected Technologies
                </h3>
                <div className="flex flex-wrap gap-2">
                  {allTechnologies.slice(0, 20).map(tech => (
                    <span
                      key={tech.name}
                      className="px-3 py-1 bg-slate-800 rounded-full text-sm text-slate-300 border border-slate-700"
                    >
                      {tech.name}
                      <span className="ml-2 text-slate-500">({tech.count})</span>
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Subdomains Tab */}
          {activeTab === "subdomains" && (
            <div className="bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden">
              <div className="p-4 border-b border-slate-800">
                <h3 className="text-lg font-bold text-white">
                  {subdomainNodes.length} Subdomains Discovered
                </h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-slate-800/50">
                    <tr>
                      <th className="text-left p-3 text-slate-400 text-sm font-medium">Subdomain</th>
                      <th className="text-left p-3 text-slate-400 text-sm font-medium">IPs</th>
                      <th className="text-left p-3 text-slate-400 text-sm font-medium">DNS Records</th>
                      <th className="text-left p-3 text-slate-400 text-sm font-medium">Source</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {subdomainNodes.map(node => {
                      const props = node.properties;
                      const dns = dnsRecords.find(d => d.subdomain === props.name);
                      return (
                        <tr key={node.id} className="hover:bg-slate-800/30">
                          <td className="p-3">
                            <div className="flex items-center gap-2">
                              <Globe size={14} className="text-cyan-400" />
                              <span className="text-white font-mono text-sm">{props.name as string}</span>
                            </div>
                          </td>
                          <td className="p-3">
                            <div className="flex flex-wrap gap-1">
                              {dns?.ips?.map(ip => (
                                <span key={ip} className="px-2 py-0.5 bg-slate-800 rounded text-xs text-slate-300 font-mono">
                                  {ip}
                                </span>
                              )) || <span className="text-slate-500 text-sm">-</span>}
                            </div>
                          </td>
                          <td className="p-3">
                            <div className="flex flex-wrap gap-1">
                              {dns?.records?.A && <span className="px-2 py-0.5 bg-emerald-500/20 rounded text-xs text-emerald-400">A</span>}
                              {dns?.records?.CNAME && <span className="px-2 py-0.5 bg-blue-500/20 rounded text-xs text-blue-400">CNAME</span>}
                              {dns?.records?.TXT && <span className="px-2 py-0.5 bg-amber-500/20 rounded text-xs text-amber-400">TXT</span>}
                              {dns?.records?.NS && <span className="px-2 py-0.5 bg-purple-500/20 rounded text-xs text-purple-400">NS</span>}
                              {!dns?.records?.A && !dns?.records?.CNAME && <span className="text-slate-500 text-sm">-</span>}
                            </div>
                          </td>
                          <td className="p-3">
                            <span className="px-2 py-1 bg-slate-800 rounded text-xs text-slate-400">
                              {props.source as string}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* HTTP Services Tab */}
          {activeTab === "services" && (
            <div className="bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden">
              <div className="p-4 border-b border-slate-800">
                <h3 className="text-lg font-bold text-white">
                  {httpServices.length || httpServiceNodes.length} HTTP Services
                </h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-slate-800/50">
                    <tr>
                      <th className="text-left p-3 text-slate-400 text-sm font-medium">URL</th>
                      <th className="text-left p-3 text-slate-400 text-sm font-medium">Status</th>
                      <th className="text-left p-3 text-slate-400 text-sm font-medium">Title</th>
                      <th className="text-left p-3 text-slate-400 text-sm font-medium">Technologies</th>
                      <th className="text-left p-3 text-slate-400 text-sm font-medium">IP</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {(httpServices.length > 0 ? httpServices : httpServiceNodes.map(n => ({
                      url: n.properties.url as string,
                      status_code: n.properties.status_code as number,
                      title: null,
                      technologies: [],
                      ip: "",
                    }))).map((svc, idx) => {
                      const statusColor =
                        svc.status_code >= 200 && svc.status_code < 300 ? "text-emerald-400 bg-emerald-500/20" :
                        svc.status_code >= 300 && svc.status_code < 400 ? "text-blue-400 bg-blue-500/20" :
                        svc.status_code >= 400 && svc.status_code < 500 ? "text-amber-400 bg-amber-500/20" :
                        "text-red-400 bg-red-500/20";

                      return (
                        <tr key={idx} className="hover:bg-slate-800/30">
                          <td className="p-3">
                            <a
                              href={svc.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center gap-2 text-cyan-400 hover:text-cyan-300"
                            >
                              <span className="font-mono text-sm truncate max-w-xs">{svc.url}</span>
                              <ExternalLink size={12} />
                            </a>
                          </td>
                          <td className="p-3">
                            <span className={`px-2 py-1 rounded text-xs font-bold ${statusColor}`}>
                              {svc.status_code}
                            </span>
                          </td>
                          <td className="p-3">
                            <span className="text-slate-300 text-sm truncate max-w-xs block">
                              {svc.title || "-"}
                            </span>
                          </td>
                          <td className="p-3">
                            <div className="flex flex-wrap gap-1 max-w-xs">
                              {svc.technologies?.slice(0, 3).map((tech: string) => (
                                <span key={tech} className="px-2 py-0.5 bg-slate-800 rounded text-xs text-slate-300">
                                  {tech}
                                </span>
                              ))}
                              {svc.technologies?.length > 3 && (
                                <span className="px-2 py-0.5 bg-slate-800 rounded text-xs text-slate-500">
                                  +{svc.technologies.length - 3}
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="p-3">
                            <span className="font-mono text-xs text-slate-400">{svc.ip || "-"}</span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Endpoints Tab */}
          {activeTab === "endpoints" && (
            <div className="bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden">
              <div className="p-4 border-b border-slate-800">
                <h3 className="text-lg font-bold text-white">
                  {endpointNodes.length} Endpoints Discovered
                </h3>
              </div>
              {endpointNodes.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-slate-800/50">
                      <tr>
                        <th className="text-left p-3 text-slate-400 text-sm font-medium">Path</th>
                        <th className="text-left p-3 text-slate-400 text-sm font-medium">Method</th>
                        <th className="text-left p-3 text-slate-400 text-sm font-medium">Category</th>
                        <th className="text-left p-3 text-slate-400 text-sm font-medium">Source</th>
                        <th className="text-left p-3 text-slate-400 text-sm font-medium">Risk</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                      {endpointNodes.map(node => {
                        const props = node.properties;
                        const riskScore = (props.risk_score as number) || 0;
                        const riskColor =
                          riskScore >= 80 ? "text-red-400 bg-red-500/20" :
                          riskScore >= 60 ? "text-amber-400 bg-amber-500/20" :
                          riskScore >= 40 ? "text-yellow-400 bg-yellow-500/20" :
                          "text-slate-400 bg-slate-500/20";

                        return (
                          <tr key={node.id} className="hover:bg-slate-800/30">
                            <td className="p-3">
                              <span className="font-mono text-sm text-white">{props.path as string}</span>
                            </td>
                            <td className="p-3">
                              <span className="px-2 py-1 bg-slate-800 rounded text-xs font-bold text-slate-300">
                                {(props.method as string) || "GET"}
                              </span>
                            </td>
                            <td className="p-3">
                              <span className="text-slate-400 text-sm">{(props.category as string) || "-"}</span>
                            </td>
                            <td className="p-3">
                              <span className="text-slate-500 text-sm">{(props.source as string) || "-"}</span>
                            </td>
                            <td className="p-3">
                              {riskScore > 0 && (
                                <span className={`px-2 py-1 rounded text-xs font-bold ${riskColor}`}>
                                  {riskScore}
                                </span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="p-8 text-center text-slate-500">
                  <Link2 size={48} className="mx-auto mb-4 opacity-50" />
                  <p>No endpoints discovered yet</p>
                  <p className="text-sm mt-2">Endpoints are discovered through JS mining and HTML crawling</p>
                </div>
              )}
            </div>
          )}

          {/* Hypotheses Tab */}
          {activeTab === "hypotheses" && (
            <div className="bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden">
              <div className="p-4 border-b border-slate-800">
                <h3 className="text-lg font-bold text-white">
                  {hypothesisNodes.length} Security Hypotheses
                </h3>
              </div>
              {hypothesisNodes.length > 0 ? (
                <div className="divide-y divide-slate-800">
                  {hypothesisNodes.map(node => {
                    const props = node.properties;
                    const confidence = (props.confidence as number) || 0;
                    const confidenceColor =
                      confidence >= 0.7 ? "text-red-400" :
                      confidence >= 0.4 ? "text-amber-400" :
                      "text-slate-400";

                    return (
                      <div key={node.id} className="p-4 hover:bg-slate-800/30">
                        <div className="flex items-start justify-between">
                          <div className="flex items-start gap-3">
                            <div className="p-2 bg-amber-500/20 rounded-lg mt-1">
                              <Lightbulb size={18} className="text-amber-400" />
                            </div>
                            <div>
                              <h4 className="text-white font-medium">{props.title as string}</h4>
                              <div className="flex items-center gap-3 mt-2">
                                <span className="px-2 py-1 bg-slate-800 rounded text-xs text-slate-300">
                                  {props.attack_type as string}
                                </span>
                                <span className="text-slate-500 text-sm">
                                  Target: <span className="font-mono text-slate-400">{props.target_id as string}</span>
                                </span>
                              </div>
                            </div>
                          </div>
                          <div className="text-right">
                            <span className={`text-lg font-bold ${confidenceColor}`}>
                              {(confidence * 100).toFixed(0)}%
                            </span>
                            <p className="text-slate-500 text-xs">Confidence</p>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="p-8 text-center text-slate-500">
                  <Lightbulb size={48} className="mx-auto mb-4 opacity-50" />
                  <p>No hypotheses generated yet</p>
                  <p className="text-sm mt-2">Hypotheses are generated during the intel phase</p>
                </div>
              )}
            </div>
          )}

          {/* Technologies Tab */}
          {activeTab === "technologies" && (
            <div className="bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden">
              <div className="p-4 border-b border-slate-800">
                <h3 className="text-lg font-bold text-white">
                  {allTechnologies.length} Technologies Detected
                </h3>
              </div>
              {allTechnologies.length > 0 ? (
                <div className="grid grid-cols-3 gap-4 p-4">
                  {allTechnologies.map(tech => (
                    <div key={tech.name} className="bg-slate-800/50 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-white font-medium">{tech.name}</span>
                        <span className="px-2 py-1 bg-cyan-500/20 rounded text-xs text-cyan-400">
                          {tech.count} service{tech.count > 1 ? "s" : ""}
                        </span>
                      </div>
                      <div className="text-slate-500 text-xs truncate">
                        {tech.services.slice(0, 2).join(", ")}
                        {tech.services.length > 2 && ` +${tech.services.length - 2} more`}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-8 text-center text-slate-500">
                  <Cpu size={48} className="mx-auto mb-4 opacity-50" />
                  <p>No technologies detected yet</p>
                </div>
              )}
            </div>
          )}
        </motion.div>
      </AnimatePresence>
      </div>
    </div>
  );
}
