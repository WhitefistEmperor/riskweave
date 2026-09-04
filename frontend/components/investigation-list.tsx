'use client';
import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { ArrowRight, FolderSearch, Plus } from 'lucide-react';
import { ProductShell } from '@/components/product-shell';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Failure, LoadingState, StatusBadge } from '@/components/workspace-states';
import { dateTime, shortId } from '@/lib/api';
import { platformApi, type InvestigationRecord, type AnalysisRun } from '@/lib/platform-api';

export function InvestigationList() {
  const [records, setRecords] = useState<InvestigationRecord[] | null>(null);
  const [latest, setLatest] = useState<Record<string, AnalysisRun | null>>({});
  const [name, setName] = useState('');
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [page, setPage] = useState(0);
  const inFlight = useRef(false);
  const visible = records?.slice(page * 10, page * 10 + 10);
  useEffect(() => {
    const controller = new AbortController();
    platformApi.investigations(controller.signal).then(items => {
      if (!controller.signal.aborted) setRecords([...items].sort((a, b) => b.updated_at.localeCompare(a.updated_at)));
    }).catch(reason => { if (!controller.signal.aborted) setError(reason); });
    return () => controller.abort();
  }, [attempt]);
  useEffect(() => {
    const controller = new AbortController();
    // Bound history reads to visible records, without fetching full results or polling.
    for (const item of records?.slice(page * 10, page * 10 + 10) ?? []) {
      platformApi.runs(item.id, controller.signal).then(runs => {
        if (!controller.signal.aborted) setLatest(current => ({ ...current, [item.id]: [...runs].sort((a, b) => a.created_at.localeCompare(b.created_at)).at(-1) ?? null }));
      }).catch(() => undefined);
    }
    return () => controller.abort();
  }, [records, page]);
  async function create() {
    if (inFlight.current || !name.trim()) return;
    inFlight.current = true; setBusy(true); setError(null);
    try {
      const item = await platformApi.create(name.trim());
      window.location.assign(`/investigations/${encodeURIComponent(item.id)}`);
    } catch (reason) { setError(reason); setBusy(false); inFlight.current = false; }
  }
  return <ProductShell>
    <div className="workspace-heading"><div><span className="product-kicker">INVESTIGATION WORKLIST</span><h1>Investigations</h1><p className="muted">Review coordinated activity. Keep the evidence and every analysis in one place.</p></div><span className="workspace-count">{records ? `${records.length} saved` : 'Loading'}</span></div>
    <Failure error={error} retry={() => { setError(null); setAttempt(n => n + 1); }} />
    <Card className="panel create-panel"><div><Plus size={19} /><h2>New investigation</h2><p className="muted">Name the case, then attach its dataset.</p></div><form onSubmit={event => { event.preventDefault(); void create(); }}><label htmlFor="investigation-name">Investigation name</label><div><Input id="investigation-name" disabled={records === null || busy} placeholder="e.g. September shared-infrastructure review" value={name} onChange={event => setName(event.target.value)} maxLength={120} required /><Button type="submit" disabled={busy || !name.trim()}>{busy ? 'Creating…' : 'Create investigation'}<ArrowRight size={15} /></Button></div></form></Card>
    {!records && !error && <LoadingState label="Loading investigations…" />}
    {records?.length === 0 && <Card className="panel workspace-empty"><FolderSearch size={32} /><h2>No investigations yet</h2><p>Start with a name above. Upload a DatasetBundle JSON file,<br className="hidden md:block" /> run analysis, then review candidate rings and their evidence.</p><span className="muted text-xs">Saved on the server · Revisit using the same identity</span></Card>}
    {!!visible?.length && <Card className="panel"><div className="section-heading"><h2>Saved investigations</h2><span className="muted text-xs">Most recently updated first · UTC</span></div><Table><TableHeader><TableRow><TableHead>Investigation</TableHead><TableHead>Status</TableHead><TableHead>Last updated</TableHead><TableHead>Latest analysis</TableHead><TableHead><span className="sr-only">Open</span></TableHead></TableRow></TableHeader><TableBody>{visible.map(item => <TableRow key={item.id}><TableCell><Link className="record-link" href={`/investigations/${item.id}`}>{item.name}<span className="record-subtitle">Created {dateTime(item.created_at)} UTC</span></Link></TableCell><TableCell><StatusBadge status={item.status} /></TableCell><TableCell className="muted whitespace-nowrap">{dateTime(item.updated_at)}</TableCell><TableCell>{latest[item.id] ? <span className="text-xs">{shortId(latest[item.id]!.id)} · {latest[item.id]!.status}</span> : item.id in latest ? <span className="muted text-xs">No runs yet</span> : <span className="muted text-xs">Not loaded</span>}</TableCell><TableCell><Link className="open-record" aria-label={`Open ${item.name}`} href={`/investigations/${item.id}`}>{latest[item.id]?.status === 'completed' ? 'Review' : 'Open'}<ArrowRight size={14} /></Link></TableCell></TableRow>)}</TableBody></Table><div className="list-pagination"><span>{page * 10 + 1}–{Math.min((page + 1) * 10, records!.length)} of {records!.length}</span><Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage(n => n - 1)}>Previous</Button><Button variant="outline" size="sm" disabled={(page + 1) * 10 >= records!.length} onClick={() => setPage(n => n + 1)}>Next</Button></div></Card>}
  </ProductShell>;
}
