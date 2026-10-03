'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { authManager } from '@/lib/auth';

let callback: Promise<unknown> | undefined;
export default function AuthCallback() {
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    callback ??= Promise.resolve().then(() =>
      authManager().signinRedirectCallback(),
    );
    callback
      .then(() => window.location.replace('/investigations'))
      .catch(() => setFailed(true));
  }, []);
  return (
    <main className="mx-auto max-w-md p-8 mt-20">
      {failed ? (
        <>
          <h1>Sign-in could not be completed</h1>
          <p>Please try again.</p>
          <Link href="/sign-in">Return to sign-in</Link>
        </>
      ) : (
        <p>Completing sign-in…</p>
      )}
    </main>
  );
}
