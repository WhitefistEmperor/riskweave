/** Explicit browser connection origins; no wildcard provider discovery. */
export function connectionSources(authority, extra = '', production = false) {
  let origins;
  try {
    origins = extra ? JSON.parse(extra) : [];
    if (!Array.isArray(origins) || origins.length > 8) throw new Error();
    if (authority) origins.unshift(new URL(authority).origin);
    return [...new Set(origins.map(value => {
      if (typeof value !== 'string') throw new Error();
      const url = new URL(value);
      if (!/^(?:[a-z0-9.-]+|\[[a-f0-9:]+\])$/i.test(url.hostname) ||
          url.username || url.password || url.pathname !== '/' || url.search ||
          url.hash || (production ? url.protocol !== 'https:' :
            !['https:', 'http:'].includes(url.protocol))) throw new Error();
      return url.origin;
    }))];
  } catch {
    throw new Error('OIDC connection origins must be explicit HTTP(S) origins');
  }
}

/** Scripts require a fresh request nonce; styles allow UI libraries' inline positioning. */
export function contentSecurityPolicy(nonce, origins, development = false) {
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${development ? " 'unsafe-eval'" : ''}`,
    "script-src-attr 'none'",
    "style-src 'self' 'unsafe-inline'",
    `connect-src 'self' ${origins.join(' ')}${development ? ' ws: wss:' : ''}`.trim(),
    "img-src 'self' data: blob:",
    "font-src 'self'",
    "worker-src 'self' blob:",
    "object-src 'none'",
    "frame-src 'none'",
    "frame-ancestors 'none'",
    "base-uri 'none'",
    "form-action 'self'",
  ].join('; ');
}
