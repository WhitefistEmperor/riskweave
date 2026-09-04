'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { Investigator } from '@/components/investigator';
import { EvidenceValue, humanize } from '@/components/evidence-value';
import { dateTime, money, shortId } from '@/lib/api';
import { ApiError } from '@/lib/client';
import {
  platformApi,
  pollRun,
  type InvestigationRecord,
  type AnalysisRun,
  type ArtifactRecord,
  type AnalysisResult,
  type Session,
} from '@/lib/platform-api';

function Workspace({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  useEffect(() => {
    let active = true;
    platformApi
      .session()
      .then((value) => {
        if (active) setSession(value);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);
  return (
    <main className="p-6 md:p-10 max-w-7xl mx-auto space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <Link href="/" className="cyan">
          RingSentinel · Demo console
        </Link>
        <Link href="/investigations" className="cyan">
          Investigations
        </Link>
        <p className="muted text-sm">
          {session
            ? `${session.user_id} · Development identity only`
            : 'Session unavailable'}
        </p>
      </header>
      {children}
    </main>
  );
}

function Failure({ error }: { error: unknown }) {
  if (!error) return null;
  const unauthorized = error instanceof ApiError && error.status === 401;
  return (
    <Card className="panel p-4" role="alert">
      <h2>
        {unauthorized ? 'Unauthorized' : 'Request could not be completed'}
      </h2>
      <p className="amber break-words">
        {error instanceof Error ? error.message : 'Request failed.'}
      </p>
      {unauthorized && (
        <p className="muted">
          A valid session is required. Production authentication is not
          connected in Phase 5A.
        </p>
      )}
    </Card>
  );
}

export function InvestigationList() {
  const [records, setRecords] = useState<InvestigationRecord[] | null>(null);
  const [name, setName] = useState('');
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    platformApi
      .investigations()
      .then((value) => {
        if (active) setRecords(value);
      })
      .catch((reason: unknown) => {
        if (active) setError(reason);
      });
    return () => {
      active = false;
    };
  }, []);
  async function create() {
    setBusy(true);
    setError(null);
    try {
      const item = await platformApi.create(name.trim());
      window.location.assign(`/investigations/${encodeURIComponent(item.id)}`);
    } catch (reason: unknown) {
      setError(reason);
      setBusy(false);
    }
  }
  return (
    <Workspace>
      <h1>Investigations</h1>
      <p className="muted">
        Saved datasets and analysis runs. Results use the unchanged
        synthetic-trained detector and require analyst review.
      </p>
      <Failure error={error} />
      <Card className="panel p-5">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void create();
          }}
          className="flex flex-wrap gap-3 items-end"
        >
          <div className="flex-1 min-w-48">
            <label htmlFor="investigation-name">Investigation name</label>
            <Input
              id="investigation-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={120}
              required
              className="mt-2"
            />
          </div>
          <Button type="submit" disabled={busy || !name.trim()}>
            {busy ? 'Creating…' : 'Create investigation'}
          </Button>
        </form>
      </Card>
      {!records && !error && <output>Loading investigations…</output>}
      {records?.length === 0 && (
        <Card className="panel p-5">
          <h2>No investigations yet</h2>
          <p className="muted">
            Create an investigation, attach a DatasetBundle JSON file, and start
            analysis.
          </p>
        </Card>
      )}
      {records?.map((item) => (
        <Card
          key={item.id}
          className="panel p-5 flex flex-wrap justify-between gap-3"
        >
          <Link
            className="cyan"
            href={`/investigations/${encodeURIComponent(item.id)}`}
          >
            {item.name}
          </Link>
          <span>{item.status}</span>
          <span className="muted text-sm">{dateTime(item.created_at)} UTC</span>
        </Card>
      ))}
    </Workspace>
  );
}

export function InvestigationDetail({
  investigationId,
  initialRunId,
}: {
  investigationId: string;
  initialRunId?: string;
}) {
  const [record, setRecord] = useState<InvestigationRecord | null>(null);
  const [artifacts, setArtifacts] = useState<ArtifactRecord[]>([]);
  const [artifactId, setArtifactId] = useState('');
  const [runs, setRuns] = useState<AnalysisRun[]>([]);
  const [runId, setRunId] = useState(initialRunId ?? '');
  const [run, setRun] = useState<AnalysisRun | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [ringId, setRingId] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [pollAttempt, setPollAttempt] = useState(0);
  // Preserve the same key after an ambiguous network failure; a retry cannot duplicate work.
  const pendingStart = useRef<{ artifactId: string; key: string } | null>(null);
  const inFlight = useRef(false);
  useEffect(() => {
    let active = true;
    Promise.all([
      platformApi.investigation(investigationId),
      platformApi.artifacts(investigationId),
      platformApi.runs(investigationId),
    ])
      .then(([item, files, history]) => {
        if (!active) return;
        setRecord(item);
        setArtifacts(files);
        setArtifactId(files.at(-1)?.id ?? '');
        setRuns(history);
        setRunId(initialRunId ?? history.at(-1)?.id ?? '');
      })
      .catch((reason: unknown) => {
        if (active) setError(reason);
      });
    return () => {
      active = false;
    };
  }, [investigationId, initialRunId]);
  useEffect(() => {
    if (!runId) return;
    const controller = new AbortController();
    pollRun(
      runId,
      (value) => {
        // A run URL must belong to this investigation, even if the same owner can read both.
        if (value.investigation_id !== investigationId)
          throw new Error('This run belongs to a different investigation.');
        setRun(value);
        setRuns((history) => [
          ...history.filter((item) => item.id !== value.id),
          value,
        ]);
      },
      controller.signal,
    )
      .then(async () => {
        if (controller.signal.aborted) return;
        const latest = await platformApi.run(runId, controller.signal);
        if (latest.status !== 'completed') return;
        const value = await platformApi.results(runId, controller.signal);
        if (!controller.signal.aborted) {
          setResult(value);
          setRingId(value.rings[0]?.candidate.candidate_id ?? '');
        }
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(reason);
      });
    return () => controller.abort();
  }, [runId, investigationId, pollAttempt]);
  function selectRun(value: string) {
    setRun(null);
    setResult(null);
    setRingId('');
    setError(null);
    setRunId(value);
    window.history.replaceState(
      null,
      '',
      `/investigations/${encodeURIComponent(investigationId)}?run=${encodeURIComponent(value)}`,
    );
  }
  async function upload() {
    if (!file || inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError(null);
    try {
      const item = await platformApi.upload(investigationId, file);
      setArtifacts((items) => [
        ...items.filter((value) => value.id !== item.id),
        item,
      ]);
      setArtifactId(item.id);
    } catch (reason: unknown) {
      setError(reason);
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }
  async function start() {
    if (!artifactId || inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError(null);
    if (pendingStart.current?.artifactId !== artifactId)
      pendingStart.current = { artifactId, key: crypto.randomUUID() };
    try {
      const value = await platformApi.start(
        investigationId,
        artifactId,
        pendingStart.current.key,
      );
      pendingStart.current = null;
      setRun(value);
      selectRun(value.id);
    } catch (reason: unknown) {
      setError(reason);
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }
  const activeRun =
    runs.some(
      (item) => item.status === 'queued' || item.status === 'running',
    ) ||
    run?.status === 'queued' ||
    run?.status === 'running';
  const selected = result?.rings.find(
    (item) => item.candidate.candidate_id === ringId,
  );
  return (
    <Workspace>
      <h1>{record?.name ?? 'Investigation'}</h1>
      <Failure error={error} />
      {Boolean(error) && runId && (
        <Button
          variant="outline"
          onClick={() => {
            setError(null);
            setPollAttempt((n) => n + 1);
          }}
        >
          Resume status checks
        </Button>
      )}
      {!record && !error && <output>Loading investigation…</output>}
      {record && (
        <>
          <Card className="panel p-5 space-y-4">
            <h2>Input dataset</h2>
            <p className="muted text-sm">
              DatasetBundle JSON only. Uploads are validated and checksummed; an
              identical upload reuses its artifact.
            </p>
            <label htmlFor="dataset-file">Dataset file</label>
            <Input
              id="dataset-file"
              type="file"
              accept=".json,application/json"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              disabled={busy || activeRun}
            />
            <Button
              onClick={() => void upload()}
              disabled={!file || busy || activeRun}
            >
              Upload dataset
            </Button>
            {artifacts.length > 0 && (
              <>
                <label id="artifact-label" htmlFor="artifact-select">
                  Analysis input
                </label>
                <Select
                  value={artifactId}
                  onValueChange={(value) => setArtifactId(String(value ?? ''))}
                  disabled={busy || activeRun}
                >
                  <SelectTrigger
                    id="artifact-select"
                    aria-labelledby="artifact-label"
                  >
                    <SelectValue>
                      {
                        artifacts.find((value) => value.id === artifactId)
                          ?.original_name
                      }
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {artifacts.map((item) => (
                      <SelectItem value={item.id} key={item.id}>
                        {item.original_name} ·{' '}
                        {item.size_bytes.toLocaleString()} bytes
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  onClick={() => void start()}
                  disabled={!artifactId || busy || activeRun}
                >
                  {busy ? 'Working…' : 'Start analysis'}
                </Button>
              </>
            )}
          </Card>
          <Card className="panel p-5 space-y-3">
            <h2>Analysis runs</h2>
            {runs.length === 0 && !run && (
              <p className="muted">No analysis runs yet.</p>
            )}
            <div className="flex flex-wrap gap-2">
              {runs.map((item) => (
                <Button
                  variant={runId === item.id ? 'default' : 'outline'}
                  key={item.id}
                  onClick={() => selectRun(item.id)}
                >
                  {shortId(item.id)} · {item.status}
                </Button>
              ))}
            </div>
            {runId && !run && !error && <output>Loading run…</output>}
            {run && (
              <div className="space-y-2">
                <output>
                  Analysis status: <strong>{run.status}</strong>
                </output>
                {run.status === 'queued' && (
                  <p className="muted">
                    Waiting for the local analysis worker.
                  </p>
                )}
                {run.status === 'running' && (
                  <p className="muted">
                    Analysis is running. This page polls persisted status; you
                    can return later.
                  </p>
                )}
                {run.status === 'failed' && (
                  <p className="amber" role="alert">
                    {run.error_message_safe} ({run.error_code})
                  </p>
                )}
                <p className="muted text-sm">
                  Run {run.id} · App {run.version_metadata.application} ·{' '}
                  {run.version_metadata.detector}
                </p>
                {run.result_checksum && (
                  <p className="muted text-sm break-all">
                    Result SHA256: {run.result_checksum}
                  </p>
                )}
              </div>
            )}
          </Card>
          {result && (
            <Card className="panel p-5 space-y-4">
              <h2>Persisted findings</h2>
              <p>
                {result.event_count.toLocaleString()} events ·{' '}
                {result.entity_count.toLocaleString()} entities ·{' '}
                {result.rings.length} candidate rings
              </p>
              <p className="muted">
                {result.model_scope}. Threshold {result.threshold.toFixed(2)}.
              </p>
              {result.rings.length === 0 && (
                <p>
                  No candidate rings were detected. This is not proof of
                  legitimacy.
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                {result.rings.map(({ candidate }) => (
                  <Button
                    variant={
                      candidate.candidate_id === ringId ? 'default' : 'outline'
                    }
                    key={candidate.candidate_id}
                    onClick={() => setRingId(candidate.candidate_id)}
                  >
                    {shortId(candidate.candidate_id)} ·{' '}
                    {money(candidate.estimated_exposure_minor)}
                  </Button>
                ))}
              </div>
              {selected && (
                <Accordion multiple>
                  {Object.entries(selected.queries).map(([query, value]) => (
                    <AccordionItem key={query} value={query}>
                      <AccordionTrigger>{humanize(query)}</AccordionTrigger>
                      <AccordionContent>
                        <EvidenceValue value={value} />
                      </AccordionContent>
                    </AccordionItem>
                  ))}
                </Accordion>
              )}
            </Card>
          )}
          {selected && run && (
            <Investigator
              key={`${run.id}-${ringId}`}
              runId={run.id}
              candidateId={ringId}
            />
          )}
        </>
      )}
    </Workspace>
  );
}
