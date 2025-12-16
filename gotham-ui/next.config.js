/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  async rewrites() {
    return [
      // Orchestrator API
      {
        source: '/api/v1/missions/:path*',
        destination: 'http://recon-orchestrator:8000/api/v1/missions/:path*',
      },
      // GraphQL endpoint
      {
        source: '/graphql',
        destination: 'http://bff-gateway:8080/graphql',
      },
      // SSE events for real-time updates
      {
        source: '/sse/:path*',
        destination: 'http://bff-gateway:8080/api/v1/sse/:path*',
      },
      // BFF Gateway API
      {
        source: '/bff/:path*',
        destination: 'http://bff-gateway:8080/api/v1/:path*',
      },
      // Graph Service direct access (for WebSocket fallback)
      {
        source: '/graph/:path*',
        destination: 'http://graph-service:8001/api/v1/:path*',
      },
    ]
  },
  images: {
    unoptimized: true,
  },
}

module.exports = nextConfig
