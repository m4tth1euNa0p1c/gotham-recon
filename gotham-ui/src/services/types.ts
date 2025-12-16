/**
 * Gotham Domain Types
 * Defines strict types for Assets, Workflow, and Relations
 */

export enum NodeType {
    // Core Assets
    DOMAIN = 'DOMAIN',
    SUBDOMAIN = 'SUBDOMAIN',
    IP = 'IP',
    HTTP_SERVICE = 'HTTP_SERVICE',
    ENDPOINT = 'ENDPOINT',
    PARAMETER = 'PARAMETER',
    DNS_RECORD = 'DNS_RECORD',

    // Technologies & Findings
    TECHNOLOGY = 'TECHNOLOGY',
    CREDENTIAL = 'CREDENTIAL',
    FINDING = 'FINDING',

    // Security
    HYPOTHESIS = 'HYPOTHESIS',
    VULNERABILITY = 'VULNERABILITY',
    ATTACK_PATH = 'ATTACK_PATH',

    // Workflow
    AGENT_RUN = 'AGENT_RUN',
    TOOL_CALL = 'TOOL_CALL',
    LLM_REASONING = 'LLM_REASONING'
}

export enum EdgeType {
    TRIGGERS = 'TRIGGERS',
    USES_TOOL = 'USES_TOOL',
    PRODUCES = 'PRODUCES',
    REFINES = 'REFINES',
    HAS_PARAM = 'HAS_PARAM',
    HAS_HYPOTHESIS = 'HAS_HYPOTHESIS',
    HAS_VULNERABILITY = 'HAS_VULNERABILITY',
    TARGETS = 'TARGETS',

    // Generic/Legacy
    LINKS_TO = 'LINKS_TO'
}

export enum MissionPhase {
    OSINT = 'OSINT',
    ACTIVE = 'ACTIVE',
    INTEL = 'INTEL',
    VERIF = 'VERIF',
    PLANNER = 'PLANNER',
    REPORT = 'REPORT'
}

export interface DomainNode {
    id: string;
    type: NodeType;
    label: string;
    data: Record<string, any>;
    metadata: {
        timestamp: string;
        source?: string;
        phase?: MissionPhase | string;
        risk_score?: number;
    };
}

export interface DomainEdge {
    id: string;
    source: string;
    target: string;
    type: EdgeType;
    label?: string;
    metadata?: Record<string, any>;
}

export type WorkflowEventType =
    | 'agent_started'
    | 'agent_finished'
    | 'tool_called'
    | 'tool_finished'
    | 'asset_mutation'
    | 'SNAPSHOT'
    | 'snapshot';

export interface WorkflowEvent {
    type: WorkflowEventType;
    timestamp: string;
    missionId: string;
    data: any;
}

export type WorkflowNodeStatus = 'pending' | 'running' | 'completed' | 'error';

export interface TraceEntry {
    id: string;
    type: 'agent_started' | 'agent_finished' | 'tool_called' | 'tool_finished' | 'asset_mutation';
    nodeId: string;
    message: string;
    timestamp: string;
    metadata: Record<string, any>;
}
