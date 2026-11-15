'use client';

import { useState } from 'react';
import { authenticationEnabled, authManager } from '@/lib/auth';
import { Button } from '@/components/ui/button';

export default function SignInPage() {
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function signIn() {
    setBusy(true);
    setError('');
    try {
      await authManager().signinRedirect();
    } catch {
      setError(
        'Sign-in could not start. Please retry or contact the operator.',
      );
      setBusy(false);
    }
  }
  return (
    <main className="mx-auto max-w-md p-8 mt-20">
      <h1 className="text-3xl font-semibold">Sign in to RiskWeave</h1>
      <p className="my-6">
        Use your analyst account to access your investigations.
      </p>
      {authenticationEnabled ? (
        <Button disabled={busy} onClick={() => void signIn()}>
          {busy ? 'Opening sign-in…' : 'Sign in'}
        </Button>
      ) : (
        <p>Analyst sign-in is not configured. Contact the operator.</p>
      )}
      {error && (
        <p role="alert" className="mt-4">
          {error}
        </p>
      )}
    </main>
  );
}
