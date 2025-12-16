/**
 * Layout Service
 * Handles workflow layout persistence (backend API + localStorage fallback)
 */

import { ServiceConfig } from './config';

export interface NodePositions {
  [nodeId: string]: { x: number; y: number };
}

export interface WorkflowLayout {
  positions: NodePositions;
  zoom: number;
  pan: { x: number; y: number };
  updatedAt?: string;
}

const STORAGE_KEY_PREFIX = 'gotham-workflow-layout-';

class LayoutServiceClass {
  /**
   * Save layout to backend API with localStorage fallback
   */
  async saveLayout(missionId: string, layout: WorkflowLayout): Promise<boolean> {
    // Always save to localStorage as backup
    this.saveToLocalStorage(missionId, layout);

    try {
      const response = await fetch(
        `${ServiceConfig.BFF_GATEWAY}/api/v1/layouts/${missionId}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            positions: layout.positions,
            zoom: layout.zoom,
            pan: layout.pan,
          }),
        }
      );

      if (response.ok) {
        console.log('[LayoutService] Saved to backend:', missionId);
        return true;
      }

      console.warn('[LayoutService] Backend save failed, using localStorage');
      return false;
    } catch (error) {
      console.warn('[LayoutService] Backend save error, using localStorage:', error);
      return false;
    }
  }

  /**
   * Load layout from backend API with localStorage fallback
   */
  async loadLayout(missionId: string): Promise<WorkflowLayout | null> {
    try {
      const response = await fetch(
        `${ServiceConfig.BFF_GATEWAY}/api/v1/layouts/${missionId}`
      );

      if (response.ok) {
        const data = await response.json();
        if (data.positions && Object.keys(data.positions).length > 0) {
          console.log('[LayoutService] Loaded from backend:', missionId);
          return {
            positions: data.positions,
            zoom: data.zoom || 1.0,
            pan: data.pan || { x: 0, y: 0 },
            updatedAt: data.updated_at,
          };
        }
      }
    } catch (error) {
      console.warn('[LayoutService] Backend load error:', error);
    }

    // Fallback to localStorage
    const localLayout = this.loadFromLocalStorage(missionId);
    if (localLayout) {
      console.log('[LayoutService] Loaded from localStorage:', missionId);
      return localLayout;
    }

    return null;
  }

  /**
   * Save layout to localStorage
   */
  private saveToLocalStorage(missionId: string, layout: WorkflowLayout): void {
    try {
      const key = `${STORAGE_KEY_PREFIX}${missionId}`;
      localStorage.setItem(key, JSON.stringify({
        ...layout,
        updatedAt: new Date().toISOString(),
      }));
    } catch (error) {
      console.warn('[LayoutService] localStorage save error:', error);
    }
  }

  /**
   * Load layout from localStorage
   */
  private loadFromLocalStorage(missionId: string): WorkflowLayout | null {
    try {
      const key = `${STORAGE_KEY_PREFIX}${missionId}`;
      const data = localStorage.getItem(key);
      if (data) {
        return JSON.parse(data);
      }
    } catch (error) {
      console.warn('[LayoutService] localStorage load error:', error);
    }
    return null;
  }

  /**
   * Clear layout for a mission
   */
  async clearLayout(missionId: string): Promise<void> {
    // Clear localStorage
    try {
      const key = `${STORAGE_KEY_PREFIX}${missionId}`;
      localStorage.removeItem(key);
    } catch (error) {
      console.warn('[LayoutService] localStorage clear error:', error);
    }

    // Note: Backend doesn't have a delete endpoint yet
    // Could be added if needed
  }

  /**
   * Get default layout for new workflows
   */
  getDefaultLayout(): WorkflowLayout {
    return {
      positions: {},
      zoom: 1.0,
      pan: { x: 0, y: 0 },
    };
  }

  /**
   * Merge saved positions with current node IDs
   * (handles case where new nodes have been added)
   */
  mergePositions(
    savedPositions: NodePositions,
    currentNodeIds: string[]
  ): NodePositions {
    const merged: NodePositions = {};

    // Keep saved positions for nodes that still exist
    for (const nodeId of currentNodeIds) {
      if (savedPositions[nodeId]) {
        merged[nodeId] = savedPositions[nodeId];
      }
    }

    return merged;
  }
}

// Singleton instance
export const LayoutService = new LayoutServiceClass();
