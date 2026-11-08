'use client';

import { createClient, type SupabaseClient } from '@supabase/supabase-js';

/**
 * Supabase Auth OAuth-server consent support. Only used when the configured OIDC
 * authority is a Supabase project (`https://<ref>.supabase.co/auth/v1`); the
 * publishable key is public by design and grants nothing without a user session.
 */
const authority = process.env.NEXT_PUBLIC_RISKWEAVE_OIDC_AUTHORITY ?? '';
const publishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? '';

export function supabaseProjectUrl(value = authority): string | null {
  try {
    const url = new URL(value);
    if (
      url.protocol !== 'https:' ||
      !/^[a-z0-9]+\.supabase\.co$/i.test(url.hostname) ||
      url.pathname.replace(/\/$/, '') !== '/auth/v1' ||
      url.search ||
      url.hash ||
      url.username ||
      url.password
    )
      return null;
    return url.origin;
  } catch {
    return null;
  }
}

export const consentEnabled = Boolean(supabaseProjectUrl() && publishableKey);
let client: SupabaseClient | undefined;

export function consentClient(): SupabaseClient {
  const url = supabaseProjectUrl();
  if (!url || !publishableKey || typeof window === 'undefined')
    throw new Error('Supabase consent is not configured.');
  client ??= createClient(url, publishableKey, {
    auth: {
      // Tab-scoped, matching the console's own session storage policy.
      storage: window.sessionStorage,
      persistSession: true,
      autoRefreshToken: false,
      detectSessionInUrl: false,
      flowType: 'pkce',
    },
  });
  return client;
}

/** Only this console's own callback may receive an authorization code from this page. */
export function trustedRedirect(value: string, origin: string): string | null {
  try {
    const url = new URL(value);
    return url.origin === origin && url.pathname === '/auth/callback'
      ? url.toString()
      : null;
  } catch {
    return null;
  }
}
