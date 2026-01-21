import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Enable standalone output for Docker
  output: "standalone",

  // Rewrites to proxy API requests to backend services
  // This allows the frontend to make requests to /graphql, /api, etc.
  // without CORS issues, and works in Docker where direct access isn't possible
  async rewrites() {
    // Get backend URLs from environment or use Docker defaults
    const bffGatewayUrl = process.env.BFF_GATEWAY_URL || "http://bff-gateway:8080";
    const orchestratorUrl = process.env.ORCHESTRATOR_URL || "http://recon-orchestrator:8000";
    const graphServiceUrl = process.env.GRAPH_SERVICE_URL || "http://graph-service:8001";

    return {
      // Apply before checking filesystem (for API-like routes)
      beforeFiles: [
        // GraphQL endpoint - proxy to BFF Gateway
        {
          source: "/graphql",
          destination: `${bffGatewayUrl}/graphql`,
        },
        // SSE events endpoint - proxy to BFF Gateway
        // More specific patterns first
        {
          source: "/api/v1/sse/events/:missionId",
          destination: `${bffGatewayUrl}/api/v1/sse/events/:missionId`,
        },
        {
          source: "/api/v1/sse/snapshot/:missionId",
          destination: `${bffGatewayUrl}/api/v1/sse/snapshot/:missionId`,
        },
        // BFF health and debug endpoints
        {
          source: "/bff/health",
          destination: `${bffGatewayUrl}/health`,
        },
        {
          source: "/bff/api/:path*",
          destination: `${bffGatewayUrl}/api/:path*`,
        },
      ],
      // Apply after checking filesystem
      afterFiles: [
        // Orchestrator API - for direct mission control
        {
          source: "/api/orchestrator/:path*",
          destination: `${orchestratorUrl}/api/v1/:path*`,
        },
        // Graph Service API - for direct graph queries
        {
          source: "/api/graph/:path*",
          destination: `${graphServiceUrl}/api/v1/:path*`,
        },
      ],
      // Fallback rewrites
      fallback: [],
    };
  },

  // Headers for WebSocket and SSE connections
  async headers() {
    return [
      {
        source: "/api/:path*",
        headers: [
          { key: "Access-Control-Allow-Origin", value: "*" },
          { key: "Access-Control-Allow-Methods", value: "GET, POST, PUT, DELETE, OPTIONS" },
          { key: "Access-Control-Allow-Headers", value: "Content-Type, Authorization" },
        ],
      },
    ];
  },
};

export default nextConfig;
