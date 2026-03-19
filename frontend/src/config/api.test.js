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
