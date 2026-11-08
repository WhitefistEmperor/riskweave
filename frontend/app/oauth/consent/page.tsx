'use client';

import { useCallback, useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  consentClient,
  consentEnabled,
  trustedRedirect,
} from '@/lib/supabase-consent';

type Details = {
  authorization_id: string;
  client: { name?: string };
  scope: string;
  user: { email: string };
};

type State =
  | { kind: 'loading' }
  | { kind: 'sign-in' }
  | { kind: 'consent'; details: Details }
  | { kind: 'redirecting' }
  | { kind: 'error'; message: string };

const GENERIC =
  'This sign-in request could not be completed. Return to RiskWeave and try again.';

export default function OAuthConsentPage() {
  const [state, setState] = useState<State>({ kind: 'loading' });
  const [busy, setBusy] = useState(false);
  const [authorizationId, setAuthorizationId] = useState('');
  const [notice, setNotice] = useState('');

  const go = useCallback((url: string) => {
    const target = trustedRedirect(url, window.location.origin);
    if (!target) {
      setState({ kind: 'error', message: GENERIC });
      return;
    }
    setState({ kind: 'redirecting' });
    window.location.replace(target);
  }, []);

  const load = useCallback(
    async (id: string) => {
      const supabase = consentClient();
      const { data: session } = await supabase.auth.getSession();
      if (!session.session) {
        setState({ kind: 'sign-in' });
        return;
      }
      const { data, error } =
        await supabase.auth.oauth.getAuthorizationDetails(id);
      if (error || !data) {
        setState({ kind: 'error', message: GENERIC });
      } else if ('authorization_id' in data) {
        setState({ kind: 'consent', details: data as Details });
      } else {
        go(data.redirect_url);
      }
    },
    [go],
  );

  useEffect(() => {
    // State updates happen asynchronously, after the URL is read.
    void Promise.resolve().then(async () => {
      if (!consentEnabled) {
        setState({
          kind: 'error',
          message: 'Analyst sign-in is not configured. Contact the operator.',
        });
        return;
      }
      const id =
        new URLSearchParams(window.location.search).get('authorization_id') ??
        '';
      if (!/^[\w-]{1,200}$/.test(id)) {
        setState({ kind: 'error', message: GENERIC });
        return;
      }
      setAuthorizationId(id);
      await load(id).catch(() => setState({ kind: 'error', message: GENERIC }));
    });
  }, [load]);

  async function signIn(event: {
    preventDefault(): void;
    currentTarget: HTMLFormElement;
  }) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const field = (name: string) => {
      const value = form.get(name);
      return typeof value === 'string' ? value : '';
    };
    setBusy(true);
    try {
      const { error } = await consentClient().auth.signInWithPassword({
        email: field('email'),
        password: field('password'),
      });
      if (error) {
        // Never reveal whether an account exists.
        setNotice('Sign-in failed. Check your email and password.');
        return;
      }
      setNotice('');
      await load(authorizationId);
    } catch {
      setState({ kind: 'error', message: GENERIC });
    } finally {
      setBusy(false);
    }
  }

  async function decide(approve: boolean) {
    setBusy(true);
    try {
      const oauth = consentClient().auth.oauth;
      const { data, error } = approve
        ? await oauth.approveAuthorization(authorizationId, {
            skipBrowserRedirect: true,
          })
        : await oauth.denyAuthorization(authorizationId, {
            skipBrowserRedirect: true,
          });
      if (error || !data) setState({ kind: 'error', message: GENERIC });
      else go(data.redirect_url);
    } catch {
      setState({ kind: 'error', message: GENERIC });
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-md p-8 mt-20">
      <h1 className="text-3xl font-semibold">Sign in to RiskWeave</h1>
      {state.kind === 'loading' && (
        <p className="my-6">Checking your sign-in request…</p>
      )}
      {state.kind === 'redirecting' && (
        <p className="my-6">Returning to RiskWeave…</p>
      )}
      {state.kind === 'error' && (
        <p role="alert" className="my-6">
          {state.message}
        </p>
      )}
      {state.kind === 'sign-in' && (
        <form
          className="my-6 grid gap-4"
          onSubmit={(event) => void signIn(event)}
        >
          <p>Use your analyst account. Accounts are created by the operator.</p>
          <div className="grid gap-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              name="email"
              type="email"
              autoComplete="username"
              required
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
            />
          </div>
          {notice && <p role="alert">{notice}</p>}
          <Button type="submit" disabled={busy}>
            {busy ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>
      )}
      {state.kind === 'consent' && (
        <section className="my-6 grid gap-4">
          <p>
            <strong>{state.details.client.name || 'RiskWeave console'}</strong>{' '}
            is asking to access your investigations as{' '}
            <strong>{state.details.user.email}</strong>.
          </p>
          <div className="flex gap-3">
            <Button disabled={busy} onClick={() => void decide(true)}>
              Allow
            </Button>
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => void decide(false)}
            >
              Deny
            </Button>
          </div>
        </section>
      )}
    </main>
  );
}
