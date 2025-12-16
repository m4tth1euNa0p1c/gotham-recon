"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Settings, Server, Shield, Bell, Palette, Database, Key, Save, RefreshCw } from "lucide-react";
import Sidebar from "@/components/dashboard/Sidebar";

interface SettingsSection {
  id: string;
  icon: typeof Settings;
  label: string;
}

const sections: SettingsSection[] = [
  { id: "general", icon: Settings, label: "General" },
  { id: "api", icon: Server, label: "API Configuration" },
  { id: "security", icon: Shield, label: "Security" },
  { id: "notifications", icon: Bell, label: "Notifications" },
  { id: "appearance", icon: Palette, label: "Appearance" },
];

export default function SettingsPage() {
  const [activeSection, setActiveSection] = useState("general");
  const [settings, setSettings] = useState({
    // General
    autoRefresh: true,
    refreshInterval: 30,
    maxConcurrentMissions: 3,

    // API
    orchestratorUrl: "http://localhost:8000",
    graphServiceUrl: "http://localhost:8001",
    bffGatewayUrl: "http://localhost:8080",

    // Security
    requireAuth: false,
    sessionTimeout: 60,

    // Notifications
    enableNotifications: true,
    notifyOnComplete: true,
    notifyOnError: true,

    // Appearance
    theme: "dark",
    compactMode: false,
    showAnimations: true,
  });

  const handleSave = () => {
    // In a real app, this would save to backend/localStorage
    console.log("Saving settings:", settings);
    // Show success toast
  };

  const Toggle = ({ enabled, onChange }: { enabled: boolean; onChange: (v: boolean) => void }) => (
    <button
      onClick={() => onChange(!enabled)}
      className={`relative w-12 h-6 rounded-full transition-colors ${enabled ? "bg-cyan-500" : "bg-slate-700"}`}
    >
      <div
        className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${enabled ? "left-7" : "left-1"}`}
      />
    </button>
  );

  return (
    <div className="flex h-screen bg-[#0a0a0f]">
      <Sidebar />
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto p-8">
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-8"
          >
            <h1 className="text-2xl font-bold text-white flex items-center gap-3 mb-2">
              <Settings className="text-cyan-500" />
              Settings
            </h1>
            <p className="text-slate-400">
              Configure your Gotham Recon instance.
            </p>
          </motion.div>

          <div className="flex gap-8">
            {/* Sidebar Navigation */}
            <div className="w-48 shrink-0">
              <nav className="space-y-1">
                {sections.map((section) => {
                  const Icon = section.icon;
                  const isActive = activeSection === section.id;

                  return (
                    <button
                      key={section.id}
                      onClick={() => setActiveSection(section.id)}
                      className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                        isActive
                          ? "bg-cyan-500/20 text-cyan-400"
                          : "text-slate-400 hover:bg-slate-800 hover:text-white"
                      }`}
                    >
                      <Icon size={18} />
                      <span className="text-sm font-medium">{section.label}</span>
                    </button>
                  );
                })}
              </nav>
            </div>

            {/* Settings Content */}
            <div className="flex-1 bg-slate-900/50 border border-slate-800 rounded-xl p-6">
              {activeSection === "general" && (
                <div className="space-y-6">
                  <h2 className="text-lg font-bold text-white mb-4">General Settings</h2>

                  <div className="flex items-center justify-between py-3 border-b border-slate-800">
                    <div>
                      <p className="text-white font-medium">Auto Refresh</p>
                      <p className="text-sm text-slate-500">Automatically refresh data in the dashboard</p>
                    </div>
                    <Toggle
                      enabled={settings.autoRefresh}
                      onChange={(v) => setSettings({ ...settings, autoRefresh: v })}
                    />
                  </div>

                  <div className="py-3 border-b border-slate-800">
                    <div className="flex items-center justify-between mb-2">
                      <div>
                        <p className="text-white font-medium">Refresh Interval</p>
                        <p className="text-sm text-slate-500">Time between automatic refreshes (seconds)</p>
                      </div>
                      <input
                        type="number"
                        value={settings.refreshInterval}
                        onChange={(e) => setSettings({ ...settings, refreshInterval: parseInt(e.target.value) })}
                        className="w-24 bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white text-right"
                        min={5}
                        max={300}
                      />
                    </div>
                  </div>

                  <div className="py-3">
                    <div className="flex items-center justify-between mb-2">
                      <div>
                        <p className="text-white font-medium">Max Concurrent Missions</p>
                        <p className="text-sm text-slate-500">Maximum number of missions that can run simultaneously</p>
                      </div>
                      <input
                        type="number"
                        value={settings.maxConcurrentMissions}
                        onChange={(e) => setSettings({ ...settings, maxConcurrentMissions: parseInt(e.target.value) })}
                        className="w-24 bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white text-right"
                        min={1}
                        max={10}
                      />
                    </div>
                  </div>
                </div>
              )}

              {activeSection === "api" && (
                <div className="space-y-6">
                  <h2 className="text-lg font-bold text-white mb-4">API Configuration</h2>

                  <div className="py-3 border-b border-slate-800">
                    <label className="block text-white font-medium mb-2">Orchestrator URL</label>
                    <input
                      type="text"
                      value={settings.orchestratorUrl}
                      onChange={(e) => setSettings({ ...settings, orchestratorUrl: e.target.value })}
                      className="w-full bg-slate-800 border border-slate-700 rounded px-4 py-2 text-white font-mono"
                    />
                    <p className="text-sm text-slate-500 mt-1">The URL of the recon-orchestrator service</p>
                  </div>

                  <div className="py-3 border-b border-slate-800">
                    <label className="block text-white font-medium mb-2">Graph Service URL</label>
                    <input
                      type="text"
                      value={settings.graphServiceUrl}
                      onChange={(e) => setSettings({ ...settings, graphServiceUrl: e.target.value })}
                      className="w-full bg-slate-800 border border-slate-700 rounded px-4 py-2 text-white font-mono"
                    />
                    <p className="text-sm text-slate-500 mt-1">The URL of the graph-service</p>
                  </div>

                  <div className="py-3">
                    <label className="block text-white font-medium mb-2">BFF Gateway URL</label>
                    <input
                      type="text"
                      value={settings.bffGatewayUrl}
                      onChange={(e) => setSettings({ ...settings, bffGatewayUrl: e.target.value })}
                      className="w-full bg-slate-800 border border-slate-700 rounded px-4 py-2 text-white font-mono"
                    />
                    <p className="text-sm text-slate-500 mt-1">The URL of the BFF gateway (GraphQL endpoint)</p>
                  </div>
                </div>
              )}

              {activeSection === "notifications" && (
                <div className="space-y-6">
                  <h2 className="text-lg font-bold text-white mb-4">Notification Settings</h2>

                  <div className="flex items-center justify-between py-3 border-b border-slate-800">
                    <div>
                      <p className="text-white font-medium">Enable Notifications</p>
                      <p className="text-sm text-slate-500">Show browser notifications for events</p>
                    </div>
                    <Toggle
                      enabled={settings.enableNotifications}
                      onChange={(v) => setSettings({ ...settings, enableNotifications: v })}
                    />
                  </div>

                  <div className="flex items-center justify-between py-3 border-b border-slate-800">
                    <div>
                      <p className="text-white font-medium">Mission Complete</p>
                      <p className="text-sm text-slate-500">Notify when a mission completes</p>
                    </div>
                    <Toggle
                      enabled={settings.notifyOnComplete}
                      onChange={(v) => setSettings({ ...settings, notifyOnComplete: v })}
                    />
                  </div>

                  <div className="flex items-center justify-between py-3">
                    <div>
                      <p className="text-white font-medium">Mission Error</p>
                      <p className="text-sm text-slate-500">Notify when a mission fails or encounters an error</p>
                    </div>
                    <Toggle
                      enabled={settings.notifyOnError}
                      onChange={(v) => setSettings({ ...settings, notifyOnError: v })}
                    />
                  </div>
                </div>
              )}

              {activeSection === "appearance" && (
                <div className="space-y-6">
                  <h2 className="text-lg font-bold text-white mb-4">Appearance Settings</h2>

                  <div className="flex items-center justify-between py-3 border-b border-slate-800">
                    <div>
                      <p className="text-white font-medium">Compact Mode</p>
                      <p className="text-sm text-slate-500">Use a more condensed layout</p>
                    </div>
                    <Toggle
                      enabled={settings.compactMode}
                      onChange={(v) => setSettings({ ...settings, compactMode: v })}
                    />
                  </div>

                  <div className="flex items-center justify-between py-3">
                    <div>
                      <p className="text-white font-medium">Show Animations</p>
                      <p className="text-sm text-slate-500">Enable motion and transition effects</p>
                    </div>
                    <Toggle
                      enabled={settings.showAnimations}
                      onChange={(v) => setSettings({ ...settings, showAnimations: v })}
                    />
                  </div>
                </div>
              )}

              {activeSection === "security" && (
                <div className="space-y-6">
                  <h2 className="text-lg font-bold text-white mb-4">Security Settings</h2>

                  <div className="flex items-center justify-between py-3 border-b border-slate-800">
                    <div>
                      <p className="text-white font-medium">Require Authentication</p>
                      <p className="text-sm text-slate-500">Require login to access the dashboard</p>
                    </div>
                    <Toggle
                      enabled={settings.requireAuth}
                      onChange={(v) => setSettings({ ...settings, requireAuth: v })}
                    />
                  </div>

                  <div className="py-3">
                    <div className="flex items-center justify-between mb-2">
                      <div>
                        <p className="text-white font-medium">Session Timeout</p>
                        <p className="text-sm text-slate-500">Minutes before session expires</p>
                      </div>
                      <input
                        type="number"
                        value={settings.sessionTimeout}
                        onChange={(e) => setSettings({ ...settings, sessionTimeout: parseInt(e.target.value) })}
                        className="w-24 bg-slate-800 border border-slate-700 rounded px-3 py-2 text-white text-right"
                        min={5}
                        max={480}
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Save Button */}
              <div className="mt-8 pt-6 border-t border-slate-800 flex justify-end gap-4">
                <button
                  onClick={() => window.location.reload()}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg flex items-center gap-2 transition-colors"
                >
                  <RefreshCw size={16} />
                  Reset
                </button>
                <button
                  onClick={handleSave}
                  className="px-6 py-2 bg-cyan-500 hover:bg-cyan-600 text-black font-bold rounded-lg flex items-center gap-2 transition-colors"
                >
                  <Save size={16} />
                  Save Changes
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
