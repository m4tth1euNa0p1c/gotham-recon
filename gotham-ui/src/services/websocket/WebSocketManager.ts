/**
 * WebSocket Manager
 * Centralized WebSocket connection management with auto-reconnection
 */

import { ServiceConfig } from '../config';

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

export interface WebSocketMessage<T = unknown> {
  type: string;
  payload: T;
  timestamp?: string;
}

export interface WebSocketOptions {
  reconnect?: boolean;
  maxRetries?: number;
  retryInterval?: number;
  onOpen?: () => void;
  onClose?: (event: CloseEvent) => void;
  onError?: (error: Event) => void;
  onMessage?: (message: WebSocketMessage) => void;
  onStatusChange?: (status: ConnectionStatus) => void;
}

export class WebSocketConnection {
  private url: string;
  private socket: WebSocket | null = null;
  private options: WebSocketOptions;
  private retryCount: number = 0;
  private retryTimeout: ReturnType<typeof setTimeout> | null = null;
  private status: ConnectionStatus = 'disconnected';
  private messageHandlers: Map<string, Set<(payload: unknown) => void>> = new Map();

  constructor(url: string, options: WebSocketOptions = {}) {
    this.url = url;
    this.options = {
      reconnect: true,
      maxRetries: ServiceConfig.WS_MAX_RETRIES,
      retryInterval: ServiceConfig.WS_RECONNECT_INTERVAL,
      ...options,
    };
  }

  private log(level: 'debug' | 'info' | 'warn' | 'error', message: string, data?: unknown): void {
    if (!ServiceConfig.DEBUG && level === 'debug') return;
    const prefix = `[WS ${this.url}]`;
    console[level](prefix, message, data || '');
  }

  private setStatus(status: ConnectionStatus): void {
    this.status = status;
    this.options.onStatusChange?.(status);
  }

  connect(): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.log('debug', 'Already connected');
      return;
    }

    this.setStatus('connecting');
    this.log('info', 'Connecting...');

    try {
      this.socket = new WebSocket(this.url);

      this.socket.onopen = () => {
        this.log('info', 'Connected');
        this.retryCount = 0;
        this.setStatus('connected');
        this.options.onOpen?.();
      };

      this.socket.onclose = (event) => {
        this.log('info', 'Disconnected', { code: event.code, reason: event.reason });
        this.setStatus('disconnected');
        this.options.onClose?.(event);
        this.attemptReconnect();
      };

      this.socket.onerror = (error) => {
        this.log('error', 'Connection error', error);
        this.setStatus('error');
        this.options.onError?.(error);
      };

      this.socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as WebSocketMessage;
          this.log('debug', 'Message received', message);

          // Call global handler
          this.options.onMessage?.(message);

          // Call type-specific handlers
          const handlers = this.messageHandlers.get(message.type);
          if (handlers) {
            handlers.forEach(handler => handler(message.payload));
          }
        } catch (error) {
          this.log('error', 'Failed to parse message', { data: event.data, error });
        }
      };
    } catch (error) {
      this.log('error', 'Failed to create WebSocket', error);
      this.setStatus('error');
      this.attemptReconnect();
    }
  }

  private attemptReconnect(): void {
    if (!this.options.reconnect) return;
    if (this.retryCount >= (this.options.maxRetries || 10)) {
      this.log('error', 'Max retries reached, giving up');
      return;
    }

    this.retryCount++;
    const delay = this.options.retryInterval! * Math.pow(1.5, this.retryCount - 1);

    this.log('info', `Reconnecting in ${delay}ms (attempt ${this.retryCount})`);

    this.retryTimeout = setTimeout(() => {
      this.connect();
    }, delay);
  }

  disconnect(): void {
    if (this.retryTimeout) {
      clearTimeout(this.retryTimeout);
      this.retryTimeout = null;
    }

    if (this.socket) {
      this.socket.onclose = null; // Prevent reconnection
      this.socket.close();
      this.socket = null;
    }

    this.setStatus('disconnected');
    this.log('info', 'Disconnected manually');
  }

  send(message: WebSocketMessage | string): void {
    if (this.socket?.readyState !== WebSocket.OPEN) {
      this.log('warn', 'Cannot send, not connected');
      return;
    }

    const data = typeof message === 'string' ? message : JSON.stringify(message);
    this.socket.send(data);
    this.log('debug', 'Message sent', message);
  }

  on<T>(type: string, handler: (payload: T) => void): () => void {
    if (!this.messageHandlers.has(type)) {
      this.messageHandlers.set(type, new Set());
    }
    this.messageHandlers.get(type)!.add(handler as (payload: unknown) => void);

    // Return unsubscribe function
    return () => {
      this.messageHandlers.get(type)?.delete(handler as (payload: unknown) => void);
    };
  }

  off(type: string, handler?: (payload: unknown) => void): void {
    if (handler) {
      this.messageHandlers.get(type)?.delete(handler);
    } else {
      this.messageHandlers.delete(type);
    }
  }

  getStatus(): ConnectionStatus {
    return this.status;
  }

  isConnected(): boolean {
    return this.status === 'connected';
  }
}

/**
 * WebSocket Manager - Manages multiple connections
 */
export class WebSocketManager {
  private connections: Map<string, WebSocketConnection> = new Map();

  createConnection(id: string, url: string, options?: WebSocketOptions): WebSocketConnection {
    // Disconnect existing connection with same id
    this.disconnect(id);

    const connection = new WebSocketConnection(url, options);
    this.connections.set(id, connection);
    return connection;
  }

  getConnection(id: string): WebSocketConnection | undefined {
    return this.connections.get(id);
  }

  disconnect(id: string): void {
    const connection = this.connections.get(id);
    if (connection) {
      connection.disconnect();
      this.connections.delete(id);
    }
  }

  disconnectAll(): void {
    this.connections.forEach(connection => connection.disconnect());
    this.connections.clear();
  }

  getStatus(id: string): ConnectionStatus | undefined {
    return this.connections.get(id)?.getStatus();
  }
}

// Singleton instance
export const wsManager = new WebSocketManager();
