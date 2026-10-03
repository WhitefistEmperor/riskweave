import type { NextConfig } from 'next';

const production = process.env.RINGSENTINEL_ENVIRONMENT === 'production';
const target = process.env.RINGSENTINEL_API_PROXY_TARGET;
const oidcAuthority = process.env.NEXT_PUBLIC_RISKWEAVE_OIDC_AUTHORITY;
const oidcClientId = process.env.NEXT_PUBLIC_RISKWEAVE_OIDC_CLIENT_ID;
if (Boolean(oidcAuthority) !== Boolean(oidcClientId))
  throw new Error('OIDC authority and client ID must be configured together');
if (oidcAuthority) {
  let issuer: URL;
  try {
    issuer = new URL(oidcAuthority);
  } catch {
    throw new Error('OIDC authority must be a valid issuer URL');
  }
  if (
    issuer.username ||
    issuer.password ||
    issuer.search ||
    issuer.hash ||
    (production
      ? issuer.protocol !== 'https:'
      : !['http:', 'https:'].includes(issuer.protocol))
  )
    throw new Error(
      'OIDC authority requires a trusted HTTP(S) issuer without credentials',
    );
}
if (production) {
  if (!target)
    throw new Error('Production requires RINGSENTINEL_API_PROXY_TARGET');
  let parsed: URL;
  try {
    parsed = new URL(target);
  } catch {
    throw new Error('API proxy target must be a valid HTTP(S) origin');
  }
  if (
    !['http:', 'https:'].includes(parsed.protocol) ||
    parsed.username ||
    parsed.password ||
    parsed.pathname !== '/' ||
    parsed.search ||
    parsed.hash
  ) {
    throw new Error(
      'API proxy target must be an explicit HTTP(S) origin without credentials',
    );
  }
  if (process.env.NEXT_PUBLIC_RINGSENTINEL_API_BASE_URL) {
    throw new Error(
      'Production browser API requests must use the authenticated same-origin gateway',
    );
  }
}

const nextConfig: NextConfig = {
  output: process.env.RINGSENTINEL_STANDALONE === 'true' ? 'standalone' : undefined,
  poweredByHeader: false,
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'Referrer-Policy', value: 'no-referrer' },
          {
            key: 'Permissions-Policy',
            value: 'camera=(), microphone=(), geolocation=()',
          },
          {
            key: 'Content-Security-Policy',
            value: "frame-ancestors 'none'; object-src 'none'; base-uri 'self'",
          },
          ...(production
            ? [{ key: 'Strict-Transport-Security', value: 'max-age=31536000' }]
            : []),
        ],
      },
    ];
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${target ?? 'http://127.0.0.1:8000'}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
