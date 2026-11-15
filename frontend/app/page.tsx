import { redirect } from 'next/navigation';

// A public read-only deployment (RINGSENTINEL_PUBLIC_DEMO=true) has no sign-in,
// so the persisted investigations workspace is locked there. Send visitors to
// the synthetic demo instead.
export default function Home() {
  redirect(process.env.RINGSENTINEL_PUBLIC_DEMO === 'true' ? '/demo' : '/investigations');
}
