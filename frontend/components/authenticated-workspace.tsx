'use client';

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react';
import Link from 'next/link';
import { authenticationEnabled, authManager, signOut } from '@/lib/auth';

type Access =
  | 'checking'
  | 'active'
  | 'expired'
  | 'signed-out'
  | 'logout-failed';
const SessionContext = createContext<(() => void) | null>(null);

export function useWorkspaceSignOut() {
  return useContext(SessionContext);
}

export function AuthenticatedWorkspace({ children }: { children: ReactNode }) {
  const [access, setAccess] = useState<Access>(
    authenticationEnabled ? 'checking' : 'active',
  );
  useEffect(() => {
    if (!authenticationEnabled) return;
    let active = true;
    const auth = authManager();
    const expired = () => {
      if (active) setAccess('expired');
    };
    const unloaded = () => {
      if (active)
        setAccess((value) => (value === 'expired' ? value : 'signed-out'));
    };
    const stopExpired = auth.events.addAccessTokenExpired(expired);
    const stopUnloaded = auth.events.addUserUnloaded(unloaded);
    void auth
      .getUser()
      .then((user) => {
        if (active) setAccess(user && !user.expired ? 'active' : 'signed-out');
      })
      .catch(() => {
        if (active) setAccess('signed-out');
      });
    return () => {
      active = false;
      stopExpired();
      stopUnloaded();
    };
  }, []);

  function endSession() {
    setAccess('signed-out');
    void signOut().catch(() => setAccess('logout-failed'));
  }

  if (access !== 'active') {
    return (
      <main className="mx-auto max-w-md p-8 mt-20">
        {access === 'checking' ? (
          <output>Checking analyst session…</output>
        ) : (
          <>
            <h1>
              {access === 'expired'
                ? 'Your session has expired'
                : 'Signed out of RiskWeave'}
            </h1>
            {access === 'logout-failed' && (
              <p role="alert">
                Sign-out could not finish. Close this tab and end your
                identity-provider session.
              </p>
            )}
            <p className="my-6">Sign in to access your investigations.</p>
            <Link href="/sign-in">Return to sign-in</Link>
          </>
        )}
      </main>
    );
  }
  return (
    <SessionContext.Provider value={endSession}>
      {children}
    </SessionContext.Provider>
  );
}
