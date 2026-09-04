'use client';

import { useEffect, useState, type CSSProperties, type ReactNode } from 'react';
import Link from 'next/link';
import { FolderSearch, Hexagon, Play, ShieldCheck } from 'lucide-react';
import { Sidebar, SidebarContent, SidebarFooter, SidebarHeader, SidebarInset, SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar';
import { platformApi, type Session } from '@/lib/platform-api';

export function ProductShell({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [sessionFailed, setSessionFailed] = useState(false);
  useEffect(() => {
    let active = true;
    platformApi.session().then(value => { if (active) setSession(value); }).catch(() => { if (active) setSessionFailed(true); });
    return () => { active = false; };
  }, []);
  return <SidebarProvider className="product-shell" style={{ '--sidebar-width': '13.5rem' } as CSSProperties}>
    <a className="skip-link" href="#workspace-content">Skip to investigation</a>
    <Sidebar>
      <SidebarHeader className="product-brand"><Link href="/investigations"><Hexagon size={25} strokeWidth={1.6} /><span>RingSentinel<small>ANALYST WORKSPACE</small></span></Link></SidebarHeader>
      <SidebarContent>
        <nav aria-label="Main navigation" className="product-navigation">
          <span className="product-kicker">WORKSPACE</span>
          <Link href="/investigations" aria-current="page"><FolderSearch size={18} />Investigations</Link>
          <span className="product-kicker mt-8">REFERENCE</span>
          <Link href="/demo"><Play size={17} />Demo / Replay</Link>
        </nav>
      </SidebarContent>
      <SidebarFooter className="product-footer"><ShieldCheck size={19} /><p>Evidence, not verdicts.<small>Synthetic-trained detection.<br />Human review required.</small></p></SidebarFooter>
    </Sidebar>
    <SidebarInset className="min-w-0">
      <header className="product-topbar"><div><SidebarTrigger /><span>Network risk operations</span></div><span className="product-session">{session ? `${session.user_id} · Development identity` : sessionFailed ? 'Session unavailable · check API connection' : 'Checking session…'}</span></header>
      <main id="workspace-content" tabIndex={-1} className="product-content">{children}</main>
    </SidebarInset>
  </SidebarProvider>;
}
