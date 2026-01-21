/**
 * Service Configuration
 * Centralized configuration for all backend services
 *
 * In Docker deployments:
 * - UI container runs on port 3000
 * - BFF Gateway on port 8080 (exposed to host)
 * - Graph Service on port 8001 (exposed to host)
 * - Orchestrator on port 8000 (exposed to host)
 *
 * Browser clients connect directly to localhost:PORT for each service.
 * This avoids the need for complex proxying.
 */

// Detect if we're running in browser or server
const isBrowser = typeof window !== 'undefined';

// Get the hostname - in Docker, browser sees localhost; server sees container names
const getHostname = (): string => {
  if (isBrowser) {
    // In browser, use current hostname (typically localhost)
    return window.location.hostname;
  }
  return 'localhost';
};

// Helper to get WebSocket URL
const getWsUrl = (httpUrl: string): string => {
  return httpUrl.replace('http://', 'ws://').replace('https://', 'wss://');
};

// Base URLs for services
// In browser: connect directly to exposed ports on localhost
// On server: connect via Docker internal network
const hostname = getHostname();

export const ServiceConfig = {
  // BFF Gateway - handles GraphQL and SSE
  BFF_GATEWAY: process.env.NEXT_PUBLIC_BFF_URL ||
    (isBrowser ? `http://${hostname}:8080` : 'http://bff-gateway:8080'),

  // Graph Service - direct access for WebSocket
  GRAPH_SERVICE: process.env.NEXT_PUBLIC_GRAPH_URL ||
    (isBrowser ? `http://${hostname}:8001` : 'http://graph-service:8001'),

  // Orchestrator - direct access for WebSocket
  ORCHESTRATOR: process.env.NEXT_PUBLIC_ORCHESTRATOR_URL ||
    (isBrowser ? `http://${hostname}:8000` : 'http://recon-orchestrator:8000'),

  // GraphQL HTTP endpoint - connects to BFF Gateway
  GRAPHQL_HTTP: process.env.NEXT_PUBLIC_GRAPHQL_URL ||
    (isBrowser ? `http://${hostname}:8080/graphql` : 'http://bff-gateway:8080/graphql'),

  // GraphQL WebSocket - connects to BFF Gateway
  GRAPHQL_WS: process.env.NEXT_PUBLIC_GRAPHQL_WS_URL ||
    (isBrowser ? `ws://${hostname}:8080/graphql` : 'ws://bff-gateway:8080/graphql'),

  // SSE Events endpoint - connects to BFF Gateway
  SSE_EVENTS: (missionId: string) => {
    const base = process.env.NEXT_PUBLIC_BFF_URL ||
      (isBrowser ? `http://${hostname}:8080` : 'http://bff-gateway:8080');
    return `${base}/api/v1/sse/events/${missionId}`;
  },

  // WebSocket Endpoints - For direct WebSocket connections
  WS_GRAPH: process.env.NEXT_PUBLIC_GRAPH_WS_URL ||
    (isBrowser ? `ws://${hostname}:8001` : 'ws://graph-service:8001'),
  WS_ORCHESTRATOR: process.env.NEXT_PUBLIC_ORCHESTRATOR_WS_URL ||
    (isBrowser ? `ws://${hostname}:8000` : 'ws://recon-orchestrator:8000'),

  // Feature Flags
  ENABLE_LIVE_MODE: process.env.NEXT_PUBLIC_ENABLE_LIVE_MODE !== 'false',
  DEBUG: process.env.NEXT_PUBLIC_DEBUG === 'true',

  // Timeouts & Retries
  REQUEST_TIMEOUT: 30000,
  WS_RECONNECT_INTERVAL: 3000,
  WS_MAX_RETRIES: 10,
  POLLING_INTERVAL: 5000,
} as const;

export type ServiceConfigType = typeof ServiceConfig;
