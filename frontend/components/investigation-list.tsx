'use client';
import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { ArrowRight, FolderSearch, Plus } from 'lucide-react';
import { ProductShell } from '@/components/product-shell';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Failure,
  LoadingState,
  StatusBadge,
} from '@/components/workspace-states';
import { dateTime, shortId } from '@/lib/api';
import {
  platformApi,
  type InvestigationRecord,
  type AnalysisRun,
} from '@/lib/platform-api';

export function InvestigationList() {
  const [records, setRecords] = useState<InvestigationRecord[] | null>(null);
  const [latest, setLatest] = useState<Record<string, AnalysisRun | null>>({});
  const [name, setName] = useState('');
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [page, setPage] = useState(0);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('all');
  const removed = useSearchParams()?.get('removed');
  const inFlight = useRef(false);
  const loadedHistory = useRef(new Set<string>());
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return records?.filter(
      (item) =>
        (status === 'all' || item.status === status) &&
        (!needle ||
          item.name.toLowerCase().includes(needle) ||
          item.id.toLowerCase().includes(needle)),
    );
  }, [records, query, status]);
  const currentPage = Math.min(
    page,
    Math.max(0, Math.ceil((filtered?.length ?? 0) / 10) - 1),
  );
  const visible = filtered?.slice(currentPage * 10, currentPage * 10 + 10);
  useEffect(() => {
    const controller = new AbortController();
    platformApi
      .investigations(controller.signal)
      .then((items) => {
        if (!controller.signal.aborted) {
          loadedHistory.current.clear();
          setLatest({});
          setRecords(
            [...items].sort((a, b) => b.updated_at.localeCompare(a.updated_at)),
          );
        }
      })
      .catch((reason) => {
        if (!controller.signal.aborted) setError(reason);
      });
    return () => controller.abort();
  }, [attempt]);
  useEffect(() => {
    const controller = new AbortController();
    // Bound history reads to visible records, without fetching full results or polling.
    for (const item of filtered?.slice(
      currentPage * 10,
      currentPage * 10 + 10,
    ) ?? []) {
      if (loadedHistory.current.has(item.id)) continue;
      platformApi
        .runs(item.id, controller.signal)
        .then((runs) => {
          if (!controller.signal.aborted) {
            loadedHistory.current.add(item.id);
            setLatest((current) => ({
              ...current,
              [item.id]:
                [...runs]
                  .sort((a, b) => a.created_at.localeCompare(b.created_at))
                  .at(-1) ?? null,
            }));
          }
        })
        .catch(() => undefined);
    }
    return () => controller.abort();
  }, [filtered, currentPage]);
  async function create() {
    if (inFlight.current || !name.trim()) return;
    inFlight.current = true;
    setBusy(true);
    setError(null);
    try {
      const item = await platformApi.create(name.trim());
      window.location.assign(`/investigations/${encodeURIComponent(item.id)}`);
    } catch (reason) {
      setError(reason);
      setBusy(false);
      inFlight.current = false;
    }
  }
  return (
    <ProductShell>
      {(removed === 'complete' || removed === 'pending') && (
        <output className="block panel p-4 mb-4">
          {removed === 'complete'
            ? 'Investigation deleted from the workspace and its stored files removed.'
            : 'Investigation removed from the workspace. Some stored files are awaiting cleanup.'}
        </output>
      )}
      <div className="workspace-heading">
        <div>
          <span className="product-kicker">INVESTIGATION WORKLIST</span>
          <h1>Investigations</h1>
          <p className="muted">
            Review coordinated activity. Keep the evidence and every analysis in
            one place.
          </p>
        </div>
        <span className="workspace-count">
          {records ? `${records.length} saved` : 'Loading'}
        </span>
      </div>
      <Failure
        error={error}
        retry={() => {
          setError(null);
          setAttempt((n) => n + 1);
        }}
      />
      <Card className="panel create-panel">
        <div>
          <Plus size={19} />
          <h2>New investigation</h2>
          <p className="muted">Name the case, then attach its dataset.</p>
        </div>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void create();
          }}
        >
          <label htmlFor="investigation-name">Investigation name</label>
          <div>
            <Input
              id="investigation-name"
              disabled={records === null || busy}
              placeholder="e.g. September shared-infrastructure review"
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={120}
              required
            />
            <Button type="submit" disabled={busy || !name.trim()}>
              {busy ? 'Creating…' : 'Create investigation'}
              <ArrowRight size={15} />
            </Button>
          </div>
        </form>
      </Card>
      {!records && !error && <LoadingState label="Loading investigations…" />}
      {!!records?.length && (
        <Card className="panel p-4 mb-4">
          <div className="flex flex-wrap items-end gap-4">
            <div className="flex-1 min-w-48">
              <label htmlFor="investigation-search">
                Search investigations
              </label>
              <Input
                id="investigation-search"
                type="search"
                placeholder="Name or case ID"
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value);
                  setPage(0);
                }}
              />
            </div>
            <div>
              <label htmlFor="investigation-status-filter" className="block">
                Case status
              </label>
              <select
                id="investigation-status-filter"
                value={status}
                className="rounded-md border px-3 py-2 bg-background text-foreground"
                onChange={(event) => {
                  setStatus(event.target.value);
                  setPage(0);
                }}
              >
                <option value="all">All statuses</option>
                {[
                  'created',
                  'uploading',
                  'queued',
                  'running',
                  'completed',
                  'failed',
                ].map((value) => (
                  <option key={value} value={value}>
                    {value[0].toUpperCase() + value.slice(1)}
                  </option>
                ))}
              </select>
            </div>
            <Button
              variant="outline"
              disabled={!query && status === 'all'}
              onClick={() => {
                setQuery('');
                setStatus('all');
                setPage(0);
              }}
            >
              Clear filters
            </Button>
          </div>
          <output className="block muted text-sm mt-3" aria-live="polite">
            {filtered?.length} matching of {records.length} saved
          </output>
        </Card>
      )}
      {!!records?.length && filtered?.length === 0 && (
        <Card className="panel workspace-empty">
          <h2>No investigations match these filters</h2>
          <p>
            Change the name, case ID or status, or clear the filters to see your
            saved cases.
          </p>
        </Card>
      )}
      {records?.length === 0 && (
        <Card className="panel workspace-empty">
          <FolderSearch size={32} />
          <h2>No investigations yet</h2>
          <p>
            Start with a name above. Upload a payment dataset JSON file,
            <br className="hidden md:block" /> run analysis, then review
            candidate rings and their evidence.
          </p>
          <span className="muted text-xs">
            Saved on the server · Revisit using the same identity
          </span>
        </Card>
      )}
      {!!visible?.length && (
        <Card className="panel">
          <div className="section-heading">
            <h2>Saved investigations</h2>
            <span className="muted text-xs">
              Most recently updated first · UTC
            </span>
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Investigation</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Last updated</TableHead>
                <TableHead>Latest analysis</TableHead>
                <TableHead>
                  <span className="sr-only">Open</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {visible.map((item) => (
                <TableRow key={item.id}>
                  <TableCell>
                    <Link
                      className="record-link"
                      href={`/investigations/${item.id}`}
                    >
                      {item.name}
                      <span className="record-subtitle">
                        Created {dateTime(item.created_at)} UTC
                      </span>
                    </Link>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={item.status} />
                  </TableCell>
                  <TableCell className="muted whitespace-nowrap">
                    {dateTime(item.updated_at)}
                  </TableCell>
                  <TableCell>
                    {latest[item.id] ? (
                      <span className="text-xs">
                        {shortId(latest[item.id]!.id)} ·{' '}
                        {latest[item.id]!.status}
                      </span>
                    ) : item.id in latest ? (
                      <span className="muted text-xs">No runs yet</span>
                    ) : (
                      <span className="muted text-xs">Not loaded</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <Link
                      className="open-record"
                      aria-label={`Open ${item.name}`}
                      href={`/investigations/${item.id}`}
                    >
                      {latest[item.id]?.status === 'completed'
                        ? 'Review'
                        : 'Open'}
                      <ArrowRight size={14} />
                    </Link>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <div className="list-pagination">
            <span>
              {currentPage * 10 + 1}–
              {Math.min((currentPage + 1) * 10, filtered!.length)} of{' '}
              {filtered!.length}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={currentPage === 0}
              onClick={() => setPage(currentPage - 1)}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={(currentPage + 1) * 10 >= filtered!.length}
              onClick={() => setPage(currentPage + 1)}
            >
              Next
            </Button>
          </div>
        </Card>
      )}
    </ProductShell>
  );
}
