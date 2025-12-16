/**
 * Base API Client
 * Provides HTTP request handling with error handling, retries, and logging
 */

import { ServiceConfig } from '../config';

export interface ApiError {
  code: string;
  message: string;
  status?: number;
  details?: unknown;
}

export interface ApiResponse<T> {
  data: T | null;
  error: ApiError | null;
  success: boolean;
}

export interface RequestOptions extends RequestInit {
  timeout?: number;
  retries?: number;
  retryDelay?: number;
}

export class BaseClient {
  protected baseUrl: string;
  protected defaultHeaders: Record<string, string>;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
    this.defaultHeaders = {
      'Content-Type': 'application/json',
    };
  }

  protected log(level: 'debug' | 'info' | 'warn' | 'error', message: string, data?: unknown): void {
    if (!ServiceConfig.DEBUG && level === 'debug') return;

    const timestamp = new Date().toISOString();
    const prefix = `[${timestamp}] [API]`;

    switch (level) {
      case 'debug':
        console.debug(prefix, message, data);
        break;
      case 'info':
        console.info(prefix, message, data);
        break;
      case 'warn':
        console.warn(prefix, message, data);
        break;
      case 'error':
        console.error(prefix, message, data);
        break;
    }
  }

  protected async fetchWithTimeout(
    url: string,
    options: RequestOptions
  ): Promise<Response> {
    const { timeout = ServiceConfig.REQUEST_TIMEOUT, ...fetchOptions } = options;

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
      const response = await fetch(url, {
        ...fetchOptions,
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      return response;
    } catch (error) {
      clearTimeout(timeoutId);
      throw error;
    }
  }

  protected async fetchWithRetry(
    url: string,
    options: RequestOptions
  ): Promise<Response> {
    const { retries = 3, retryDelay = 1000, ...fetchOptions } = options;

    let lastError: Error | null = null;

    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        const response = await this.fetchWithTimeout(url, fetchOptions);

        if (response.ok || attempt === retries) {
          return response;
        }

        // Retry on 5xx errors
        if (response.status >= 500) {
          this.log('warn', `Request failed with ${response.status}, retrying...`, { attempt, url });
          await this.delay(retryDelay * Math.pow(2, attempt));
          continue;
        }

        return response;
      } catch (error) {
        lastError = error as Error;

        if (attempt < retries) {
          this.log('warn', `Request error, retrying...`, { attempt, url, error: lastError.message });
          await this.delay(retryDelay * Math.pow(2, attempt));
        }
      }
    }

    throw lastError || new Error('Request failed after retries');
  }

  protected delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  protected async request<T>(
    method: string,
    path: string,
    body?: unknown,
    options: RequestOptions = {}
  ): Promise<ApiResponse<T>> {
    const url = `${this.baseUrl}${path}`;

    this.log('debug', `${method} ${path}`, body);

    try {
      const response = await this.fetchWithRetry(url, {
        method,
        headers: { ...this.defaultHeaders, ...options.headers },
        body: body ? JSON.stringify(body) : undefined,
        ...options,
      });

      if (!response.ok) {
        const errorBody = await response.text();
        let errorData: unknown;

        try {
          errorData = JSON.parse(errorBody);
        } catch {
          errorData = errorBody;
        }

        this.log('error', `Request failed: ${response.status}`, { url, errorData });

        return {
          data: null,
          error: {
            code: `HTTP_${response.status}`,
            message: response.statusText,
            status: response.status,
            details: errorData,
          },
          success: false,
        };
      }

      const data = await response.json();
      this.log('debug', `Response received`, { url, data });

      return {
        data: data as T,
        error: null,
        success: true,
      };
    } catch (error) {
      const err = error as Error;
      this.log('error', `Request exception: ${err.message}`, { url });

      return {
        data: null,
        error: {
          code: 'NETWORK_ERROR',
          message: err.message,
          details: err,
        },
        success: false,
      };
    }
  }

  async get<T>(path: string, options?: RequestOptions): Promise<ApiResponse<T>> {
    return this.request<T>('GET', path, undefined, options);
  }

  async post<T>(path: string, body?: unknown, options?: RequestOptions): Promise<ApiResponse<T>> {
    return this.request<T>('POST', path, body, options);
  }

  async put<T>(path: string, body?: unknown, options?: RequestOptions): Promise<ApiResponse<T>> {
    return this.request<T>('PUT', path, body, options);
  }

  async delete<T>(path: string, options?: RequestOptions): Promise<ApiResponse<T>> {
    return this.request<T>('DELETE', path, undefined, options);
  }
}
