import { AnalystConsole } from '@/components/analyst-console';

// Read per request (not at build time), so the hosting environment decides it.
export const dynamic = 'force-dynamic';

export default function DemoPage() {
  // On a sleeping host, requests that the frontend server forwards from inside
  // the host's network may be refused instead of waking the API. A request
  // from the visitor's own browser to the API's public address wakes it, so
  // the page sends one while it waits. Unset locally: nothing extra is sent.
  return <AnalystConsole wakeUrl={process.env.RINGSENTINEL_DEMO_WAKE_URL} />;
}
