"use client";

import { motion } from "framer-motion";
import { History, LayoutList } from "lucide-react";
import Sidebar from "@/components/dashboard/Sidebar";
import Header from "@/components/dashboard/Header";
import MissionList from "@/components/history/MissionList";

export default function HistoryPage() {
    return (
        <div className="flex h-screen overflow-hidden bg-[#0a0a0f]">
            {/* Sidebar */}
            <Sidebar />

            {/* Main Content */}
            <div className="flex-1 flex flex-col min-w-0">
                <Header />

                <main className="flex-1 overflow-y-auto p-8">
                    <div className="max-w-5xl mx-auto">
                        <motion.div
                            initial={{ opacity: 0, y: -20 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="mb-8"
                        >
                            <h1 className="text-2xl font-bold text-white flex items-center gap-3 mb-2">
                                <History className="text-cyan-500" />
                                Mission History
                            </h1>
                            <p className="text-slate-400">
                                Archive of all reconnaissance missions and their workflow states.
                            </p>
                        </motion.div>

                        <MissionList />
                    </div>
                </main>
            </div>
        </div>
    );
}
