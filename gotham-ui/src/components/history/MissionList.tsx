"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { format } from "date-fns";
import { motion, AnimatePresence } from "framer-motion";
import { Shield, Clock, ArrowRight, Activity, Trash2, AlertTriangle, X } from "lucide-react";
import { MissionService, Mission } from "@/services/MissionService";
import { useMissionStore } from "@/stores/missionStore";

// Confirmation Dialog Component
function ConfirmDialog({
    isOpen,
    title,
    message,
    confirmText = "Delete",
    onConfirm,
    onCancel,
    isDestructive = true
}: {
    isOpen: boolean;
    title: string;
    message: string;
    confirmText?: string;
    onConfirm: () => void;
    onCancel: () => void;
    isDestructive?: boolean;
}) {
    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onCancel} />
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="relative bg-[#12121a] border border-[#1a1a25] rounded-lg p-6 max-w-md w-full mx-4 shadow-2xl"
            >
                <div className="flex items-center gap-3 mb-4">
                    <div className={`w-10 h-10 rounded flex items-center justify-center ${isDestructive ? 'bg-red-950/50 text-red-400' : 'bg-cyan-950/50 text-cyan-400'}`}>
                        <AlertTriangle size={20} />
                    </div>
                    <h3 className="text-lg font-bold text-slate-200">{title}</h3>
                </div>
                <p className="text-sm text-slate-400 mb-6">{message}</p>
                <div className="flex justify-end gap-3">
                    <button
                        onClick={onCancel}
                        className="px-4 py-2 text-sm text-slate-400 hover:text-slate-200 transition-colors"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={onConfirm}
                        className={`px-4 py-2 text-sm font-medium rounded transition-colors ${
                            isDestructive
                                ? 'bg-red-600 hover:bg-red-500 text-white'
                                : 'bg-cyan-600 hover:bg-cyan-500 text-white'
                        }`}
                    >
                        {confirmText}
                    </button>
                </div>
            </motion.div>
        </div>
    );
}

export default function MissionList() {
    const router = useRouter();
    const [missions, setMissions] = useState<Mission[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [deleteConfirm, setDeleteConfirm] = useState<{ type: 'mission' | 'all'; missionId?: string } | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);

    // Get setCurrentMission from store to update selected mission
    const setCurrentMission = useMissionStore((state) => state.setCurrentMission);

    useEffect(() => {
        loadMissions();
    }, []);

    const loadMissions = async () => {
        setIsLoading(true);
        try {
            const result = await MissionService.getMissions(50);
            // Sort by date desc (if not already sorted by backend)
            const sorted = result.items.sort((a, b) =>
                new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
            );
            setMissions(sorted);
        } catch (err) {
            console.error("Failed to load missions:", err);
            setError("Failed to load mission history");
        } finally {
            setIsLoading(false);
        }
    };

    const handleDeleteMission = useCallback(async (missionId: string) => {
        setIsDeleting(true);
        try {
            const result = await MissionService.deleteMission(missionId);
            if (result.success) {
                setMissions(prev => prev.filter(m => m.id !== missionId));
            }
        } catch (err) {
            console.error("Failed to delete mission:", err);
        } finally {
            setIsDeleting(false);
            setDeleteConfirm(null);
        }
    }, []);

    const handleClearAll = useCallback(async () => {
        setIsDeleting(true);
        try {
            const result = await MissionService.clearAllData();
            if (result.success) {
                setMissions([]);
            }
        } catch (err) {
            console.error("Failed to clear all data:", err);
        } finally {
            setIsDeleting(false);
            setDeleteConfirm(null);
        }
    }, []);

    const getStatusColor = (status: string) => {
        switch (status.toLowerCase()) {
            case 'running': return 'text-cyan-400 bg-cyan-950/30 border-cyan-800';
            case 'completed': return 'text-emerald-400 bg-emerald-950/30 border-emerald-800';
            case 'failed': return 'text-red-400 bg-red-950/30 border-red-800';
            case 'cancelled': return 'text-orange-400 bg-orange-950/30 border-orange-800';
            default: return 'text-slate-400 bg-slate-900 border-slate-700';
        }
    };

    const handleMissionClick = (mission: Mission) => {
        // Update the current mission in the store BEFORE navigating
        setCurrentMission(mission);
        router.push(`/mission/${mission.id}/workflow`);
    };

    if (isLoading) {
        return (
            <div className="flex items-center justify-center p-12">
                <div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
            </div>
        );
    }

    if (error) {
        return (
            <div className="p-8 text-center">
                <div className="text-red-400 mb-2">{error}</div>
                <button
                    onClick={loadMissions}
                    className="text-sm text-cyan-400 hover:text-cyan-300 underline"
                >
                    Retry
                </button>
            </div>
        );
    }

    if (missions.length === 0) {
        return (
            <div className="p-12 text-center text-slate-500">
                <Clock className="w-12 h-12 mx-auto mb-4 opacity-20" />
                <p>No missions found</p>
            </div>
        );
    }

    return (
        <>
            {/* Header with Clear All button */}
            <div className="flex justify-between items-center mb-4">
                <div className="text-sm text-slate-500">
                    {missions.length} mission{missions.length > 1 ? 's' : ''}
                </div>
                <button
                    onClick={() => setDeleteConfirm({ type: 'all' })}
                    disabled={isDeleting}
                    className="flex items-center gap-2 px-3 py-1.5 text-xs text-red-400 hover:text-red-300 hover:bg-red-950/30 border border-red-900/50 rounded transition-colors disabled:opacity-50"
                >
                    <Trash2 size={14} />
                    Clear All Data
                </button>
            </div>

            <div className="w-full">
                <div className="grid gap-2">
                    {missions.map((mission, index) => (
                        <motion.div
                            key={mission.id}
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: index * 0.05 }}
                            className="group relative bg-[#12121a] border border-[#1a1a25] hover:border-cyan-500/50 p-4 rounded-lg transition-all hover:bg-[#16161f]"
                        >
                            <div className="flex items-center justify-between">
                                <div
                                    className="flex items-center gap-4 flex-1 cursor-pointer"
                                    onClick={() => handleMissionClick(mission)}
                                >
                                    <div className={`w-10 h-10 rounded flex items-center justify-center border ${getStatusColor(mission.status)}`}>
                                        <Shield size={18} />
                                    </div>
                                    <div>
                                        <div className="font-mono font-bold text-slate-200 group-hover:text-cyan-400 transition-colors">
                                            {mission.targetDomain}
                                        </div>
                                        <div className="text-xs text-slate-500 flex items-center gap-2 mt-1">
                                            <Clock size={12} />
                                            {format(new Date(mission.createdAt), "MMM d, yyyy HH:mm")}
                                            <span className="w-1 h-1 rounded-full bg-slate-600" />
                                            <span>{mission.mode}</span>
                                        </div>
                                    </div>
                                </div>

                                <div className="flex items-center gap-4">
                                    {/* Stats Mini-View */}
                                    {mission.stats && (
                                        <div className="hidden md:flex items-center gap-4 text-xs text-slate-500">
                                            <div className="flex items-center gap-1.5">
                                                <Activity size={12} />
                                                <span>{mission.stats.totalNodes || 0} Nodes</span>
                                            </div>
                                        </div>
                                    )}

                                    <div className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${getStatusColor(mission.status)}`}>
                                        {mission.status}
                                    </div>

                                    {/* Delete Button */}
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            setDeleteConfirm({ type: 'mission', missionId: mission.id });
                                        }}
                                        disabled={isDeleting}
                                        className="p-2 text-slate-600 hover:text-red-400 hover:bg-red-950/30 rounded transition-colors opacity-0 group-hover:opacity-100 disabled:opacity-50"
                                        title="Delete mission"
                                    >
                                        <Trash2 size={16} />
                                    </button>

                                    <div
                                        className="cursor-pointer"
                                        onClick={() => handleMissionClick(mission)}
                                    >
                                        <ArrowRight className="w-4 h-4 text-slate-600 group-hover:text-cyan-400 transform group-hover:translate-x-1 transition-all" />
                                    </div>
                                </div>
                            </div>
                        </motion.div>
                    ))}
                </div>
            </div>

            {/* Confirmation Dialogs */}
            <AnimatePresence>
                {deleteConfirm?.type === 'mission' && deleteConfirm.missionId && (
                    <ConfirmDialog
                        isOpen={true}
                        title="Delete Mission"
                        message={`Are you sure you want to delete this mission? This will permanently remove all nodes, edges, logs, and associated data.`}
                        confirmText={isDeleting ? "Deleting..." : "Delete Mission"}
                        onConfirm={() => handleDeleteMission(deleteConfirm.missionId!)}
                        onCancel={() => setDeleteConfirm(null)}
                    />
                )}
                {deleteConfirm?.type === 'all' && (
                    <ConfirmDialog
                        isOpen={true}
                        title="Clear All Data"
                        message="Are you sure you want to clear ALL data? This will permanently delete all missions, nodes, edges, and logs. This action cannot be undone!"
                        confirmText={isDeleting ? "Clearing..." : "Clear Everything"}
                        onConfirm={handleClearAll}
                        onCancel={() => setDeleteConfirm(null)}
                    />
                )}
            </AnimatePresence>
        </>
    );
}
