"use client";

import { Shield, Home, Activity, FileSearch, Settings, FileText, Target, BarChart3, Bug, Network } from "lucide-react";
import { motion } from "framer-motion";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useUIStore } from "@/stores/uiStore";
import { useMissionStore } from "@/stores/missionStore";

interface NavItem {
    path: string;
    icon: typeof Home;
    label: string;
    badge?: number;
}

export default function Sidebar() {
    // UI State
    const extensionConnected = useUIStore((state) => state.extensionConnected);

    // Navigation and Routing
    const pathname = usePathname();
    const currentMission = useMissionStore((state) => state.currentMission);
    const missionId = currentMission?.id;

    // Extract mission ID from pathname if on a mission page
    const pathMissionId = pathname.match(/\/mission\/([^/]+)/)?.[1];
    const activeMissionId = missionId || pathMissionId;

    // Main Navigation Routes
    const mainNav: NavItem[] = [
        { path: "/", icon: Home, label: "Dashboard" },
        { path: "/history", icon: FileSearch, label: "Mission History" },
        { path: "/targets", icon: Target, label: "Targets" },
        { path: "/reports", icon: FileText, label: "Reports" },
    ];

    // Mission-specific Routes (only when a mission is active)
    const missionNav: NavItem[] = activeMissionId ? [
        { path: `/mission/${activeMissionId}`, icon: Shield, label: "Mission Details" },
        { path: `/mission/${activeMissionId}/workflow`, icon: Activity, label: "Workflow" },
        { path: `/mission/${activeMissionId}/graph`, icon: Network, label: "Asset Graph" },
        { path: `/mission/${activeMissionId}/vulnerabilities`, icon: Bug, label: "Vulnerabilities" },
    ] : [];

    // Tools & Settings Routes
    const toolsNav: NavItem[] = [
        { path: "/analytics", icon: BarChart3, label: "Analytics" },
        { path: "/settings", icon: Settings, label: "Settings" },
    ];

    // Check if path is active (exact match or starts with for mission pages)
    const isActive = (path: string) => {
        if (path === "/") return pathname === "/";
        return pathname === path || pathname.startsWith(path + "/");
    };

    const NavSection = ({ title, items }: { title: string; items: NavItem[] }) => (
        <div className="flex flex-col gap-1 w-full items-center mb-4">
            <div className="text-[8px] text-[#4a4a5a] uppercase font-bold mb-1 tracking-wider">{title}</div>
            {items.map((item) => (
                <Link
                    key={item.path}
                    href={item.path}
                    className={`relative w-9 h-9 rounded flex items-center justify-center transition-all group ${
                        isActive(item.path)
                            ? "bg-[#00ffff]/10 text-[#00ffff] border border-[#00ffff]/30"
                            : "text-[#4a4a5a] hover:text-[#00ffff] hover:bg-[#1a1a25]"
                    }`}
                    title={item.label}
                >
                    <item.icon size={16} />
                    {item.badge !== undefined && item.badge > 0 && (
                        <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-white text-[9px] font-bold rounded-full flex items-center justify-center">
                            {item.badge > 9 ? "9+" : item.badge}
                        </span>
                    )}
                    {/* Tooltip */}
                    <div className="absolute left-full ml-2 px-2 py-1 bg-[#1a1a25] border border-[#2a2a3a] rounded text-xs text-white whitespace-nowrap opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50 pointer-events-none">
                        {item.label}
                    </div>
                </Link>
            ))}
        </div>
    );

    return (
        <aside className="w-14 bg-[#0d0d12] border-r border-[#1a1a25] flex flex-col items-center py-3 z-50 h-full overflow-y-auto noscroll shrink-0">
            {/* Logo */}
            <div className="mb-6 relative shrink-0">
                <Link href="/">
                    <motion.div
                        animate={{
                            boxShadow: extensionConnected
                                ? ['0 0 10px rgba(0,255,255,0.3)', '0 0 20px rgba(0,255,255,0.6)', '0 0 10px rgba(0,255,255,0.3)']
                                : ['0 0 0px rgba(0,0,0,0)', '0 0 0px rgba(0,0,0,0)']
                        }}
                        transition={{ duration: 2, repeat: Infinity }}
                        className={`w-9 h-9 rounded flex items-center justify-center transition-colors cursor-pointer ${
                            extensionConnected
                                ? "bg-gradient-to-br from-[#00ffff] to-[#bf00ff]"
                                : "bg-[#1a1a25] border border-[#2a2a3a] hover:border-[#00ffff]/50"
                        }`}
                        title="Gotham Recon"
                    >
                        <Shield size={20} className={extensionConnected ? "text-[#0a0a0f]" : "text-[#4a4a5a]"} />
                    </motion.div>
                </Link>

                {/* Connection Status Dot */}
                <div className={`absolute -bottom-1 -right-1 w-2.5 h-2.5 rounded-full border-2 border-[#0d0d12] ${
                    extensionConnected ? "bg-[#00ff41]" : "bg-[#4a4a5a]"
                }`} />
            </div>

            {/* Navigation */}
            <nav className="flex-1 flex flex-col w-full items-center">
                <NavSection title="MAIN" items={mainNav} />

                {missionNav.length > 0 && (
                    <NavSection title="MISSION" items={missionNav} />
                )}

                <NavSection title="TOOLS" items={toolsNav} />
            </nav>

            {/* Version */}
            <div className="text-[9px] text-[#3a3a4a] font-mono uppercase tracking-widest mt-2 flex flex-col items-center gap-1 shrink-0">
                <span>v3.0</span>
                {extensionConnected && (
                    <span className="text-[8px] text-[#00ff41]">EXT</span>
                )}
            </div>
        </aside>
    );
}
