const LOOPBACK_HOSTNAMES = new Set(['localhost', '127.0.0.1', '0.0.0.0', '::1', '[::1]']);

export function isLoopbackHostname(hostname) {
  return LOOPBACK_HOSTNAMES.has((hostname || '').trim().toLowerCase());
}

export function resolveServerUrl(explicitUrl, currentOrigin = window?.location?.origin) {
  const candidate = explicitUrl?.trim();
  if (!candidate) {
    return undefined;
  }

  try {
    const resolved = new URL(candidate, currentOrigin || undefined);
    const current = currentOrigin ? new URL(currentOrigin) : null;

    if (current && !isLoopbackHostname(current.hostname) && isLoopbackHostname(resolved.hostname)) {
      return current.origin;
    }

    return resolved.origin;
  } catch {
    return candidate;
  }
}

export function resolveApiBaseUrl(explicitUrl, currentOrigin = window?.location?.origin) {
  const serverUrl = resolveServerUrl(explicitUrl, currentOrigin);
  return serverUrl ? `${serverUrl}/api` : '/api';
}