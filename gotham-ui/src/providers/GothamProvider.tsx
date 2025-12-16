'use client';

/**
 * Gotham Provider
 * Root provider component that initializes services and provides context
 */

import React, { createContext, useContext, useEffect, useCallback, ReactNode } from 'react';
import { useMissionStore, useGraphStore, useUIStore } from '@/stores';
import { MissionService, GraphService, wsManager } from '@/services';

interface GothamContextValue {
  // Global actions
  cleanup: () => void;
  notify: (type: 'info' | 'success' | 'warning' | 'error', title: string, message: string) => void;
}

const GothamContext = createContext<GothamContextValue | null>(null);

interface GothamProviderProps {
  children: ReactNode;
}

export function GothamProvider({ children }: GothamProviderProps) {
  const missionReset = useMissionStore(state => state.reset);
  const graphReset = useGraphStore(state => state.reset);
  const addNotification = useUIStore(state => state.addNotification);

  // Cleanup all services and stores
  const cleanup = useCallback(() => {
    wsManager.disconnectAll();
    MissionService.cleanup();
    GraphService.cleanup();
    missionReset();
    graphReset();
  }, [missionReset, graphReset]);

  // Notify helper
  const notify = useCallback(
    (type: 'info' | 'success' | 'warning' | 'error', title: string, message: string) => {
      addNotification({
        type,
        title,
        message,
        duration: type === 'error' ? undefined : 5000,
      });
    },
    [addNotification]
  );

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cleanup();
    };
  }, [cleanup]);

  // Handle page visibility changes
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden) {
        // Page is hidden, could pause non-essential operations
      } else {
        // Page is visible again, could resume operations
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, []);

  // Handle online/offline events
  useEffect(() => {
    const handleOnline = () => {
      notify('success', 'Connection Restored', 'You are back online');
    };

    const handleOffline = () => {
      notify('warning', 'Connection Lost', 'You are currently offline');
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [notify]);

  const value: GothamContextValue = {
    cleanup,
    notify,
  };

  return (
    <GothamContext.Provider value={value}>
      {children}
    </GothamContext.Provider>
  );
}

// Hook to use Gotham context
export function useGotham(): GothamContextValue {
  const context = useContext(GothamContext);
  if (!context) {
    throw new Error('useGotham must be used within a GothamProvider');
  }
  return context;
}

// HOC to wrap components that need Gotham context
export function withGotham<P extends object>(
  WrappedComponent: React.ComponentType<P>
): React.FC<P> {
  const WithGothamComponent: React.FC<P> = (props) => {
    return (
      <GothamProvider>
        <WrappedComponent {...props} />
      </GothamProvider>
    );
  };

  WithGothamComponent.displayName = `withGotham(${WrappedComponent.displayName || WrappedComponent.name || 'Component'})`;

  return WithGothamComponent;
}
