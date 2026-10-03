'use client';

import { UserManager, WebStorageStateStore } from 'oidc-client-ts';

const authority = process.env.NEXT_PUBLIC_RISKWEAVE_OIDC_AUTHORITY;
const clientId = process.env.NEXT_PUBLIC_RISKWEAVE_OIDC_CLIENT_ID;
export const authenticationEnabled = Boolean(authority && clientId);
let manager: UserManager | undefined;

export function authManager(): UserManager {
  if (!authenticationEnabled || typeof window === 'undefined')
    throw new Error('Analyst sign-in is not configured.');
  manager ??= new UserManager({
    authority: authority!,
    client_id: clientId!,
    redirect_uri: `${window.location.origin}/auth/callback`,
    post_logout_redirect_uri: `${window.location.origin}/sign-in`,
    response_type: 'code',
    scope: 'openid profile ringsentinel:analyst',
    automaticSilentRenew: false,
    loadUserInfo: false,
    userStore: new WebStorageStateStore({ store: window.sessionStorage }),
    stateStore: new WebStorageStateStore({ store: window.sessionStorage }),
  });
  return manager;
}

export async function accessToken(): Promise<string | null> {
  if (!authenticationEnabled) return null;
  const user = await authManager().getUser();
  return user && !user.expired ? user.access_token : null;
}

export async function signOut(): Promise<void> {
  const auth = authManager();
  const user = await auth.getUser();
  await auth.removeUser();
  await auth.signoutRedirect({ id_token_hint: user?.id_token });
}
