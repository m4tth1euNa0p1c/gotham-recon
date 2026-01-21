/**
 * Mission Store
 * Zustand store for mission state management
 */

import { create } from 'zustand';
import { devtools, subscribeWithSelector } from 'zustand/middleware';
import {
  MissionService,
  Mission,
  MissionMode,
  MissionStatus,
  LogEntry,
  StartMissionInput,
  ConnectionStatus
} from '@/services';

interface MissionState {
  // Current mission
  currentMission: Mission | null;
  isLoading: boolean;
  error: string | null;

  // Mission list
  missions: Mission[];
  missionsTotal: number;

  // Logs
  logs: LogEntry[];
  maxLogs: number;

  // Connection status
  connectionStatus: ConnectionStatus;

  // Refresh tracking
  lastRefresh: number | null;

  // Actions
  startMission: (input: StartMissionInput) => Promise<Mission | null>;
  cancelMission: () => Promise<boolean>;
  pauseMission: () => Promise<boolean>;
  resumeMission: () => Promise<boolean>;
  setCurrentMission: (mission: Mission | null) => void;
  updateMissionStatus: (missionId: string, status: MissionStatus) => void;
  fetchMission: (missionId: string) => Promise<void>;
  fetchMissions: (limit?: number, offset?: number) => Promise<void>;
  refreshMissions: () => Promise<void>;
  addLog: (log: LogEntry) => void;
  clearLogs: () => void;
  setConnectionStatus: (status: ConnectionStatus) => void;
  subscribeToLogs: (missionId: string) => void;
  unsubscribeFromLogs: () => void;
  reset: () => void;
}

const initialState = {
  currentMission: null,
  isLoading: false,
  error: null,
  missions: [],
  missionsTotal: 0,
  logs: [],
  maxLogs: 500,
  connectionStatus: 'disconnected' as ConnectionStatus,
  lastRefresh: null,
};

export const useMissionStore = create<MissionState>()(
  devtools(
    subscribeWithSelector((set, get) => ({
      ...initialState,

      startMission: async (input: StartMissionInput) => {
        set({ isLoading: true, error: null });

        try {
          const mission = await MissionService.startMission(input);

          if (mission) {
            set({
              currentMission: mission,
              isLoading: false,
              logs: [], // Clear previous logs
            });
            return mission;
          }

          set({ isLoading: false, error: 'Failed to start mission' });
          return null;
        } catch (error) {
          set({ isLoading: false, error: (error as Error).message });
          return null;
        }
      },

      cancelMission: async () => {
        const { currentMission } = get();
        if (!currentMission) return false;

        set({ isLoading: true });

        try {
          const success = await MissionService.cancelMission(currentMission.id);

          if (success) {
            set({
              currentMission: { ...currentMission, status: 'cancelled' },
              isLoading: false,
            });
          }

          return success;
        } catch (error) {
          set({ isLoading: false, error: (error as Error).message });
          return false;
        }
      },

      pauseMission: async () => {
        const { currentMission } = get();
        if (!currentMission) return false;

        try {
          const success = await MissionService.pauseMission(currentMission.id);

          if (success) {
            set({ currentMission: { ...currentMission, status: 'paused' } });
          }

          return success;
        } catch (error) {
          set({ error: (error as Error).message });
          return false;
        }
      },

      resumeMission: async () => {
        const { currentMission } = get();
        if (!currentMission) return false;

        try {
          const success = await MissionService.resumeMission(currentMission.id);

          if (success) {
            set({ currentMission: { ...currentMission, status: 'running' } });
          }

          return success;
        } catch (error) {
          set({ error: (error as Error).message });
          return false;
        }
      },

      setCurrentMission: (mission: Mission | null) => {
        set({ currentMission: mission });
      },

      updateMissionStatus: (missionId: string, status: MissionStatus) => {
        set(state => {
          // Update in missions list
          const updatedMissions = state.missions.map(m =>
            m.id === missionId ? { ...m, status } : m
          );

          // Update current mission if it matches
          const updatedCurrentMission =
            state.currentMission?.id === missionId
              ? { ...state.currentMission, status }
              : state.currentMission;

          return {
            missions: updatedMissions,
            currentMission: updatedCurrentMission
          };
        });
      },

      fetchMission: async (missionId: string) => {
        set({ isLoading: true, error: null });

        try {
          const mission = await MissionService.getMission(missionId);
          set({ currentMission: mission, isLoading: false });
        } catch (error) {
          set({ isLoading: false, error: (error as Error).message });
        }
      },

      fetchMissions: async (limit = 20, offset = 0) => {
        set({ isLoading: true, error: null });

        try {
          const result = await MissionService.getMissions(limit, offset);
          set({
            missions: result.items,
            missionsTotal: result.total,
            isLoading: false,
            lastRefresh: Date.now(),
          });
        } catch (error) {
          set({ isLoading: false, error: (error as Error).message });
        }
      },

      refreshMissions: async () => {
        // Non-blocking refresh (doesn't set isLoading)
        try {
          const result = await MissionService.getMissions(50);
          set({
            missions: result.items,
            missionsTotal: result.total,
            lastRefresh: Date.now(),
          });
        } catch (error) {
          console.error('Failed to refresh missions:', error);
        }
      },

      addLog: (log: LogEntry) => {
        const { logs, maxLogs } = get();
        const newLogs = [log, ...logs].slice(0, maxLogs);
        set({ logs: newLogs });
      },

      clearLogs: () => {
        set({ logs: [] });
      },

      setConnectionStatus: (status: ConnectionStatus) => {
        set({ connectionStatus: status });
      },

      subscribeToLogs: (missionId: string) => {
        // Set up log handler
        const unsubscribeLog = MissionService.onLog((log) => {
          get().addLog(log);
        });

        // Set up status handler
        const unsubscribeStatus = MissionService.onStatusChange((status) => {
          get().setConnectionStatus(status);
        });

        // Subscribe to WebSocket
        MissionService.subscribeToLogs(missionId);

        // Store unsubscribe functions (could be used for cleanup)
      },

      unsubscribeFromLogs: () => {
        MissionService.unsubscribeFromLogs();
        set({ connectionStatus: 'disconnected' });
      },

      reset: () => {
        MissionService.cleanup();
        set(initialState);
      },
    })),
    { name: 'mission-store' }
  )
);

// Selectors for optimized component updates
export const selectCurrentMission = (state: MissionState) => state.currentMission;
export const selectMissionStatus = (state: MissionState) => state.currentMission?.status;
export const selectLogs = (state: MissionState) => state.logs;
export const selectConnectionStatus = (state: MissionState) => state.connectionStatus;
export const selectIsLoading = (state: MissionState) => state.isLoading;
export const selectError = (state: MissionState) => state.error;
