'use client';
import { useState } from 'react';
import Link from 'next/link';
import { ChevronRight, FileJson, Upload, ArrowRight } from 'lucide-react';
import { useInvestigation } from '@/hooks/use-investigation';
import { ProductShell } from '@/components/product-shell';
import {
  Failure,
  LoadingState,
  StatusBadge,
} from '@/components/workspace-states';
import { PersistedFindings } from '@/components/persisted-findings';
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
import { dateTime, shortId } from '@/lib/api';
export { InvestigationList } from '@/components/investigation-list';

export function InvestigationDetail({
  investigationId,
  initialRunId,
}: {
  investigationId: string;
  initialRunId?: string;
}) {
  const state = useInvestigation(investigationId, initialRunId);
  const {
    record,
    artifacts,
    artifactId,
    runs,
    runId,
    run,
    result,
    error,
    busy,
    activeRun,
  } = state;
  const [file, setFile] = useState<File | null>(null);
  const artifact = artifacts.find((item) => item.id === artifactId);
  return (
    <ProductShell>
      <nav aria-label="Breadcrumb" className="breadcrumb">
        <Link href="/investigations">Investigations</Link>
        <ChevronRight size={14} />
        <span>{record?.name ?? 'Investigation'}</span>
      </nav>
      <div className="workspace-heading">
        <div>
          <h1>{record?.name ?? 'Investigation'}</h1>
          <p className="muted">
            Persisted dataset analysis · Retrospective, not a live monitor
          </p>
        </div>
        {record && <StatusBadge status={run?.status ?? record.status} />}
      </div>
      <Failure error={error} retry={state.retry} />
      {!record && !error && <LoadingState label="Loading investigation…" />}
      {record && (
        <>
          {(runs.length > 0 || runId) && (
            <Card className="panel p-5 run-panel">
              <div className="section-heading compact">
                <h2>Analysis runs</h2>
                <Select
                  value={runId}
                  onValueChange={(value) => state.selectRun(String(value))}
                >
                  <SelectTrigger aria-label="Selected analysis run">
                    <SelectValue>
                      {run
                        ? shortId(run.id) + ' · ' + run.status
                        : 'Choose a run'}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {[...runs].reverse().map((item) => (
                      <SelectItem key={item.id} value={item.id}>
                        {shortId(item.id)} · {item.status} ·{' '}
                        {dateTime(item.created_at)} UTC
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {runId && !run && !error && <LoadingState label="Loading run…" />}
              {run && (
                <div className={'run-state run-state-' + run.status}>
                  <output>
                    Analysis status: <strong>{run.status}</strong>
                  </output>
                  <p className="muted">
                    {run.status === 'queued'
                      ? 'Waiting for the local analysis worker. You can leave this page and return later.'
                      : run.status === 'running'
                        ? 'Computing network relationships and evidence. You can return later; no percentage estimate is available.'
                        : run.status === 'completed'
                          ? 'Review the candidate rings below. Findings require analyst assessment.'
                          : 'The run did not produce usable results. Review the error before starting a new run.'}
                  </p>
                  {run.status === 'failed' && (
                    <p className="amber" role="alert">
                      {run.error_message_safe} ({run.error_code})
                    </p>
                  )}
                  <details className="technical-details">
                    <summary>Run provenance and integrity</summary>
                    <p>Run {run.id}</p>
                    <p>
                      Created {dateTime(run.created_at)} UTC
                      {run.started_at &&
                        ' · Started ' + dateTime(run.started_at) + ' UTC'}
                      {run.completed_at &&
                        ' · Finished ' + dateTime(run.completed_at) + ' UTC'}
                    </p>
                    <p>
                      App {run.version_metadata.application} ·{' '}
                      {run.version_metadata.detector}
                    </p>
                    {run.result_checksum && (
                      <p>Result SHA256: {run.result_checksum}</p>
                    )}
                  </details>
                </div>
              )}
            </Card>
          )}
          {run?.status === 'completed' && !result && !error && (
            <LoadingState label="Loading completed findings…" />
          )}
          {result && run && (
            <PersistedFindings key={run.id} result={result} runId={run.id} />
          )}
          <details
            key={result ? 'review' : activeRun ? 'active' : 'setup'}
            open={!result && !activeRun}
            className="setup-details"
          >
            <summary>
              Dataset &amp; run setup
              <span>
                {artifacts.length
                  ? artifacts.length + ' validated artifact(s)'
                  : 'Upload a dataset to get started'}
              </span>
            </summary>
            <Card className="panel input-panel">
              <div className="section-heading">
                <div>
                  <h2>
                    <FileJson size={18} />
                    Input dataset
                  </h2>
                  <p className="muted text-sm">
                    DatasetBundle JSON only. Arbitrary CSV or payment exports
                    are not supported.
                  </p>
                </div>
              </div>
              <div className="input-grid">
                <div>
                  <label htmlFor="dataset-file">Dataset file</label>
                  <Input
                    id="dataset-file"
                    type="file"
                    accept=".json,application/json"
                    onChange={(event) =>
                      setFile(event.target.files?.[0] ?? null)
                    }
                    disabled={!!busy || activeRun}
                  />
                  <p className="muted text-xs">
                    Validated and checksummed by the API. Identical uploads
                    reuse the artifact.
                  </p>
                  <Button
                    variant="outline"
                    onClick={() => file && void state.upload(file)}
                    disabled={!file || !!busy || activeRun}
                  >
                    <Upload size={15} />
                    {busy === 'upload'
                      ? 'Uploading and validating…'
                      : 'Upload dataset'}
                  </Button>
                </div>
                <div>
                  {artifacts.length ? (
                    <>
                      <label id="artifact-label" htmlFor="artifact-select">
                        Analysis input
                      </label>
                      <Select
                        value={artifactId}
                        onValueChange={(value) =>
                          state.setArtifactId(String(value ?? ''))
                        }
                        disabled={!!busy || activeRun}
                      >
                        <SelectTrigger
                          id="artifact-select"
                          aria-labelledby="artifact-label"
                        >
                          <SelectValue>{artifact?.original_name}</SelectValue>
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
                      <p className="muted text-xs">
                        Validated artifact ·{' '}
                        {artifact?.size_bytes.toLocaleString()} bytes
                      </p>
                      <Button
                        onClick={() => void state.start()}
                        disabled={!artifactId || !!busy || activeRun}
                      >
                        {busy === 'start'
                          ? 'Queuing analysis…'
                          : 'Start analysis'}
                        <ArrowRight size={15} />
                      </Button>
                      <details className="technical-details">
                        <summary>Artifact integrity</summary>
                        <p>Artifact {artifact?.id}</p>
                        <p>SHA256: {artifact?.checksum}</p>
                      </details>
                    </>
                  ) : (
                    <div className="input-hint">
                      <FileJson size={24} />
                      <p>Upload a dataset to enable analysis.</p>
                      <span className="muted text-xs">
                        The server validates the file before accepting it.
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </Card>
          </details>
        </>
      )}
    </ProductShell>
  );
}
