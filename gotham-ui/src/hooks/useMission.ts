/**
 * useMission Hook
 * Provides mission management functionality to components
 */

import { useCallback, useEffect } from 'react';
import { useMissionStore } from '@/stores';
import { StartMissionInput, MissionMode } from '@/services';

export interface UseMissionOptions {
  autoSubscribe?: boolean;
}

export function useMission(missionId?: string, options: UseMissionOptions = {}) {
  const { autoSubscribe = true } = options;

  const {
    currentMission,
    isLoading,
    error,
    logs,
    connectionStatus,
    startMission: startMissionAction,
    cancelMission: cancelMissionAction,
    pauseMission: pauseMissionAction,
    resumeMission: resumeMissionAction,
    fetchMission,
    subscribeToLogs,
    unsubscribeFromLogs,
    clearLogs,
  } = useMissionStore();

  // Auto-fetch and subscribe when missionId changes
  useEffect(() => {
    if (missionId) {
      fetchMission(missionId);

      if (autoSubscribe) {
        subscribeToLogs(missionId);
      }
    }

    return () => {
      if (autoSubscribe) {
        unsubscribeFromLogs();
      }
    };
  }, [missionId, autoSubscribe, fetchMission, subscribeToLogs, unsubscribeFromLogs]);

  // Start a new mission
  const startMission = useCallback(
    async (targetDomain: string, mode: MissionMode = 'AGGRESSIVE') => {
      const input: StartMissionInput = { targetDomain, mode };
      return await startMissionAction(input);
    },
    [startMissionAction]
  );

  // Cancel current mission
  const cancelMission = useCallback(async () => {
    return await cancelMissionAction();
  }, [cancelMissionAction]);

  // Pause current mission
  const pauseMission = useCallback(async () => {
    return await pauseMissionAction();
  }, [pauseMissionAction]);

  // Resume current mission
  const resumeMission = useCallback(async () => {
    return await resumeMissionAction();
  }, [resumeMissionAction]);

  // Check if mission is active
  const isActive = currentMission?.status === 'running';
  const isPaused = currentMission?.status === 'paused';
  const isCompleted = currentMission?.status === 'completed';
  const isFailed = currentMission?.status === 'failed';

  return {
    // State
    mission: currentMission,
    isLoading,
    error,
    logs,
    connectionStatus,

    // Computed
    isActive,
    isPaused,
    isCompleted,
    isFailed,
    hasLogs: logs.length > 0,

    // Actions
    startMission,
    cancelMission,
    pauseMission,
    resumeMission,
    clearLogs,
    subscribe: subscribeToLogs,
    unsubscribe: unsubscribeFromLogs,
  };
}

/**
 * useMissionList Hook
 * For listing and browsing missions
 */
export function useMissionList() {
  const {
    missions,
    missionsTotal,
    isLoading,
    error,
    fetchMissions,
    setCurrentMission,
  } = useMissionStore();

  const loadMissions = useCallback(
    (limit?: number, offset?: number) => {
      fetchMissions(limit, offset);
    },
    [fetchMissions]
  );

  useEffect(() => {
    loadMissions();
  }, [loadMissions]);

  return {
    missions,
    total: missionsTotal,
    isLoading,
    error,
    refresh: loadMissions,
    selectMission: setCurrentMission,
  };
}
