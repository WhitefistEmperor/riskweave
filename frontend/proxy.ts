import { randomBytes } from 'node:crypto';
import { NextRequest, NextResponse } from 'next/server';
import { connectionSources, contentSecurityPolicy } from './lib/security-policy.mjs';

const origins = connectionSources(
  process.env.NEXT_PUBLIC_RISKWEAVE_OIDC_AUTHORITY,
  process.env.RINGSENTINEL_OIDC_CONNECT_ORIGINS,
  process.env.RINGSENTINEL_ENVIRONMENT === 'production',
);

export function proxy(request: NextRequest) {
  const nonce = randomBytes(18).toString('base64');
  const policy = contentSecurityPolicy(nonce, origins, process.env.NODE_ENV === 'development');
  const headers = new Headers(request.headers);
  // Replace caller values before Next extracts the nonce for its rendering scripts.
  headers.set('x-nonce', nonce);
  headers.set('Content-Security-Policy', policy);
  const response = NextResponse.next({ request: { headers } });
  response.headers.set('Content-Security-Policy', policy);
  response.headers.set('Cache-Control', 'private, no-store');
  return response;
}

export const config = {
  matcher: ['/((?!api(?:/|$)|_next/|favicon\\.svg$).*)'],
};
