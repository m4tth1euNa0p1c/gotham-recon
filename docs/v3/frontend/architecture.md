# Frontend Architecture - Gotham UI v3.2.1

> **Documentation de l'interface utilisateur Next.js**
>
> Dernière mise à jour: Décembre 2025 (v3.2.1)

---

## Changelog v3.2.1

### Service Configuration - Direct URL Access

**Problème résolu:** L'UI ne pouvait pas communiquer avec les services backend via les rewrites Next.js en mode standalone.

**Solution:** Configuration directe vers les ports Docker exposés:

```typescript
// src/services/config.ts
export const ServiceConfig = {
  // Browser clients connect directly to exposed ports
  BFF_GATEWAY: isBrowser ? `http://${hostname}:8080` : 'http://bff-gateway:8080',
  GRAPHQL_HTTP: isBrowser ? `http://${hostname}:8080/graphql` : 'http://bff-gateway:8080/graphql',

  // SSE Events - absolute URL for browser
  SSE_EVENTS: (missionId: string) => {
    const base = isBrowser ? `http://${hostname}:8080` : 'http://bff-gateway:8080';
    return `${base}/api/v1/sse/events/${missionId}`;
  },
};
```

### Bug Fixes - Workflow Components

| Composant | Bug | Fix |
|-----------|-----|-----|
| **WorkflowHierarchy.tsx:391** | `asset.label.substring()` sur undefined | Ajout fallback: `asset.label \|\| asset.id \|\| 'Asset'` |
| **AssetMap.tsx:285** | `node.id.substring()` sur undefined | Ajout fallback: `node.id \|\| ''` |
| **AgentPipeline.tsx:141** | `agent.data.model.split()` sur undefined | Ajout fallback: `(agent.data.model \|\| '').split()` |

### Next.js Configuration

Ajout des rewrites pour proxy API (backup si direct access échoue):

```typescript
// next.config.ts
async rewrites() {
  return {
    beforeFiles: [
      { source: "/graphql", destination: `${bffGatewayUrl}/graphql` },
      { source: "/api/v1/sse/events/:missionId", destination: `${bffGatewayUrl}/api/v1/sse/events/:missionId` },
    ],
  };
}
```

---

## Changelog v3.2.0

### AssetGraph Improvements

| Composant | Modification |
|-----------|--------------|
| **NodeType enum** | Ajout `DNS_RECORD`, `SNAPSHOT`, `snapshot` |
| **AssetGraph.tsx** | Support complet AGENT_RUN, TOOL_CALL, DNS_RECORD |
| **workflowStore.ts** | Gestion événements SNAPSHOT pour SSE reconnexion |
| **graphStore.ts** | DNS_RECORD dans ALL_NODE_TYPES et statistiques |
| **types.ts** | Ajout `label?` à DomainEdge, SNAPSHOT à WorkflowEventType |

### Node Types Visualization

| Type | Couleur | Shape | Edges |
|------|---------|-------|-------|
| `AGENT_RUN` | #14b8a6 (teal) | round-rectangle | → DOMAIN |
| `TOOL_CALL` | #0ea5e9 (sky) | barrel | → AGENT_RUN ou DOMAIN |
| `DNS_RECORD` | #84cc16 (lime) | round-diamond | → SUBDOMAIN |
| `HYPOTHESIS` | #ec4899 (pink) | vee | → ENDPOINT ou HTTP_SERVICE |

### SSE Reconnection (P0.5)

Le `LiveStreamProvider` supporte maintenant:
- Tracking du `lastEventId` pour reconnexion
- Gestion des événements `SNAPSHOT` pour état initial
- Reconnexion automatique avec `?lastEventId=X`

---

## Vue d'Ensemble

Gotham UI est une application Next.js 14 avec App Router qui fournit une interface moderne pour visualiser et interagir avec les missions de reconnaissance.

### Stack Technique

| Technologie | Version | Usage |
|-------------|---------|-------|
| Next.js | 14.2+ | Framework React |
| React | 18+ | UI Components |
| TypeScript | 5+ | Type Safety |
| Zustand | 4.5+ | State Management |
| React Flow | 11+ | Graph Visualization |
| Framer Motion | 11+ | Animations |
| Tailwind CSS | 3.4+ | Styling |
| Lucide React | - | Icons |

---

## Structure du Projet

```
gotham-ui/
├── src/
│   ├── app/                      # App Router (pages)
│   │   ├── layout.tsx            # Layout principal
│   │   ├── page.tsx              # Dashboard (/)
│   │   ├── history/
│   │   │   └── page.tsx          # Historique des missions
│   │   ├── targets/
│   │   │   └── page.tsx          # Gestion des cibles
│   │   ├── reports/
│   │   │   └── page.tsx          # Exports de rapports
│   │   ├── analytics/
│   │   │   └── page.tsx          # Statistiques
│   │   ├── settings/
│   │   │   └── page.tsx          # Configuration
│   │   └── mission/
│   │       └── [id]/
│   │           ├── page.tsx      # Détails mission
│   │           ├── workflow/
│   │           │   └── page.tsx  # Visualisation workflow
│   │           ├── graph/
│   │           │   └── page.tsx  # Graphe d'assets
│   │           └── vulnerabilities/
│   │               └── page.tsx  # Findings sécurité
│   │
│   ├── components/               # Composants React
│   │   ├── dashboard/            # Composants dashboard
│   │   │   ├── Sidebar.tsx       # Navigation latérale
│   │   │   ├── MissionCard.tsx   # Carte mission
│   │   │   ├── NewMissionModal.tsx
│   │   │   └── StatsOverview.tsx
│   │   ├── workflow/             # Composants workflow
│   │   │   ├── WorkflowHierarchy.tsx
│   │   │   ├── AgentPipeline.tsx
│   │   │   ├── TracePanel.tsx
│   │   │   ├── WorkflowControls.tsx
│   │   │   ├── AssetMap.tsx
│   │   │   └── LiveStreamStatus.tsx
│   │   ├── assets/               # Composants graphe
│   │   │   ├── AssetGraph.tsx
│   │   │   ├── NodePanel.tsx
│   │   │   └── AssetTable.tsx
│   │   └── ui/                   # Composants génériques
│   │       ├── Button.tsx
│   │       ├── Card.tsx
│   │       └── Modal.tsx
│   │
│   ├── stores/                   # Zustand stores
│   │   ├── index.ts              # Export centralisé
│   │   ├── missionStore.ts       # État des missions
│   │   ├── graphStore.ts         # État du graphe
│   │   ├── workflowStore.ts      # État du workflow
│   │   └── uiStore.ts            # État UI
│   │
│   ├── providers/                # Context providers
│   │   └── LiveStreamProvider.tsx
│   │
│   ├── lib/                      # Utilitaires
│   │   ├── api.ts                # Client API
│   │   ├── graphql.ts            # Client GraphQL
│   │   └── utils.ts              # Helpers
│   │
│   └── types/                    # Types TypeScript
│       ├── mission.ts
│       ├── graph.ts
│       └── workflow.ts
│
├── public/                       # Assets statiques
├── tailwind.config.ts           # Config Tailwind
├── next.config.js               # Config Next.js
└── package.json
```

---

## Routes et Pages

### Structure des Routes

| Route | Page | Description |
|-------|------|-------------|
| `/` | Dashboard | Liste des missions, création |
| `/history` | History | Historique complet |
| `/targets` | Targets | Gestion des domaines cibles |
| `/reports` | Reports | Exports et téléchargements |
| `/analytics` | Analytics | Statistiques globales |
| `/settings` | Settings | Configuration |
| `/mission/[id]` | MissionDetail | Détails d'une mission |
| `/mission/[id]/workflow` | Workflow | Visualisation temps réel |
| `/mission/[id]/graph` | Graph | Graphe d'assets |
| `/mission/[id]/vulnerabilities` | Vulnerabilities | Findings sécurité |

### Layout Principal

```tsx
// src/app/layout.tsx
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-slate-950 text-white">
        <QueryClientProvider client={queryClient}>
          {children}
        </QueryClientProvider>
      </body>
    </html>
  );
}
```

---

## State Management (Zustand)

### Mission Store

```typescript
// src/stores/missionStore.ts
interface MissionState {
  missions: Mission[];
  currentMission: Mission | null;
  loading: boolean;
  error: string | null;

  // Actions
  fetchMissions: () => Promise<void>;
  fetchMission: (id: string) => Promise<void>;
  createMission: (input: MissionInput) => Promise<Mission>;
  cancelMission: (id: string) => Promise<void>;
  deleteMission: (id: string) => Promise<void>;
}

export const useMissionStore = create<MissionState>((set, get) => ({
  missions: [],
  currentMission: null,
  loading: false,
  error: null,

  fetchMissions: async () => {
    set({ loading: true });
    try {
      const data = await graphqlFetch<{ missions: MissionList }>(
        MISSIONS_QUERY
      );
      set({ missions: data.missions.items, loading: false });
    } catch (error) {
      set({ error: error.message, loading: false });
    }
  },

  fetchMission: async (id) => {
    const data = await graphqlFetch<{ mission: Mission }>(
      MISSION_QUERY,
      { id }
    );
    set({ currentMission: data.mission });
  },

  createMission: async (input) => {
    const data = await graphqlFetch<{ startMission: Mission }>(
      START_MISSION_MUTATION,
      { input }
    );
    const mission = data.startMission;
    set((state) => ({
      missions: [mission, ...state.missions],
    }));
    return mission;
  },
}));
```

### Graph Store

```typescript
// src/stores/graphStore.ts
interface GraphState {
  nodes: Map<string, GraphNode>;
  edges: Edge[];
  stats: GraphStats | null;
  loading: boolean;

  // Actions
  fetchGraph: (missionId: string) => Promise<void>;
  subscribe: (missionId: string) => void;
  unsubscribe: () => void;
  addNode: (node: GraphNode) => void;
  updateNode: (id: string, updates: Partial<GraphNode>) => void;
  addEdge: (edge: Edge) => void;
}

export const useGraphStore = create<GraphState>((set, get) => ({
  nodes: new Map(),
  edges: [],
  stats: null,
  loading: false,

  fetchGraph: async (missionId) => {
    set({ loading: true });

    // Fetch nodes
    const nodesData = await graphqlFetch(NODES_QUERY, { missionId });
    const nodesMap = new Map();
    nodesData.nodes.forEach((n) => nodesMap.set(n.id, n));

    // Fetch edges
    const edgesData = await graphqlFetch(EDGES_QUERY, { missionId });

    // Fetch stats
    const statsData = await graphqlFetch(STATS_QUERY, { missionId });

    set({
      nodes: nodesMap,
      edges: edgesData.edges,
      stats: statsData.graphStats,
      loading: false,
    });
  },

  subscribe: (missionId) => {
    // WebSocket subscription for real-time updates
    const ws = new WebSocket(`ws://localhost:8080/graphql`);
    // ... subscription logic
  },
}));
```

### Workflow Store

```typescript
// src/stores/workflowStore.ts
interface WorkflowState {
  agentRuns: Map<string, AgentRun>;
  toolCalls: Map<string, ToolCall>;
  selectedNodeId: string | null;
  connectionStatus: 'connecting' | 'connected' | 'disconnected' | 'error';

  // Actions
  setAgentRun: (run: AgentRun) => void;
  updateAgentRun: (id: string, updates: Partial<AgentRun>) => void;
  setToolCall: (call: ToolCall) => void;
  updateToolCall: (id: string, updates: Partial<ToolCall>) => void;
  selectNode: (id: string | null) => void;
  reset: () => void;
}

export const useWorkflowStore = create<WorkflowState>((set) => ({
  agentRuns: new Map(),
  toolCalls: new Map(),
  selectedNodeId: null,
  connectionStatus: 'disconnected',

  setAgentRun: (run) =>
    set((state) => {
      const newMap = new Map(state.agentRuns);
      newMap.set(run.id, run);
      return { agentRuns: newMap };
    }),

  updateAgentRun: (id, updates) =>
    set((state) => {
      const newMap = new Map(state.agentRuns);
      const existing = newMap.get(id);
      if (existing) {
        newMap.set(id, { ...existing, ...updates });
      }
      return { agentRuns: newMap };
    }),
}));
```

---

## Providers

### LiveStreamProvider

```tsx
// src/providers/LiveStreamProvider.tsx
interface LiveStreamContextValue {
  connect: (missionId: string) => void;
  disconnect: () => void;
  status: 'connecting' | 'connected' | 'disconnected' | 'error';
  isLive: boolean;
  isHistorical: boolean;
  loadHistoricalData: (missionId: string) => Promise<void>;
}

export const LiveStreamProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const eventSourceRef = useRef<EventSource | null>(null);

  const connect = useCallback((missionId: string) => {
    setStatus('connecting');

    // SSE connection for events
    const eventSource = new EventSource(
      `http://localhost:8080/api/v1/sse/events/${missionId}`
    );

    eventSource.onopen = () => {
      setStatus('connected');
    };

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      handleEvent(data);
    };

    eventSource.onerror = () => {
      setStatus('error');
    };

    eventSourceRef.current = eventSource;
  }, []);

  const disconnect = useCallback(() => {
    eventSourceRef.current?.close();
    setStatus('disconnected');
  }, []);

  return (
    <LiveStreamContext.Provider
      value={{ connect, disconnect, status, isLive: status === 'connected' }}
    >
      {children}
    </LiveStreamContext.Provider>
  );
};
```

---

## Composants Principaux

### Sidebar

```tsx
// src/components/dashboard/Sidebar.tsx
const navItems = [
  { path: '/', icon: Home, label: 'Dashboard' },
  { path: '/history', icon: FileSearch, label: 'History' },
  { path: '/targets', icon: Target, label: 'Targets' },
  { path: '/reports', icon: FileText, label: 'Reports' },
  { path: '/analytics', icon: BarChart3, label: 'Analytics' },
  { path: '/settings', icon: Settings, label: 'Settings' },
];

export default function Sidebar() {
  const pathname = usePathname();
  const params = useParams();
  const missionId = params.id as string;

  return (
    <aside className="w-64 bg-slate-900 border-r border-slate-800 p-4">
      {/* Logo */}
      <div className="flex items-center gap-2 mb-8">
        <Shield className="text-cyan-400" size={28} />
        <span className="text-xl font-bold">GOTHAM</span>
      </div>

      {/* Navigation */}
      <nav className="space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.path;

          return (
            <Link
              key={item.path}
              href={item.path}
              className={cn(
                'flex items-center gap-3 px-4 py-3 rounded-lg',
                isActive
                  ? 'bg-cyan-500/20 text-cyan-400'
                  : 'text-slate-400 hover:bg-slate-800'
              )}
            >
              <Icon size={18} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Mission navigation if on mission page */}
      {missionId && <MissionNav missionId={missionId} />}
    </aside>
  );
}
```

### WorkflowHierarchy

```tsx
// src/components/workflow/WorkflowHierarchy.tsx
export default function WorkflowHierarchy({ missionId }: Props) {
  const agentRuns = useWorkflowStore((s) => s.agentRuns);
  const toolCalls = useWorkflowStore((s) => s.toolCalls);
  const selectedNodeId = useWorkflowStore((s) => s.selectedNodeId);
  const selectNode = useWorkflowStore((s) => s.selectNode);

  // Build nodes for React Flow
  const nodes: Node[] = useMemo(() => {
    const result: Node[] = [];

    // Agent nodes
    agentRuns.forEach((agent) => {
      result.push({
        id: agent.id,
        type: 'agent',
        data: agent,
        position: { x: 0, y: 0 }, // Will be set by layout
      });
    });

    // Tool nodes
    toolCalls.forEach((tool) => {
      result.push({
        id: tool.id,
        type: 'tool',
        data: tool,
        position: { x: 0, y: 0 },
      });
    });

    return result;
  }, [agentRuns, toolCalls]);

  // Build edges
  const edges: Edge[] = useMemo(() => {
    const result: Edge[] = [];

    toolCalls.forEach((tool) => {
      if (tool.agentId) {
        result.push({
          id: `${tool.agentId}-${tool.id}`,
          source: tool.agentId,
          target: tool.id,
          type: 'smoothstep',
        });
      }
    });

    return result;
  }, [toolCalls]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      onNodeClick={(_, node) => selectNode(node.id)}
      fitView
    >
      <Background />
      <Controls />
      <MiniMap />
    </ReactFlow>
  );
}
```

---

## API Client

### GraphQL Client

```typescript
// src/lib/api.ts
const GRAPHQL_URL = process.env.NEXT_PUBLIC_GRAPHQL_URL || 'http://localhost:8080/graphql';

export async function graphqlFetch<T>(
  query: string,
  variables?: Record<string, any>
): Promise<T> {
  const response = await fetch(GRAPHQL_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query, variables }),
  });

  const { data, errors } = await response.json();

  if (errors) {
    throw new Error(errors[0].message);
  }

  return data;
}
```

### GraphQL Queries

```typescript
// src/lib/graphql.ts
export const MISSIONS_QUERY = `
  query GetMissions($limit: Int, $offset: Int) {
    missions(limit: $limit, offset: $offset) {
      items {
        id
        targetDomain
        mode
        status
        currentPhase
        createdAt
        progress
      }
      total
    }
  }
`;

export const MISSION_QUERY = `
  query GetMission($id: String!) {
    mission(id: $id) {
      id
      targetDomain
      mode
      status
      currentPhase
      createdAt
      progress
    }
  }
`;

export const START_MISSION_MUTATION = `
  mutation StartMission($input: MissionInput!) {
    startMission(input: $input) {
      id
      targetDomain
      status
    }
  }
`;

export const WORKFLOW_NODES_QUERY = `
  query GetWorkflowNodes($missionId: String!) {
    workflowNodes(missionId: $missionId, types: [AGENT_RUN, TOOL_CALL]) {
      id
      type
      properties
    }
  }
`;
```

---

## Configuration

### Variables d'Environnement

```bash
# .env.local
NEXT_PUBLIC_GRAPHQL_URL=http://localhost:8080/graphql
NEXT_PUBLIC_WS_URL=ws://localhost:8080/graphql
NEXT_PUBLIC_SSE_URL=http://localhost:8080/api/v1/sse
NEXT_PUBLIC_REST_URL=http://localhost:8000/api/v1
```

### Tailwind Configuration

```typescript
// tailwind.config.ts
import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        slate: {
          950: '#0a0a0f',
        },
      },
    },
  },
  plugins: [],
};

export default config;
```

---

## Build et Déploiement

### Développement

```bash
cd gotham-ui
npm install
npm run dev
```

### Production

```bash
npm run build
npm run start
```

### Docker

```dockerfile
# Dockerfile
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:18-alpine AS runner
WORKDIR /app
COPY --from=builder /app/next.config.js ./
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./

EXPOSE 3000
CMD ["npm", "start"]
```
