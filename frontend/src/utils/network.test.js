import { describe, expect, it } from 'vitest';

import { resolveApiBaseUrl, resolveServerUrl } from './network';

describe('network URL resolution', () => {
  it('keeps the configured localhost URL on the host machine itself', () => {
    expect(resolveServerUrl('http://localhost:5000', 'http://localhost:5173')).toBe('http://localhost:5000');
  });

  it('prefers the active browser origin for remote clients when the env URL is loopback', () => {
    expect(resolveServerUrl('http://localhost:5000', 'http://10.25.103.93:5173')).toBe('http://10.25.103.93:5173');
  });

  it('keeps the current https origin for proxied production clients when the env URL is loopback', () => {
    expect(resolveServerUrl('http://localhost:5000', 'https://poorup.wnusair.org')).toBe('https://poorup.wnusair.org');
  });

  it('falls back to the Vite proxy when no explicit API URL is configured', () => {
    expect(resolveApiBaseUrl(undefined, 'http://10.25.103.93:5173')).toBe('/api');
  });

  it('routes API calls through the current origin proxy for remote clients with loopback env config', () => {
    expect(resolveApiBaseUrl('http://localhost:5000', 'http://10.25.103.93:5173')).toBe('http://10.25.103.93:5173/api');
  });
});