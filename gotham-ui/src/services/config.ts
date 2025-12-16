/**
 * Service Configuration
 * Centralized configuration for all backend services
 * Uses relative paths to leverage Next.js rewrites for Docker compatibility
 */

// Detect if we're running in browser or server
const isBrowser = typeof window !== 'undefined';
const origin = isBrowser ? window.location.origin : '';

export const ServiceConfig = {
  // API Endpoints - Use relative paths for browser (Next.js rewrites handle routing)
  // Fall back to localhost for direct development
  BFF_GATEWAY: process.env.NEXT_PUBLIC_BFF_URL || (isBrowser ? origin : 'http://localhost:8080'),
  GRAPH_SERVICE: process.env.NEXT_PUBLIC_GRAPH_URL || 'http://localhost:8001',
  ORCHESTRATOR: process.env.NEXT_PUBLIC_ORCHESTRATOR_URL || (isBrowser ? `${origin}/api` : 'http://localhost:8000'),

  // GraphQL - Use relative path in browser to leverage Next.js rewrite
  GRAPHQL_HTTP: process.env.NEXT_PUBLIC_GRAPHQL_URL || (isBrowser ? `${origin}/graphql` : 'http://localhost:8080/graphql'),
  GRAPHQL_WS: process.env.NEXT_PUBLIC_GRAPHQL_WS_URL || (isBrowser ? `${origin.replace('http', 'ws')}/graphql` : 'ws://localhost:8080/graphql'),

  // WebSocket Endpoints - For SSE/WebSocket connections
  WS_GRAPH: process.env.NEXT_PUBLIC_GRAPH_WS_URL || 'ws://localhost:8001',
  WS_ORCHESTRATOR: process.env.NEXT_PUBLIC_ORCHESTRATOR_WS_URL || 'ws://localhost:8000',

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
