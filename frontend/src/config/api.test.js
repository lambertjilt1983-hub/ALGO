import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';

import { config } from './api';

describe('config.authFetch transport handling', () => {
  beforeEach(() => {
    config.clearApiBackoff();
    vi.restoreAllMocks();

    if (!globalThis.localStorage) {
      const store = new Map();
      globalThis.localStorage = {
        getItem: (key) => (store.has(key) ? store.get(key) : null),
        setItem: (key, value) => {
          store.set(String(key), String(value));
        },
        removeItem: (key) => {
          store.delete(String(key));
        },
        clear: () => {
          store.clear();
        },
      };
    }
  });

  afterEach(() => {
    config.clearApiBackoff();
  });

  it('does not force Content-Type for GET without body', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 200 }));
    globalThis.fetch = fetchMock;

    const res = await config.authFetch('/health', { includeAuth: false });

    expect(res.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const options = fetchMock.mock.calls[0][1] || {};
    expect(options?.headers?.['Content-Type']).toBeUndefined();
  });

  it('returns response on 502 and enters backoff instead of throwing', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 502, statusText: 'Bad Gateway' }));
    globalThis.fetch = fetchMock;

    const first = await config.authFetch('/health', { includeAuth: false });
    expect(first.status).toBe(502);
    expect(config.isApiBackoffActive()).toBe(true);

    const second = await config.authFetch('/health', { includeAuth: false });
    expect(second.status).toBe(503);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('applies long backoff window on 502 outage responses', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 502, statusText: 'Bad Gateway' }));
    globalThis.fetch = fetchMock;

    const first = await config.authFetch('/autotrade/status', { includeAuth: false });
    expect(first.status).toBe(502);

    const info = config.getApiBackoffInfo();
    expect(info.active).toBe(true);
    // Hard failures should jump to a long cooldown to avoid request storms.
    expect(Number(info.remainingMs || 0)).toBeGreaterThan(100000);
  });

  it('does not trigger global backoff for POST 429 business-rule errors', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 429, statusText: 'Too Many Requests' }));
    globalThis.fetch = fetchMock;

    const first = await config.authFetch('/autotrade/execute', {
      includeAuth: false,
      method: 'POST',
      body: JSON.stringify({ symbol: 'TEST' }),
    });
    expect(first.status).toBe(429);
    expect(config.isApiBackoffActive()).toBe(false);

    const second = await config.authFetch('/autotrade/execute', {
      includeAuth: false,
      method: 'POST',
      body: JSON.stringify({ symbol: 'TEST2' }),
    });
    expect(second.status).toBe(429);
    // Both calls should hit fetch because no global circuit-breaker is opened for POST 429.
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('suppresses repeated polling calls while backoff is active', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 503, statusText: 'Service Unavailable' }));
    globalThis.fetch = fetchMock;

    const first = await config.authFetch('/autotrade/status', { includeAuth: false });
    expect(first.status).toBe(503);

    const burst = await Promise.all(
      Array.from({ length: 5 }, () => config.authFetch('/autotrade/status', { includeAuth: false }))
    );

    burst.forEach((res) => {
      expect(res.status).toBe(503);
    });

    // Only the first call reaches fetch; the rest are short-circuited by backoff.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
