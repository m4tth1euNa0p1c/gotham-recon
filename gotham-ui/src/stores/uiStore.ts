/**
 * UI Store
 * Zustand store for UI state management
 */

import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

export type ViewTab = 'agents' | 'assets';
export type SidebarView = 'dashboard' | 'agents' | 'assets' | 'vulns' | 'reports' | 'config';

interface UIState {
  // Layout
  sidebarCollapsed: boolean;
  logPanelExpanded: boolean;
  logPanelHeight: number;

  // View
  activeTab: ViewTab;
  sidebarView: SidebarView;

  // Modals
  showSettingsModal: boolean;
  showMissionModal: boolean;
  showNodeDetailsModal: boolean;

  // Notifications
  notifications: Notification[];

  // Actions
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleLogPanel: () => void;
  setLogPanelExpanded: (expanded: boolean) => void;
  setLogPanelHeight: (height: number) => void;
  setActiveTab: (tab: ViewTab) => void;
  setSidebarView: (view: SidebarView) => void;
  openSettingsModal: () => void;
  closeSettingsModal: () => void;
  openMissionModal: () => void;
  closeMissionModal: () => void;
  openNodeDetailsModal: () => void;
  closeNodeDetailsModal: () => void;
  addNotification: (notification: Omit<Notification, 'id' | 'timestamp'>) => void;
  removeNotification: (id: string) => void;
  clearNotifications: () => void;

  // Extension
  extensionConnected: boolean;
  setExtensionConnected: (connected: boolean) => void;
}

interface Notification {
  id: string;
  type: 'info' | 'success' | 'warning' | 'error';
  title: string;
  message: string;
  timestamp: number;
  duration?: number; // Auto-dismiss in ms
}

const generateId = () => Math.random().toString(36).substring(2, 9);

export const useUIStore = create<UIState>()(
  devtools(
    persist(
      (set, get) => ({
        // Initial state
        sidebarCollapsed: false,
        logPanelExpanded: false,
        logPanelHeight: 200,
        activeTab: 'agents',
        sidebarView: 'dashboard',
        showSettingsModal: false,
        showMissionModal: false,
        showNodeDetailsModal: false,
        notifications: [],

        // Sidebar actions
        toggleSidebar: () => {
          set(state => ({ sidebarCollapsed: !state.sidebarCollapsed }));
        },

        setSidebarCollapsed: (collapsed: boolean) => {
          set({ sidebarCollapsed: collapsed });
        },

        // Log panel actions
        toggleLogPanel: () => {
          set(state => ({ logPanelExpanded: !state.logPanelExpanded }));
        },

        setLogPanelExpanded: (expanded: boolean) => {
          set({ logPanelExpanded: expanded });
        },

        setLogPanelHeight: (height: number) => {
          set({ logPanelHeight: Math.max(100, Math.min(500, height)) });
        },

        // View actions
        setActiveTab: (tab: ViewTab) => {
          set({ activeTab: tab });
        },

        setSidebarView: (view: SidebarView) => {
          set({ sidebarView: view });
        },

        // Modal actions
        openSettingsModal: () => set({ showSettingsModal: true }),
        closeSettingsModal: () => set({ showSettingsModal: false }),
        openMissionModal: () => set({ showMissionModal: true }),
        closeMissionModal: () => set({ showMissionModal: false }),
        openNodeDetailsModal: () => set({ showNodeDetailsModal: true }),
        closeNodeDetailsModal: () => set({ showNodeDetailsModal: false }),

        // Notification actions
        addNotification: (notification) => {
          const newNotification: Notification = {
            ...notification,
            id: generateId(),
            timestamp: Date.now(),
          };

          set(state => ({
            notifications: [newNotification, ...state.notifications].slice(0, 10),
          }));

          // Auto-dismiss if duration is set
          if (notification.duration) {
            setTimeout(() => {
              get().removeNotification(newNotification.id);
            }, notification.duration);
          }
        },

        removeNotification: (id: string) => {
          set(state => ({
            notifications: state.notifications.filter(n => n.id !== id),
          }));
        },

        clearNotifications: () => {
          set({ notifications: [] });
        },

        // Extension actions
        extensionConnected: false,
        setExtensionConnected: (connected: boolean) => {
          set({ extensionConnected: connected });
        },
      }),
      {
        name: 'gotham-ui-store',
        partialize: (state) => ({
          sidebarCollapsed: state.sidebarCollapsed,
          logPanelHeight: state.logPanelHeight,
          activeTab: state.activeTab,
        }),
      }
    ),
    { name: 'ui-store' }
  )
);

// Selectors
export const selectActiveTab = (state: UIState) => state.activeTab;
export const selectLogPanelExpanded = (state: UIState) => state.logPanelExpanded;
export const selectNotifications = (state: UIState) => state.notifications;
